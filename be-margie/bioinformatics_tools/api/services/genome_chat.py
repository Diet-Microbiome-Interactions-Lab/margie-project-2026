"""
Chat with the genome, on the website: a model answers questions about one genome's results through
three tools (list files, read one, search the report table), confined to that genome's folders on
the cluster and capped by a reading budget; each read becomes cited evidence [E1], [E2]... A port of
the desktop app's lib/server/genome-chat.ts, reading the results over the user's own SSH connection.

Everything is kept in the user's cluster account: the choices in
~/.config/bioinformatics-tools/genome-chat.json, each genome's conversation in
~/.local/share/bioinformatics-tools/genome-chat/<genome>.json, and API keys in
~/.config/bioinformatics-tools/secrets/chat-keys.json (folder 700, file 600). A key is stored
encrypted with a key only this server holds (derived from BSP_ENCRYPTION_KEY), so the file alone is
no use to someone who gets into the account, and it expires: after the days chosen when it was
saved it is refused and removed. The browser only ever sees a key's last four characters.

Providers: Claude through the Anthropic SDK (refusals fall back server-side where the model allows);
OpenAI, Gemini and OpenAI-compatible services through chat completions.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import logging
import os
import posixpath
import re
import shlex
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from bioinformatics_tools.utilities import ssh_sftp

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------- providers

PROVIDERS: dict[str, dict] = {
    'anthropic': {
        'label': 'Claude (Anthropic)',
        'base': '',
        'models': ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5', 'claude-fable-5-1'],
        'policy': 'https://www.anthropic.com/legal/commercial-terms',
        'keys': 'https://console.anthropic.com/settings/keys',
    },
    'openai': {
        'label': 'OpenAI',
        'base': 'https://api.openai.com/v1',
        'models': ['gpt-5', 'gpt-5-mini', 'gpt-4.1'],
        'policy': 'https://openai.com/enterprise-privacy/',
        'keys': 'https://platform.openai.com/api-keys',
    },
    'gemini': {
        'label': 'Google Gemini',
        'base': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'models': ['gemini-2.5-pro', 'gemini-2.5-flash'],
        'policy': 'https://ai.google.dev/gemini-api/terms',
        'keys': 'https://aistudio.google.com/app/apikey',
    },
    'custom': {'label': 'Other (OpenAI-compatible)', 'base': '', 'models': [], 'policy': '', 'keys': ''},
    'builtin': {'label': 'Built-in (on this computer)', 'base': '', 'models': [], 'policy': '', 'keys': ''},
}

DEFAULTS = {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'baseUrl': '', 'budget': 10000,
            'answerTokens': 16000, 'consented': []}

# How long a saved key is kept, in days: offered choices and the default.
KEY_DAYS = (1, 7, 10, 30)
KEY_DAYS_DEFAULT = 10

# Claude models whose refusals the API re-runs on a fallback model (fallbacks: "default").
FALLBACK_MODELS = {'claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5'}
FALLBACK_BETA = 'server-side-fallback-2026-07-01'

SETTINGS_FILE = '.config/bioinformatics-tools/genome-chat.json'
SECRETS_DIR = '.config/bioinformatics-tools/secrets'
KEYS_FILE = f'{SECRETS_DIR}/chat-keys.json'
HISTORY_DIR = '.local/share/bioinformatics-tools/genome-chat'

# The most of one file read for the model (the report table is read whole once per question).
READ_LIMIT = 1_000_000
TEXT = re.compile(r'\.(tsv|txt|log|csv|json|md|tab|gff|gff3|out|tbl|yaml|yml|faa|fna|fa|fasta)$', re.I)


class ChatError(Exception):
    """A request that cannot be answered; the message and HTTP status go to the page."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class ReadError(Exception):
    """A file that could not be read; reported to the model, not the researcher."""


def safe_genome(g) -> str:
    s = str(g or '')
    if not re.fullmatch(r'[\w.-]+', s) or s in ('.', '..'):
        raise ChatError('That is not a genome name.', 400)
    return s


# ---------------------------------------------------------------- files in the user's account

def _run(conn, command: str) -> tuple[int, str]:
    ssh = conn.connect()
    _, stdout, stderr = ssh.exec_command(command, timeout=60)
    code = stdout.channel.recv_exit_status()
    return code, stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')


