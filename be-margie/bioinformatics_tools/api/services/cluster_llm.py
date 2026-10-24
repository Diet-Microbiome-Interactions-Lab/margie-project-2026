"""Built-in genome chat on the cluster: the user's own model, served by workflow_tools/llm/chat_server.py
in a SLURM job on a GPU node (1 GPU, 10 cores, 80% of the node's memory), started by the first question
and stopped by the server after 5 idle minutes.

The model is the trained one when its folder holds a model, else the base one: margie_sb.llm.trained_model
and margie_sb.llm.base_model in config.yaml, by default <Databases folder>/llm/trained-model and
<Databases folder>/llm/base-model. The API reaches the server with curl on the login node, over the
user's SSH connection, since GPU nodes are not reachable from where the API runs.
"""

from __future__ import annotations

import json
import posixpath
import re
import shlex

from bioinformatics_tools.utilities import ssh_sftp

CONFIG = '.config/bioinformatics-tools/config.yaml'
ADVERT = '.local/share/bsp/chat-endpoint.json'
JOB_NAME = 'margie-chat-llm'
PARTITION = 'gpu'
CPUS = 10
MEM_SHARE = 0.8
# The chat job's walltime; the server exits sooner when idle.
WALLTIME = '08:00:00'


class LlmError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _run(conn, command: str, stdin: bytes | None = None, timeout: int = 60) -> tuple[int, str]:
    ssh = conn.connect()
    chan_in, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    if stdin is not None:
        chan_in.write(stdin)
        chan_in.channel.shutdown_write()
    code = stdout.channel.recv_exit_status()
    return code, stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')


def read_config(conn, home: str) -> dict:
    try:
        return ssh_sftp.read_remote_yaml(f'{home}/{CONFIG}', connection=conn) or {}
    except Exception:
        return {}


def _dig(cfg: dict, dotted: str):
    cur = cfg
    for part in dotted.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def model_folders(cfg: dict) -> dict[str, str]:
    """The trained and base model folders from config.yaml, or their places in the Databases folder."""
    root = ''
    for wf in ('margie_sb', 'margie'):
        r = _dig(cfg, f'{wf}.db_root')
        if r:
            root = str(r).rstrip('/')
            break
    llm_root = str(_dig(cfg, 'db.llm') or (f'{root}/llm' if root else '')).rstrip('/')
    out = {}
    for which, default in (('trained', 'trained-model'), ('base', 'base-model')):
        set_to = str(_dig(cfg, f'margie_sb.llm.{which}_model') or '').strip().rstrip('/')
        out[which] = set_to or (f'{llm_root}/{default}' if llm_root else '')
    return out


def _holds_model(conn, folder: str) -> bool:
    """Whether a folder holds a Hugging Face model: config.json and weights."""
    if not folder:
        return False
    q = shlex.quote(folder)
    code, out = _run(conn, f'test -f {q}/config.json && ls {q} | grep -E "\\.(safetensors|bin)$" | head -1')
    return code == 0 and bool(out.strip())


def choose_model(conn, cfg: dict) -> dict:
    """{'ready', 'model', 'which', 'folders'}: the trained model when its folder holds one, else the base model."""
    folders = model_folders(cfg)
    for which in ('trained', 'base'):
        if _holds_model(conn, folders[which]):
            return {'ready': True, 'model': folders[which], 'which': which, 'folders': folders}
    return {'ready': False, 'model': '', 'which': '', 'folders': folders}


def _sif(cfg: dict, home: str) -> str:
    name = str(_dig(cfg, 'margie_sb.llm.sif') or 'llm.sif')
    if name.startswith('/'):
        return name
    folder = str(_dig(cfg, 'margie_sb.sif_path') or cfg.get('sif_path') or f'{home}/margie/sif').rstrip('/')
    return f'{folder}/{name}'


def server(conn, home: str) -> dict:
    """{'state': 'online'|'starting'|'off', 'host', 'port', 'model'}."""
    code, out = _run(conn, f'cat {shlex.quote(posixpath.join(home, ADVERT))} 2>/dev/null')
    adv = None
    if code == 0 and out.strip():
        try:
            adv = json.loads(out)
        except ValueError:
            adv = None
    if adv and adv.get('host') and adv.get('port'):
        host, port = str(adv['host']), int(adv['port'])
        if re.fullmatch(r'[\w.-]+', host):
            c, h = _run(conn, f'curl -s -m 5 http://{host}:{port}/health')
            try:
                health = json.loads(h) if c == 0 else {}
            except ValueError:
                health = {}
            if health.get('ok'):
                return {'state': 'online', 'host': host, 'port': port, 'model': adv.get('model', '')}
    code, out = _run(conn, f'squeue -h -u "$USER" -n {JOB_NAME} -o "%i %T" 2>/dev/null')
    if code == 0 and out.strip():
        return {'state': 'starting', 'job': out.split()[0]}
    return {'state': 'off'}