def _read(conn, path: str, limit: int | None = None) -> bytes | None:
    """The file's bytes (at most limit), or None when it is not there."""
    sftp = conn.connect().open_sftp()
    try:
        with sftp.open(path, 'rb') as fh:
            return fh.read(limit) if limit else fh.read()
    except FileNotFoundError:
        return None
    finally:
        sftp.close()


def _read_json(conn, path: str):
    raw = _read(conn, path)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        return None


def _write(conn, path: str, text: str, private: bool = False) -> None:
    """Writes a file whole (beside it, then moved over it); private: folder 700, file 600 before any content."""
    folder = posixpath.dirname(path)
    code, out = _run(conn, f'mkdir -p {shlex.quote(folder)}' + (f' && chmod 700 {shlex.quote(folder)}' if private else ''))
    if code != 0:
        raise ChatError(f'Could not make {folder} on the cluster: {out.strip()}', 502)
    sftp = conn.connect().open_sftp()
    tmp = f'{path}.tmp'
    try:
        with sftp.open(tmp, 'w') as fh:
            if private:
                sftp.chmod(tmp, 0o600)
            fh.write(text.encode())
        sftp.posix_rename(tmp, path)
    finally:
        sftp.close()


# ---------------------------------------------------------------- choices

def load_settings(conn, home: str) -> dict:
    stored = _read_json(conn, f'{home}/{SETTINGS_FILE}')
    return {**DEFAULTS, **(stored if isinstance(stored, dict) else {})}


def _clean_settings(current: dict, body: dict) -> dict:
    s = dict(current)
    if body.get('provider') in PROVIDERS:
        s['provider'] = body['provider']
    if isinstance(body.get('model'), str):
        s['model'] = body['model'].strip()[:120]
    if isinstance(body.get('baseUrl'), str):
        s['baseUrl'] = body['baseUrl'].strip()[:300]
    for key, low, high in (('budget', 1000, 400000), ('answerTokens', 500, 64000)):
        value = body.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            s[key] = max(low, min(high, int(round(value))))
    if isinstance(body.get('consented'), list):
        s['consented'] = [p for p in body['consented'] if p in PROVIDERS]
    return s


# ---------------------------------------------------------------- keys: encrypted, and dated to expire