def _node_mem_mb(conn) -> int:
    """80% of the smallest node memory in the GPU partition, in MB."""
    code, out = _run(conn, f'sinfo -h -p {PARTITION} -o "%m" 2>/dev/null')
    sizes = [int(m) for m in re.findall(r'\d+', out)] if code == 0 else []
    if not sizes:
        raise LlmError(f'Could not read the {PARTITION} partition from SLURM.', 502)
    return int(min(sizes) * MEM_SHARE)


def start(conn, home: str, cfg: dict, model: str) -> str:
    """Submits the chat server job; returns its job id."""
    backend = f'{home}/bioinformatics-tools'
    sif = _sif(cfg, home)
    code, _ = _run(conn, f'test -f {shlex.quote(sif)}')
    if code != 0:
        raise LlmError(f'The LLM container is not there yet: {sif}. Build it in Install, or set margie_sb.llm.sif.', 400)
    account = str(_dig(cfg, 'compute.cluster_default.account') or '').strip()
    logs = posixpath.join(home, posixpath.dirname(ADVERT))
    env = (f'MARGIE_LLM_MODEL={shlex.quote(model)} MARGIE_LLM_SIF={shlex.quote(sif)} '
           f'MARGIE_BACKEND={shlex.quote(backend)} MARGIE_CHAT_ADVERTISE={shlex.quote(posixpath.join(home, ADVERT))}')
    opts = (f'--parsable -J {JOB_NAME} -p {PARTITION} --gres=gpu:1 -c {CPUS} --mem={_node_mem_mb(conn)}M '
            f'-t {WALLTIME} -D {shlex.quote(logs)}' + (f' -A {shlex.quote(account)}' if account else ''))
    script = f'{backend}/bioinformatics_tools/workflow_tools/llm/chat-server.sbatch'
    code, out = _run(conn, f'mkdir -p {shlex.quote(logs)} && {env} sbatch {opts} {shlex.quote(script)}')
    job = out.strip().split(';')[0]
    if code != 0 or not job.isdigit():
        raise LlmError(f'SLURM did not take the chat job: {out.strip()[:300] or "no reason given"}', 502)
    return job


def generate(conn, host: str, port: int, system: str, prompt: str, max_tokens: int) -> str:
    """Asks the chat server one question through the login node."""
    body = json.dumps({'system': system, 'prompt': prompt, 'max_tokens': max_tokens}).encode()
    code, out = _run(conn, f"curl -s -m 600 -X POST -H 'Content-Type: application/json' --data-binary @- http://{host}:{port}/chat",
                     stdin=body, timeout=620)
    try:
        d = json.loads(out) if code == 0 else {}
    except ValueError:
        d = {}
    if 'text' not in d:
        raise LlmError(f'The chat model did not answer: {d.get("error") or out.strip()[:300] or "no reply"}', 502)
    return str(d['text']).strip()


def status(conn, home: str, cfg: dict | None = None) -> dict:
    """What the chat panel shows for the built-in model: whether it can run, which model, and the server's state."""
    cfg = cfg if cfg is not None else read_config(conn, home)
    chosen = choose_model(conn, cfg)
    folders = chosen['folders']
    info = {'ready': False, 'model': chosen['model'], 'which': chosen['which'], 'folders': folders, 'state': 'off'}
    if not chosen['ready']:
        where = ' or '.join(f for f in (folders['trained'], folders['base']) if f) or 'the folders in Settings → LLM'
        return {**info, 'note': f'No model found. Put one (Hugging Face format: config.json and its weights) in {where}, '
                                'or point Settings → LLM at its folder.'}
    sif = _sif(cfg, home)
    code, _ = _run(conn, f'test -f {shlex.quote(sif)}')
    if code != 0:
        return {**info, 'note': f'Model found ({chosen["which"]}): {chosen["model"]}. The LLM container ({sif}) is not ready yet, '
                                'so the built-in model cannot run.'}
    srv = server(conn, home)
    state = srv['state']
    note = {
        'online': f'Running on {srv.get("host", "a GPU node")}.',
        'starting': f'Starting on a GPU node (job {srv.get("job", "")}); this takes a few minutes.',
        'off': 'Ready. The first question starts it on a GPU node (1 GPU, 10 cores, 80% of the node\'s memory); '
               'it stops after 5 idle minutes.',
    }[state]
    where = {'host': srv['host'], 'port': srv['port']} if state == 'online' else {}
    return {**info, **where, 'ready': True, 'state': state, 'sif': sif,
            'note': f'{note} Model ({chosen["which"]}): {chosen["model"]}.'}