def _fernet() -> Fernet:
    """This server's key for chat API keys, derived from BSP_ENCRYPTION_KEY (never the SSH-key one itself)."""
    master = os.environ.get('BSP_ENCRYPTION_KEY', '')
    if not master:
        raise ChatError('This server cannot keep keys: it has no encryption key.', 500)
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=b'margie', info=b'genome-chat api keys').derive(master.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def seal(key: str, now: float | None = None) -> str:
    return _fernet().encrypt_at_time(key.encode(), int(now if now is not None else time.time())).decode()


def unseal(token: str, days: int, now: float | None = None) -> str | None:
    """The key, or None when it has expired (or was sealed by another server key)."""
    try:
        return _fernet().decrypt_at_time(token.encode(), days * 86400, int(now if now is not None else time.time())).decode()
    except InvalidToken:
        return None


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds')


def _keys(conn, home: str, now: float | None = None) -> tuple[dict, list[str]]:
    """Returns ({provider: {key, expires}} still usable, providers whose key expired); expired ones are removed."""
    path = f'{home}/{KEYS_FILE}'
    stored = _read_json(conn, path)
    stored = stored if isinstance(stored, dict) else {}
    usable, expired = {}, []
    for p, rec in list(stored.items()):
        if p not in PROVIDERS or not isinstance(rec, dict) or not isinstance(rec.get('token'), str):
            stored.pop(p, None)
            continue
        days = int(rec.get('days') or KEY_DAYS_DEFAULT)
        key = unseal(rec['token'], days, now)
        if key is None:
            stored.pop(p)
            expired.append(p)
            continue
        usable[p] = {'key': key, 'expires': rec.get('expires', '')}
    if expired:
        _write(conn, path, json.dumps(stored, indent=1) + '\n', private=True)
    return usable, expired


def save_key(conn, home: str, provider: str, key: str | None, days: int = KEY_DAYS_DEFAULT, now: float | None = None) -> None:
    """Saves one provider's key (sealed, with its expiry), or with None removes it."""
    if provider not in PROVIDERS:
        raise ChatError('Unknown provider.', 400)
    path = f'{home}/{KEYS_FILE}'
    stored = _read_json(conn, path)
    stored = stored if isinstance(stored, dict) else {}
    if key and key.strip():
        days = days if days in KEY_DAYS else KEY_DAYS_DEFAULT
        t = time.time() if now is None else now
        stored[provider] = {'token': seal(key.strip(), t), 'days': days, 'saved': _iso(t), 'expires': _iso(t + days * 86400)}
    else:
        stored.pop(provider, None)
    _write(conn, path, json.dumps(stored, indent=1) + '\n', private=True)


def public_settings(conn, home: str) -> dict:
    """What the page may see: the choices, and each key only as its last four characters and expiry."""
    usable, expired = _keys(conn, home)
    keys = {p: ({'saved': True, 'last4': usable[p]['key'][-4:], 'expires': usable[p]['expires'], 'cluster': True}
                if p in usable else {'saved': False}) for p in PROVIDERS}
    return {
        'settings': load_settings(conn, home),
        'keys': keys,
        'expired': expired,
        'keyDays': list(KEY_DAYS),
        'providers': PROVIDERS,
        'builtin': {'ready': False, 'model': '', 'note': 'The built-in model runs only in the MARGIE app on your own computer.'},
    }


def update_settings(conn, home: str, body: dict) -> dict:
    """Saves the choices; `key` saves a key (with `keyDays`), `key: null` removes it."""
    s = _clean_settings(load_settings(conn, home), body or {})
    _write(conn, f'{home}/{SETTINGS_FILE}', json.dumps(s, indent=1) + '\n')
    if 'key' in (body or {}):
        who = body.get('keyFor') if body.get('keyFor') in PROVIDERS else s['provider']
        days = body.get('keyDays') if isinstance(body.get('keyDays'), int) else KEY_DAYS_DEFAULT
        save_key(conn, home, who, body.get('key') if isinstance(body.get('key'), str) else None, days)
    return public_settings(conn, home)


# ---------------------------------------------------------------- the conversation, kept per genome

def _history_file(home: str, genome: str) -> str:
    return f'{home}/{HISTORY_DIR}/{safe_genome(genome)}.json'


def read_history(conn, home: str, genome: str) -> list:
    if not genome:
        return []
    turns = _read_json(conn, _history_file(home, genome))
    return turns if isinstance(turns, list) else []


def clear_history(conn, home: str, genome: str) -> None:
    _run(conn, f'rm -f {shlex.quote(_history_file(home, genome))}')


# ---------------------------------------------------------------- the genome's results, and nothing else

class Source:
    """A genome's folders on the cluster, read over the user's connection; paths are shown relative to base."""

    depth = 2

    def __init__(self, conn, genome: str, roots, table):
        def clean(p):
            return posixpath.normpath(p).rstrip('/') if isinstance(p, str) and p.startswith('/') else ''
        self.conn = conn
        self.roots = list(dict.fromkeys(r for r in map(clean, roots if isinstance(roots, list) else []) if len(r) > 1))
        if not self.roots:
            raise ChatError(f'No results for {genome} on the cluster yet.', 404)
        parts = [r.split('/') for r in self.roots]
        common = []
        for i, piece in enumerate(parts[0]):
            if all(len(q) > i and q[i] == piece for q in parts):
                common.append(piece)
            else:
                break
        base = '/'.join(common) or '/'
        # One folder: shown from the folder above it, so paths start with its name.
        self.base = posixpath.dirname(base) if base in self.roots else base
        t = clean(table)
        self.table = t if t and self.within(t) else None

    def within(self, p: str) -> bool:
        return any(p == r or p.startswith(r + '/') for r in self.roots)

    def inside(self, p) -> str | None:
        s = str(p or '')
        full = posixpath.normpath(s if s.startswith('/') else posixpath.join(self.base, s)).rstrip('/')
        return full if self.within(full) else None

    def rel(self, p: str) -> str:
        return posixpath.relpath(p, self.base)

    def list(self, folder: str) -> list[dict]:
        return [{'name': e['name'], 'dir': e['type'] == 'directory', 'size': e.get('size') or 0}
                for e in ssh_sftp.list_remote_dir(folder, connection=self.conn)]

    def is_dir(self, p: str) -> bool:
        if TEXT.search(p):
            return False
        try:
            return ssh_sftp.check_remote_path_kind(p, self.conn) == 'directory'
        except Exception:
            return False

    def read(self, path: str) -> str:
        try:
            raw = _read(self.conn, path, READ_LIMIT + 1)
        except PermissionError:
            raise ReadError(f'Could not read {path}: permission denied.')
        if raw is None:
            raise ReadError(f'Could not read {path}: it is not there (a link to a file that has moved, or one not written yet).')
        if b'\x00' in raw[:8192]:
            return ''
        text = raw[:READ_LIMIT].decode(errors='replace')
        return f'{text}\n[only the first megabyte of this file can be read from here]' if len(raw) > READ_LIMIT else text


KEEP = ['gene_id', 'RAST_feature_id', 'FEATURE_TYPE', 'RAST_start', 'RAST_end', 'IS_IN_OPERON?', 'UniOP_OPERON_id',
        'best_consensus_product_descriptor', 'best_consensus_product_descriptor_source',
        'ADJUSTED_CONFIDENCE_WITH_OPERON_CONTEXT', 'CONFIDENCE_TIER', 'NEEDS_REVIEW?', 'NEEDS_REVIEW_REASON']


class Toolkit:
    """The three tools, bound to one genome's folders, one reading budget and one evidence list."""

    def __init__(self, genome: str, budget: int, src: Source):
        self.genome, self.budget, self.src = genome, budget, src
        self.evidence: list[dict] = []
        self.used = 0
        self._table_text: str | None = None

    def _cite(self, kind: str, path: str, detail: str, full: str | None = None) -> str:
        eid = f'E{len(self.evidence) + 1}'
        self.evidence.append({'id': eid, 'kind': kind, 'path': path, 'detail': detail, **({'full': full} if full else {})})
        return eid

    def _spend(self, text: str) -> str:
        left = self.budget - self.used
        if left <= 0:
            return '[reading budget used up: answer with what you have read]'
        tokens = -(-len(text) // 4)
        if tokens <= left:
            self.used += tokens
            return text
        self.used = self.budget
        return text[:left * 4] + '\n[cut off: the reading budget ran out here]'

    def list_files(self, folder: str | None = None) -> str:
        starts = [self.src.inside(folder)] if folder else self.src.roots
        if any(s is None for s in starts):
            return f"Not in {self.genome}'s results: {folder}"
        lines: list[str] = []

        def walk(d: str, depth: int):
            if len(lines) > 400:
                return
            try:
                entries = self.src.list(d)
            except Exception:
                return
            for e in sorted(entries, key=lambda x: x['name']):
                p = posixpath.join(d, e['name'])
                if e['dir']:
                    lines.append(f'{self.src.rel(p)}/')
                    if depth < self.src.depth:
                        walk(p, depth + 1)
                else:
                    lines.append(f"{self.src.rel(p)}  ({e['size']} bytes)")

        for s in starts:
            walk(s, 0)
        what = folder or f"{self.genome}'s results"
        eid = self._cite('list', what, f'{len(lines)} entries', starts[0] if len(starts) == 1 else None)
        return self._spend(f'[{eid}] files under {what}:\n' + '\n'.join(lines))

    def read_file(self, path: str, start_line: int = 1, max_lines: int = 200) -> str:
        real = self.src.inside(path)
        if not real:
            return f"Not in {self.genome}'s results: {path}"
        if self.src.is_dir(real):
            return self.list_files(path)
        if not TEXT.search(real):
            return f'{path} is not a text file (tables, logs and text only).'
        all_lines = self.src.read(real).split('\n')
        start = max(1, int(start_line))
        n = max(1, min(2000, int(max_lines)))
        chunk = all_lines[start - 1:start - 1 + n]
        span = f'lines {start}-{start + len(chunk) - 1} of {len(all_lines)}'
        eid = self._cite('read', self.src.rel(real), span, real)
        return self._spend(f'[{eid}] {self.src.rel(real)}, {span}:\n' + '\n'.join(chunk))

    def search_table(self, query: str, max_rows: int = 20) -> str:
        table = self.src.table
        if not table:
            return f'{self.genome} has no report table yet.'
        if self._table_text is None:
            raw = _read(self.src.conn, table)
            self._table_text = raw.decode(errors='replace') if raw is not None else ''
        head, *rows = [r for r in self._table_text.split('\n') if r]
        if not head:
            return f"{self.genome}'s report table could not be read."
        cols = [re.sub(r'^Column-[A-Z]+:\s*', '', c) for c in head.split('\t')]
        keep = [cols.index(k) for k in KEEP if k in cols]
        q = str(query or '').lower().strip()
        hits = [r for r in rows if q in r.lower()]
        shown = hits[:max(1, min(100, int(max_rows)))]
        eid = self._cite('search', self.src.rel(table), f'"{query}": {len(hits)} row{"" if len(hits) == 1 else "s"}', table)
        body = '\n'.join(['\t'.join(cols[i] for i in keep),
                          *('\t'.join((r.split('\t') + [''] * len(cols))[i] for i in keep) for r in shown)])
        more = f' (first {len(shown)} shown)' if len(hits) > len(shown) else ''
        return self._spend(f'[{eid}] {self.src.rel(table)}: {len(hits)} of {len(rows)} genes match "{query}"{more}; '
                           f'key columns only (read the file for all {len(cols)}):\n{body}')

    def run(self, name: str, args: dict) -> str:
        """Runs one tool call; read failures go back to the model as text."""
        try:
            if name == 'list_files':
                return self.list_files(args.get('dir') if isinstance(args.get('dir'), str) else None)
            if name == 'read_file':
                return self.read_file(str(args.get('path') or ''), int(args.get('start_line') or 1), int(args.get('max_lines') or 200))
            if name == 'search_table':
                return self.search_table(str(args.get('query') or ''), int(args.get('max_rows') or 20))
            return f'No tool named {name}.'
        except (ValueError, TypeError):
            return f'The arguments for {name} were not usable; try again.'
        except ReadError as e:
            return f'[not read] {e} Try another file, or answer with what you have.'
        except Exception as e:
            LOGGER.warning('chat tool %s failed: %s', name, e)
            return f'[not read] {e} Try another file, or answer with what you have.'


TOOL_DOCS = {
    'list_files': {
        'description': "List the files and folders in this genome's results (or under one folder of them), with sizes.",
        'schema': {'type': 'object', 'properties': {'dir': {'type': 'string', 'description': "A folder path as listed, relative to the results folder. Leave out for all of the genome's folders."}},
                   'additionalProperties': False},
    },
    'read_file': {
        'description': "Read lines of one text file in this genome's results (tables, logs, text).",
        'schema': {'type': 'object', 'properties': {
            'path': {'type': 'string', 'description': 'The file path as listed, relative to the results folder.'},
            'start_line': {'type': 'integer', 'description': 'First line to read (1-based). Default 1.'},
            'max_lines': {'type': 'integer', 'description': 'How many lines (default 200, at most 2000).'}},
            'required': ['path'], 'additionalProperties': False},
    },
    'search_table': {
        'description': "Search the genome's report table (one row per gene) for a word, gene id, product name, EC number or operon id; returns matching genes with their key columns.",
        'schema': {'type': 'object', 'properties': {'query': {'type': 'string'}, 'max_rows': {'type': 'integer', 'description': 'Default 20, at most 100.'}},
                   'required': ['query'], 'additionalProperties': False},
    },
}


def system_prompt(genome: str, roots_rel: list[str], table_path: str) -> str:
    return f'''You help a researcher understand the annotation of one prokaryotic genome, "{genome}", produced by MARGIE (gene calling, a dozen annotation tools, operon prediction, consolidation, labelling and confidence scoring into tiers highest/high/medium/fair/low).

You can read only this genome's results, with the tools list_files, read_file and search_table. Its folders are: {', '.join(roots_rel)}. The report table is {table_path} (one row per gene; confidence columns C1-C4, CONFIDENCE_TIER, NEEDS_REVIEW?). Each tool's folder has a *-pipeline-log.txt with the commands it ran.

Every tool result starts with an evidence tag such as [E3]. Base your answer only on what you read, and cite the tags for each claim. If what you read does not settle the question, say so and say what would. Reading is limited by a budget, so search before reading whole files, and read only the lines you need.

A question may start with what the researcher had open in MARGIE (a gene, an operon, a contig, a table filter). Treat that as the subject when the question does not name one ("this gene", "here"), but you may read anything else in the genome's results.

Answer in well-structured Markdown: short headings where they help, bullet lists, and tables for tabular facts. Do not paste raw file contents or code blocks unless asked.'''


def _with_context(t: dict) -> str:
    return f"[Open in MARGIE when asked: {t['context']}]\n\n{t['text']}" if t.get('role') == 'user' and t.get('context') else t.get('text', '')


LENGTH_NOTE = '\n\n_The answer reached its length limit; raise "Answer length" to let it finish._'
KEPT_READING = '_The model kept reading without answering; ask a narrower question or raise the reading budget._'


# ---------------------------------------------------------------- Claude

def ask_claude(kit: Toolkit, s: dict, key: str, system: str, history: list, question: str, client=None) -> str:
    """Asks Claude, running its tool calls against the genome's results until it answers (at most 10 rounds)."""
    import anthropic

    client = client or anthropic.Anthropic(api_key=key)
    model = s.get('model') or 'claude-opus-5-5'
    params = {
        'model': model,
        'max_tokens': s['answerTokens'],
        'system': system,
        'tools': [{'name': n, 'description': d['description'], 'input_schema': d['schema']} for n, d in TOOL_DOCS.items()],
        'messages': [*({'role': t['role'], 'content': _with_context(t)} for t in history), {'role': 'user', 'content': question}],
    }
    # Earlier Claude generations take no adaptive thinking.
    if not model.startswith(('claude-haiku-4', 'claude-3', 'claude-sonnet-4-5', 'claude-opus-4-5', 'claude-opus-4-1')):
        params['thinking'] = {'type': 'adaptive'}
    falls = model in FALLBACK_MODELS
    try:
        for _ in range(10):
            # Streamed, so a long answer is not cut off by a request timeout.
            stream = (client.beta.messages.stream(**params, betas=[FALLBACK_BETA], fallbacks='default') if falls
                      else client.messages.stream(**params))
            with stream as live:
                message = live.get_final_message()
            if message.stop_reason == 'refusal':
                return '_The model declined to answer this question._'
            if message.stop_reason in ('tool_use', 'pause_turn'):
                # The whole turn goes back unchanged (its thinking blocks too), then every result in one message.
                params['messages'].append({'role': 'assistant', 'content': message.content})
                if message.stop_reason == 'tool_use':
                    params['messages'].append({'role': 'user', 'content': [
                        {'type': 'tool_result', 'tool_use_id': b.id, 'content': kit.run(b.name, b.input if isinstance(b.input, dict) else {})}
                        for b in message.content if b.type == 'tool_use']})
                continue
            text = '\n\n'.join(b.text for b in message.content if b.type == 'text').strip()
            if message.stop_reason == 'max_tokens':
                return f'{text}{LENGTH_NOTE}'
            return text or '_No answer came back._'
        return KEPT_READING
    except anthropic.AuthenticationError:
        raise ChatError('Claude did not accept the API key.', 401)
    except anthropic.PermissionDeniedError:
        raise ChatError('This API key may not use that model.', 403)
    except anthropic.NotFoundError:
        raise ChatError(f'No model named "{model}".', 404)
    except anthropic.RateLimitError:
        raise ChatError('Claude is limiting requests from this key; try again in a moment.', 429)
    except anthropic.BadRequestError as e:
        raise ChatError(f'Claude refused the request: {e.message}', 400)
    except anthropic.APIStatusError as e:
        raise ChatError(f'Claude answered with an error ({e.status_code}): {e.message}', 502)
    except anthropic.APIConnectionError:
        raise ChatError('Could not reach Claude.', 502)


# ---------------------------------------------------------------- OpenAI, Gemini and OpenAI-compatible services

def public_https(url: str) -> str:
    """The service's base URL, if it is https and every address it names is on the public internet.

    This server runs inside a cluster's network; it must not be pointed at machines there."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme != 'https' or not parts.hostname:
        raise ChatError('On the website the service must be an https address on the internet (a model on your own computer works only in the MARGIE app).', 400)
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ChatError(f'{parts.hostname} cannot be found.', 400)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ChatError(f'{parts.hostname} is not on the public internet.', 400)
    return url.rstrip('/')


def _post_json(url: str, key: str, body: dict) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST', headers={
        'Content-Type': 'application/json', **({'Authorization': f'Bearer {key}'} if key else {})})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


def ask_openai(kit: Toolkit, s: dict, p: str, key: str, system: str, history: list, question: str, post=_post_json) -> str:
    """Asks OpenAI, Gemini or an OpenAI-compatible service via chat completions, over the same three tools."""
    label = PROVIDERS[p]['label']
    base = public_https(s.get('baseUrl', '')) if p == 'custom' else PROVIDERS[p]['base']
    if not base:
        raise ChatError("Give the service's base URL first (it ends in /v1).", 400)
    if not s.get('model'):
        raise ChatError('Choose a model first.', 400)
    tools = [{'type': 'function', 'function': {'name': n, 'description': d['description'], 'parameters': d['schema']}}
             for n, d in TOOL_DOCS.items()]
    messages: list[dict] = [{'role': 'system', 'content': system},
                            *({'role': t['role'], 'content': _with_context(t)} for t in history),
                            {'role': 'user', 'content': question}]
    limit = {'max_completion_tokens': s['answerTokens']} if p == 'openai' else {'max_tokens': s['answerTokens']}
    for _ in range(10):
        try:
            status, d = post(f'{base}/chat/completions', key, {'model': s['model'], 'messages': messages, 'tools': tools, **limit})
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ChatError(f'Could not reach {label}: {e}', 502)
        if status >= 400:
            why = (d.get('error') or {}).get('message') if isinstance(d.get('error'), dict) else d.get('message')
            if status == 401:
                raise ChatError(f'{label} did not accept the API key.', 401)
            raise ChatError(f'{label} answered with an error ({status}): {why or "no reason given"}', 502)
        choice = (d.get('choices') or [{}])[0]
        m = choice.get('message')
        if not m:
            raise ChatError('The service sent no answer.', 502)
        calls = m.get('tool_calls') or []
        if not calls:
            text = str(m.get('content') or '').strip()
            if choice.get('finish_reason') == 'length':
                return f'{text}{LENGTH_NOTE}'
            return text or '_No answer came back._'
        messages.append({'role': 'assistant', 'content': m.get('content'), 'tool_calls': calls})
        for c in calls:
            try:
                args = json.loads(c['function'].get('arguments') or '{}')
            except (ValueError, KeyError, TypeError):
                messages.append({'role': 'tool', 'tool_call_id': c.get('id'), 'content': 'The arguments were not valid JSON; try again.'})
                continue
            messages.append({'role': 'tool', 'tool_call_id': c.get('id'), 'content': kit.run(c['function']['name'], args if isinstance(args, dict) else {})})
    return KEPT_READING


# ---------------------------------------------------------------- one question

def ask(conn, home: str, genome_in, question: str, context_in, remote: dict | None) -> dict:
    """Asks one question about a genome; returns the answer with the evidence it read, and keeps both."""
    genome = safe_genome(genome_in)
    q = str(question or '').strip()
    context = str(context_in or '').strip()[:600]
    if not q:
        raise ChatError('Ask a question first.', 400)
    s = load_settings(conn, home)
    p = s['provider'] if s.get('provider') in PROVIDERS else 'anthropic'
    if p == 'builtin':
        raise ChatError('The built-in model runs only in the MARGIE app on your own computer.', 400)
    if p not in s.get('consented', []):
        raise ChatError('Read and accept the data notice for this provider first.', 400)
    usable, expired = _keys(conn, home)
    key = usable.get(p, {}).get('key', '')
    if not key and p != 'custom':
        if p in expired:
            raise ChatError(f'Your {PROVIDERS[p]["label"]} key expired and was removed. Paste it again (or a new one) in the chat settings.', 400)
        raise ChatError(f'Add your {PROVIDERS[p]["label"]} API key first.', 400)

    remote = remote or {}
    kit = Toolkit(genome, int(s['budget']), Source(conn, genome, remote.get('roots'), remote.get('table')))
    history = read_history(conn, home, genome)[-12:]
    table = kit.src.rel(kit.src.table) if kit.src.table else f'{genome}/scoring/FINAL_ANNOTATION_WITH_CONFIDENCE.tsv (not made yet)'
    system = system_prompt(genome, [kit.src.rel(r) for r in kit.src.roots], table)
    asked = {'role': 'user', 'text': q, 'at': _iso(time.time()), **({'context': context} if context else {})}
    text = (ask_claude(kit, s, key, system, history, _with_context(asked)) if p == 'anthropic'
            else ask_openai(kit, s, p, key, system, history, _with_context(asked)))
    answer = {'role': 'assistant', 'text': text, 'at': _iso(time.time()), 'evidence': kit.evidence,
              'provider': p, 'model': s.get('model', ''), 'read': kit.used}
    _write(conn, _history_file(home, genome), json.dumps([*read_history(conn, home, genome), asked, answer], indent=1) + '\n')
    return answer
