"""
Manages each user's working copies of MARGIE's growing databases on scratch and their backups on depot.
Base copies on depot are only read; a user's first run copies the base (or newest backup) to
<scratch>/margie/margie-databases/<store>/<user>-<name>-vN, and "Back up" copies vN to depot and renames the working copy to vN+1.
Copies run as a SLURM job (or detached on the login node) driven by a plan file; nothing is ever deleted.
A copy the user already put in the working folder is used where it is instead (own_copy, adopt).
"""

from __future__ import annotations

import json
import os
import logging
import posixpath
import re
import shlex
import time

from bioinformatics_tools.utilities import ssh_sftp
from bioinformatics_tools.workflow_tools.workflow_registry import SHARED_FOLDER_DEFAULTS

LOGGER = logging.getLogger(__name__)

# Shared storage for the group (MARGIE_SHARED_ROOT on the server); empty: none.
DEPOT = os.environ.get('MARGIE_SHARED_ROOT', '').rstrip('/')
# Base copies, one folder per database; each user's backups go beside them.
GENERATED = f'{DEPOT}/databases/margie-generated-databases' if DEPOT else ''
# A group folder to suggest from the SLURM account, where the server names a pattern
# (MARGIE_GROUP_FOLDER_PATTERN, with {account} in it); shown in Settings, not written.
GROUP_PATTERN = os.environ.get('MARGIE_GROUP_FOLDER_PATTERN', '').strip()


def depot(cfg: dict | None) -> str:
    """The group folder: margie_sb.shared_root from the user's config, else the server's MARGIE_SHARED_ROOT."""
    chosen = _cfg_get(cfg or {}, 'margie_sb.shared_root')
    return chosen.strip().rstrip('/') if isinstance(chosen, str) and chosen.strip() else DEPOT


def generated(cfg: dict | None) -> str:
    """The folder of base databases under the group folder."""
    d = depot(cfg)
    return f'{d}/databases/margie-generated-databases' if d else ''


def base_of(store: dict, cfg: dict | None) -> str:
    """Where a first run copies a store from: its own setting, else its place under the group folder."""
    chosen = _cfg_get(cfg or {}, f"margie_sb.stores.base.{store['id']}")
    if isinstance(chosen, str) and chosen.strip():
        return chosen.strip().rstrip('/')
    g = generated(cfg)
    return f"{g}/{store['base_rel']}" if g else ''


def resolve_base(conn, store: dict, cfg: dict | None) -> str:
    """The base that exists on the cluster: base_of(), or else the first file or folder of that
    name anywhere under the group folder (a group may lay its folder out its own way). '' when none."""
    guess = base_of(store, cfg)
    if guess:
        code, _ = _run(conn, f'test -e {shlex.quote(guess)}')
        if code == 0:
            return guess
    d = depot(cfg)
    if not d:
        return ''
    name = posixpath.basename(store['base_rel'])
    kind = 'd' if store['kind'] == 'dir' else 'f'
    code, out = _run(conn, f'find {shlex.quote(d)} -maxdepth 6 -type {kind} -name {shlex.quote(name)} 2>/dev/null | head -1')
    return out.strip() if code == 0 and out.strip() else ''


# Where the backend checkout keeps the starter operon reference (scoring/reference/operon-db.manifest.txt).
STARTER_OCC = 'bioinformatics-tools/bioinformatics_tools/workflow_tools/scoring/reference/operon-db.pkl'
# The user's MARGIE folder on scratch, and the folders in it used when Settings names none:
# <scratch>/margie/margie-databases (every store and run archive), margie-input and margie-output.
HOME_NAME = 'margie'
ROOT_NAME = 'margie-databases'
INPUT_NAME = 'margie-input'
OUTPUT_NAME = 'margie-output'
# The genomes and results folders a config leaves empty, and their folder under HOME_NAME.
DEFAULT_FOLDERS = {'margie_sb.input_path': INPUT_NAME, 'margie_sb.output_path': OUTPUT_NAME}
# The folder those (and the databases folder) go in when left empty: /scratch/<cluster>/<user>/margie.
WORKING_KEY = 'margie_sb.working_folder'
# The containers and reference databases folders a config leaves empty: the group's where the
# account reads them (SHARED_FOLDER_DEFAULTS), else these folders in the working folder.
TOOL_FOLDERS = {'sif_path': 'sif', 'db_root': 'reference-databases/db'}
# Bookkeeping folder inside it: the store manifest and the copy under way.
STATE_DIR = '.margie'

# ---- Stores ----
# kind 'file' (plus companions) or 'dir' (whole folder); config: config.yaml keys.
STORES: list[dict] = [
    {
        'id': 'job_db',
        'label': 'MARGIE database',
        'note': 'The main MARGIE database (SQLite): every run’s results and cached tool outputs; the job history sits beside it.',
        'kind': 'file',
        'base_rel': 'sqlite/margie-thesis-22-prokaryotes-base.db',
        'depot_sub': 'sqlite',
        'sub': 'sqlite',
        'name': 'margie-thesis-22-prokaryotes-base',
        # A copy set up any other way than from the base (new, the starter, the user's own): <user>-margie-vN.db.
        'short': 'margie',
        'ext': '.db',
        'companions': [],
        'config': {'main_database': None},
    },
    {
        'id': 'occ',
        'label': 'Operon reference',
        'note': 'The cross-genome operon (OCC) reference scoring reads and adds each genome to.',
        'kind': 'file',
        'base_rel': 'operon-database/occ_reference.pkl',
        'depot_sub': 'operon-database',
        'sub': 'operon-database',
        'name': 'occ_reference',
        'short': 'operon-reference',
        'ext': '.pkl',
        # Written beside the reference by update-occ-reference-depot.py.
        'companions': ['.members.tsv', '.genome_stats.tsv'],
        'config': {'margie_sb.operon_database.occ_reference_pkl': None},
    },
    {
        'id': 'fingerprint',
        'label': 'Fingerprint databases',
        'note': 'The gene fingerprint database and the four operon fingerprint databases beside it.',
        'kind': 'dir',
        'base_rel': 'fingerprint-database',
        # Only the database files, not the backups and locks beside them.
        'base_files': [
            'fingerprint-database.tsv',
            'fingerprint-database-metadata.json',
            'operon-fingerprint-database-evidence-ordered.tsv',
            'operon-fingerprint-database-evidence-composition.tsv',
            'operon-fingerprint-database-label-ordered.tsv',
            'operon-fingerprint-database-label-composition.tsv',
            'operon-fingerprint-database-evidence_ordered-metadata.json',
            'operon-fingerprint-database-evidence_composition-metadata.json',
            'operon-fingerprint-database-label_ordered-metadata.json',
            'operon-fingerprint-database-label_composition-metadata.json',
        ],
        'depot_sub': 'fingerprint-database',
        'sub': 'fingerprint-database',
        'name': 'fingerprint-database',
        'config': {
            'margie_sb.fingerprint_database.path': 'fingerprint-database.tsv',
            # The report figures read the label-ordered operon fingerprints.
            'margie_sb.report_figures.operon_db': 'operon-fingerprint-database-label-ordered.tsv',
        },
    },
    {
        'id': 'genome_pool',
        'label': 'Genome pool',
        'note': 'Genomes ANI and AAI compare against; every annotated genome joins it.',
        'kind': 'dir',
        'base_rel': 'genome-pool',
        # Only the genome folders, not the backups beside them.
        'base_files': ['fna', 'faa'],
        'depot_sub': 'genome-pool',
        'sub': 'genome-pool',
        'name': 'genome-pool',
        'config': {'margie_sb.genome_pool.path': ''},
    },
]

# Run output folders on scratch; never backed up.
OUTPUT_DIRS = {
    'margie_sb.scoring_results_historical.path': 'scoring-archive',
    'margie_sb.final_tables_depot.path': 'final-tables',
    'margie_sb.sqlite_pipeline_snapshot.path': 'sqlite/snapshots',
}

STORE_BY_ID = {s['id']: s for s in STORES}


def backup_root(cfg: dict | None) -> str:
    """Returns margie_sb.backup_root if set, else the base folder on depot."""
    chosen = _cfg_get(cfg or {}, 'margie_sb.backup_root')
    return chosen.strip().rstrip('/') if isinstance(chosen, str) and chosen.strip() else generated(cfg)


def backup_dir(store: dict, cfg: dict | None) -> str:
    """Returns the store's backup folder."""
    return f"{backup_root(cfg)}/{store['depot_sub']}"


class StoreError(Exception):
    """A request that cannot be done now; the message and HTTP status go to the page."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---- Remote helpers ----

def _run(conn, command: str, timeout: float = 60.0) -> tuple[int, str]:
    """Runs a shell command over SSH; returns (exit code, stdout + stderr)."""
    ssh = conn.connect()
    _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    # Read first: a command with over 2 MB to say waits for it to be read before it ends.
    out = stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')
    return stdout.channel.recv_exit_status(), out


def _cfg_get(cfg: dict, dotted: str):
    """Returns the value at a dotted config key, or None."""
    cur = cfg
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _cfg_set(cfg: dict, dotted: str, value) -> None:
    """Sets a dotted config key, creating intermediate dicts."""
    parts = dotted.split('.')
    cur = cfg
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _scratch(conn) -> str:
    """Returns /scratch/<cluster>/<user>. The cluster short name comes from the login node's domain
    (login01.mycluster.example.edu -> mycluster)."""
    code, out = _run(conn, 'printf "%s %s" "$(hostname -d 2>/dev/null | cut -d. -f1)" "$USER"')
    cluster, _, user = out.strip().partition(' ')
    if code != 0 or not cluster or not user:
        raise StoreError('Could not work out your scratch folder on the cluster. Set margie_sb.stores_root in Settings.')
    return f'/scratch/{cluster}/{user}'


def working_folder(conn, cfg: dict) -> str:
    """Returns margie_sb.working_folder if set, else /scratch/<cluster>/<user>/margie."""
    chosen = _cfg_get(cfg, WORKING_KEY)
    if isinstance(chosen, str) and chosen.strip():
        return chosen.strip().rstrip('/')
    return f'{_scratch(conn)}/{HOME_NAME}'


def scratch_root(conn, cfg: dict) -> str:
    """Returns margie_sb.stores_root if set (every finished setup saves it), else margie-databases
    in the working folder."""
    chosen = _cfg_get(cfg, 'margie_sb.stores_root')
    if isinstance(chosen, str) and chosen.strip():
        return chosen.strip().rstrip('/')
    return f'{working_folder(conn, cfg)}/{ROOT_NAME}'


def readable(conn, paths: list[str]) -> set[str]:
    """The folders among paths that the account can open and read."""
    q = shlex.quote
    if not paths:
        return set()
    _, out = _run(conn, '; '.join(f'[ -r {q(p)} ] && [ -x {q(p)} ] && echo {i}' for i, p in enumerate(paths)) + '; true')
    hits = {int(x) for x in out.split() if x.isdigit()}
    return {p for i, p in enumerate(paths) if i in hits}


def in_group(path: str) -> bool:
    """Whether path is the group's shared folder (DEPOT) or under it."""
    return bool(DEPOT) and (path == DEPOT or path.startswith(DEPOT + '/'))


def reads_group(conn) -> bool:
    """Whether the account can read the group's shared folder (a member of the group can)."""
    return bool(DEPOT) and DEPOT in readable(conn, [DEPOT])


def suggested_group(cfg: dict | None) -> str:
    """The group folder GROUP_PATTERN gives for the config's SLURM account; '' without either."""
    account = str(_cfg_get(cfg or {}, 'compute.cluster_default.account') or '').strip()
    if not GROUP_PATTERN or not account or not all(c.isalnum() or c in '._-' for c in account):
        return ''
    return GROUP_PATTERN.replace('{account}', account).rstrip('/')


def tool_folder(conn, name: str, working: str, seen: set[str] | None = None) -> str:
    """Where an empty containers (sif_path) or reference databases (db_root) setting points: the
    group's folder when the account reads it, else sif or reference-databases/db in the working folder."""
    group = SHARED_FOLDER_DEFAULTS.get(name, '')
    if group and group in (seen if seen is not None else readable(conn, [group])):
        return group
    return f'{working}/{TOOL_FOLDERS[name]}'


def fill_default_folders(conn, cfg: dict) -> bool:
    """Sets the folders a config leaves empty: the working folder to margie in <scratch>; the
    genomes and results folders to margie-input and margie-output in it; and the containers and
    reference databases to the group's where the account reads them, else sif and reference-databases/db in the
    working folder. The folders in the working folder are made (with the databases folder) so
    files can go straight in. A folder chosen in Settings is kept. Returns True when the config
    changed."""
    unset = lambda key: not str(_cfg_get(cfg, key) or '').strip()  # noqa: E731
    tools = [n for n in TOOL_FOLDERS if unset(f'margie_sb.{n}')]
    empty = [k for k in DEFAULT_FOLDERS if unset(k)]
    if not tools and not empty and not unset(WORKING_KEY):
        return False
    working = working_folder(conn, cfg)
    _cfg_set(cfg, WORKING_KEY, working)
    made = [f'{working}/{DEFAULT_FOLDERS[k]}' for k in empty]
    for k, path in zip(empty, made):
        _cfg_set(cfg, k, path)
    seen = readable(conn, [SHARED_FOLDER_DEFAULTS[n] for n in tools if SHARED_FOLDER_DEFAULTS.get(n)])
    for n in tools:
        path = tool_folder(conn, n, working, seen)
        _cfg_set(cfg, f'margie_sb.{n}', path)
        if path.startswith(f'{working}/'):
            made.append(path)
    made.append(scratch_root(conn, cfg))
    _run(conn, 'mkdir -p -- ' + ' '.join(shlex.quote(p) for p in made))
    return True


def fill_default_partition(conn, cfg: dict) -> bool:
    """Sets an empty SLURM partition setting to the cluster's default (default_partition), since a
    cluster that marks none may refuse a job without one. A partition chosen in Settings is
    never changed. Returns True when the config changed."""
    if str(_cfg_get(cfg, 'compute.cluster_default.partition') or '').strip():
        return False
    partition = default_partition(conn)
    if not partition:
        return False
    _cfg_set(cfg, 'compute.cluster_default.partition', partition)
    return True


# ---- Names ----

def short_stem(store: dict) -> str:
    """The name of a copy set up any other way than from the group's base (new, the starter, the
    user's own): margie, operon-reference, fingerprint-database, genome-pool."""
    return store.get('short') or store['name']


def _stems(store: dict) -> list[str]:
    """The names a copy of the store goes by: the base's (a copy of the group's base, and its
    backups) and the short one."""
    return list(dict.fromkeys([store['name'], short_stem(store)]))


def versioned(store: dict, user: str, version: int, stem: str | None = None) -> str:
    """Returns <user>-<name>-v<N><ext>, the name used on scratch and depot: the base's name, or
    stem (short_stem for a copy not made from the base)."""
    return f"{user}-{stem or store['name']}-v{version}{store.get('ext', '') if store['kind'] == 'file' else ''}"


def parse_versioned(store: dict, user: str, name: str) -> tuple[int, str] | None:
    """The version and name stem of a versioned name (either stem), or None."""
    ext = re.escape(store.get('ext', '')) if store['kind'] == 'file' else ''
    for stem in _stems(store):
        m = re.fullmatch(rf"{re.escape(user)}-{re.escape(stem)}-v(\d+){ext}", name)
        if m:
            return int(m.group(1)), stem
    return None


def _version_of(store: dict, user: str, name: str) -> int | None:
    """Parses the version from a versioned name, or None."""
    found = parse_versioned(store, user, name)
    return found[0] if found else None


def stem_of(entry: dict | None, store: dict) -> str:
    """The name stem a manifest entry records ({version, name}); an entry without one is the base's."""
    name = (entry or {}).get('name')
    return name if name in _stems(store) else store['name']


def _backups(conn, store: dict, user: str, cfg: dict | None = None) -> list[tuple[int, str]]:
    """Returns this user's backups of the store as (version, name stem), oldest first."""
    try:
        entries = ssh_sftp.list_remote_dir(backup_dir(store, cfg), connection=conn)
    except Exception:
        return []
    want = 'file' if store['kind'] == 'file' else 'directory'
    found = []
    for e in entries:
        if e.get('type') != want:
            continue
        p = parse_versioned(store, user, e.get('name') or '')
        if p is not None:
            found.append(p)
    return sorted(found)


# ---- State: stores.json holds working versions; op.* the current or last copy ----

def _state_path(root: str, name: str) -> str:
    return f'{root}/{STATE_DIR}/{name}'


def _read_text(conn, path: str) -> str:
    code, out = _run(conn, f'cat {shlex.quote(path)} 2>/dev/null')
    return out if code == 0 else ''


def read_manifest(conn, root: str) -> dict:
    try:
        data = json.loads(_read_text(conn, _state_path(root, 'stores.json')) or '{}')
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_manifest(conn, root: str, manifest: dict) -> None:
    ssh_sftp.write_remote_text_file(_state_path(root, 'stores.json'), json.dumps(manifest, indent=2) + '\n', connection=conn)


def working_path(store: dict, root: str, user: str, version: int, stem: str | None = None) -> str:
    return f"{root}/{store['sub']}/{versioned(store, user, version, stem)}"


def _probe(conn, root: str, user: str, cfg: dict | None = None) -> dict:
    """Collects the manifest, working copies, backups and copy status in one cluster round-trip
    (plus a small second one for the working copies)."""
    manifest_path = _state_path(root, 'stores.json')
    status_path = _state_path(root, 'op.status')
    log_path = _state_path(root, 'op.log')
    parts = [f'echo "@@manifest"; cat {shlex.quote(manifest_path)} 2>/dev/null',
             f'echo "@@status"; cat {shlex.quote(status_path)} 2>/dev/null',
             f'echo "@@log"; tail -c 16000 {shlex.quote(log_path)} 2>/dev/null | tr "\\r" "\\n"',
             'echo "@@host"; hostname',
             f'echo "@@squeue"; j=$(cat {shlex.quote(_state_path(root, "op.jobid"))} 2>/dev/null); '
             f'[ -n "$j" ] && {{ echo "job=$j"; squeue -h -j "$j" -o "%T|%r" 2>/dev/null; }}',
             f'echo "@@slurmout"; tail -n 20 {shlex.quote(_state_path(root, "op.slurm.out"))} 2>/dev/null',
             f'echo "@@logage"; echo $(( $(date +%s) - $(stat -c %Y {shlex.quote(log_path)} 2>/dev/null || echo 0) ))']
    for st in STORES:
        names = '|'.join(re.escape(n) for n in _stems(st))
        parts.append(f'echo "@@depot {st["id"]}"; ls -1p {shlex.quote(backup_dir(st, cfg))} 2>/dev/null | grep -E "^{user}-({names})-v"')
    # What is in the working folder, for copies put there by hand (own_copy).
    # Newest first, so a copy found by its extension is the newest one (own_copy).
    parts.append(f'echo "@@here"; ls -1pAt {shlex.quote(root)} 2>/dev/null')
    for sub in sorted({st['sub'] for st in STORES}):
        parts.append(f'echo "@@here {sub}"; ls -1pAt {shlex.quote(root + "/" + sub)} 2>/dev/null')
    code, out = _run(conn, '; '.join(parts), timeout=60)
    sections: dict[str, list[str]] = {}
    current = None
    for line in out.splitlines():
        if line.startswith('@@'):
            current = line[2:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    try:
        manifest = json.loads('\n'.join(sections.get('manifest', [])) or '{}')
    except json.JSONDecodeError:
        manifest = {}
    # Checks the working copies named by the manifest.
    wanted = {}
    for st in STORES:
        entry = (manifest.get(st['id']) or {}) if isinstance(manifest, dict) else {}
        v = entry.get('version')
        if v:
            wanted[st['id']] = (int(v), working_path(st, root, user, int(v), stem_of(entry, st)))
    present = set()
    if wanted:
        cmd = '; '.join(f'test -e {shlex.quote(p)} && echo {sid}' for sid, (_, p) in wanted.items())
        _, out2 = _run(conn, cmd)
        present = set(out2.split())
    backups = {}
    for st in STORES:
        names = [n.rstrip('/') for n in sections.get(f'depot {st["id"]}', [])]
        is_dir = st['kind'] == 'dir'
        vs = sorted(p for n in names
                    if (p := parse_versioned(st, user, n)) is not None
                    and any(x == n + '/' for x in sections.get(f'depot {st["id"]}', [])) == is_dir)
        backups[st['id']] = vs
    return {
        'manifest': manifest if isinstance(manifest, dict) else {},
        'wanted': wanted,
        'present': present,
        'backups': backups,
        'here': {sub: sections.get(f'here {sub}', []) for sub in {st['sub'] for st in STORES}} | {'': sections.get('here', [])},
        'op': _op_from(sections, root),
    }


# ---- Copies the user put in the working folder themselves ----

def own_copy(store: dict, user: str, root: str, top: list[str], inside: list[str]) -> dict | None:
    """Finds a copy of the store already in the working folder that MARGIE has no record of, from
    `ls -1pt` of the folder (top) and of the store's subfolder (inside), newest first: one under
    MARGIE's own name (<user>-<name>-vN, the newest), the base's own name at either level or else the
    newest file with the store's extension (.db, .pkl) in the subfolder and then at the top (a file
    store), or the base folder's files laid straight into the subfolder (a folder store, whose files
    the pipeline reads by name). A file under another user's MARGIE name is left alone. None when
    there is none."""
    sub = f"{root}/{store['sub']}"
    is_dir = store['kind'] == 'dir'
    # In the listing's order (newest first), each name once.
    listed = lambda names: list(dict.fromkeys((n.rstrip('/'), n.endswith('/')) for n in names if n.strip()))
    top, inside = listed(top), listed(inside)
    named = [(p[0], n, p[1]) for n, d in inside if d == is_dir and (p := parse_versioned(store, user, n)) is not None]
    if named:
        v, n, stem = max(named)
        return {'path': f'{sub}/{n}', 'how': 'named', 'version': v, 'stem': stem}
    base = posixpath.basename(store['base_rel'])
    if not is_dir:
        for where, names in ((sub, inside), (root, top)):
            if (base, False) in names:
                return {'path': f'{where}/{base}', 'how': 'base', 'version': 1}
        ext = store.get('ext', '')
        someone_elses = re.compile(rf".+-({'|'.join(re.escape(n) for n in _stems(store))})-v\d+{re.escape(ext)}")
        for where, names in ((sub, inside), (root, top)):
            for n, d in names:
                if not d and ext and n.endswith(ext) and n != ext and not n.startswith('.') and not someone_elses.fullmatch(n):
                    return {'path': f'{where}/{n}', 'how': 'ext', 'version': 1}
        return None
    need = store.get('base_files') or []
    if need and all(any(n == f for n, _ in inside) for f in need):
        return {'path': sub, 'how': 'flat', 'version': 1}
    return None


# A file changed this recently may still be being copied.
SETTLE_SECONDS = 120


def _check_own(conn, found: dict, bases: dict) -> None:
    """Marks each found copy ready, or says why not: a file still changing, or not the size of the
    group's copy it was made from. found: {store id: own_copy()}; bases: {store id: base path}."""
    files = {sid: f for sid, f in found.items() if STORE_BY_ID[sid]['kind'] == 'file'}
    for f in found.values():
        f['ready'], f['note'] = True, ''
    if not files:
        return
    q = shlex.quote
    cmd = ['date +%s']
    for sid, f in files.items():
        cmd.append(f'printf "%s " {sid}; stat -c "%s %Y" {q(f["path"])} 2>/dev/null || echo')
        cmd.append(f'printf "%s " {sid}.base; stat -c "%s" {q(bases.get(sid) or "/nonexistent")} 2>/dev/null || echo')
    _, out = _run(conn, '; '.join(cmd))
    lines = out.splitlines()
    now = int(lines[0]) if lines and lines[0].strip().isdigit() else 0
    seen = {k: v.split() for k, _, v in (l.partition(' ') for l in lines[1:])}
    for sid, f in files.items():
        size_age = seen.get(sid) or []
        base = seen.get(f'{sid}.base') or []
        if len(size_age) != 2:
            f['ready'], f['note'] = False, 'could not be read'
            continue
        size, mtime = int(size_age[0]), int(size_age[1])
        f['bytes'] = size
        if now and now - mtime < SETTLE_SECONDS:
            f['ready'], f['note'] = False, 'still changing (being copied?); look again in a few minutes'
        elif f['how'] == 'base' and base and int(base[0]) != size:
            f['ready'], f['note'] = False, (f'not the size of the group\'s copy ({_gb(size)} of {_gb(int(base[0]))}); '
                                            'still being copied?')


def _gb(n: int) -> str:
    for unit, size in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= size:
            return f'{n / size:.1f} {unit}'
    return f'{n} bytes'


def adopted_stem(store: dict, found: dict) -> str:
    """The name a found copy goes by once taken: its own (MARGIE's name), the base's (a file named
    as the group's base is a copy of it), else the short one."""
    if found['how'] == 'named':
        return found.get('stem') or store['name']
    return store['name'] if found['how'] == 'base' else short_stem(store)


def adopt(conn, store: dict, found: dict, root: str, user: str) -> int:
    """Takes a found copy as the store's working copy, where it is: renamed to MARGIE's name in the
    store's subfolder (companions too), or a base folder's files moved into one. Nothing is copied
    or overwritten. Returns its version."""
    if found['how'] == 'named':
        return found['version']
    dst = working_path(store, root, user, 1, adopted_stem(store, found))
    q = shlex.quote
    if found['how'] in ('base', 'ext'):
        src = found['path']
        # Never onto something already there (test ! -e first: mv onto a folder would move into it).
        steps = [f'mkdir -p {q(posixpath.dirname(dst))}', f'test ! -e {q(dst)}', f'mv -n -- {q(src)} {q(dst)}', f'test -e {q(dst)}']
        steps += [f'{{ ! test -e {q(src + c)} || {{ test ! -e {q(dst + c)} && mv -n -- {q(src + c)} {q(dst + c)}; }}; }}'
                  for c in store.get('companions', [])]
    else:
        names = ' '.join(q(f"{found['path']}/{n}") for n in store.get('base_files') or [])
        steps = [f'test ! -e {q(dst)}', f'mkdir {q(dst + ".partial")}', f'mv -n -- {names} {q(dst + ".partial")}/',
                 f'mv -- {q(dst + ".partial")} {q(dst)}']
    code, out = _run(conn, ' && '.join(steps))
    if code != 0:
        raise StoreError(f"Could not use your copy of {store['label']} ({found['path']}): {out.strip()}")
    return 1


def _op_from(sections: dict, root: str) -> dict:
    """Builds the current or last copy's state from its status file, SLURM state and log progress."""
    op: dict = {}
    for line in sections.get('status', []):
        k, _, v = line.partition('=')
        if k:
            op[k] = v
    if not op:
        return {}
    # Marks a running op failed if its script is gone (squeue, pid, or idle log).
    squeue = [l.strip() for l in sections.get('squeue', []) if l.strip()]
    job = next((l[4:] for l in squeue if l.startswith('job=')), '')
    slurm_line = next((l for l in squeue if not l.startswith('job=')), '')
    slurm_state, _, slurm_reason = slurm_line.partition('|')
    if job:
        op['job'] = job
        op['slurm_state'] = slurm_state
        # Pending reason (Resources, Priority, ...) shown beside the queued state.
        if slurm_state == 'PENDING' and slurm_reason and slurm_reason != 'None':
            op['slurm_reason'] = slurm_reason
    if op.get('state') == 'queued' and not job:
        # Queued with no SLURM job behind it: the submission was refused (as an older version left it).
        op['state'] = 'failed'
        op['message'] = op.get('message') or 'This copy has no SLURM job behind it; start it again.'
    if op.get('state') in ('queued', 'running') and job:
        # A SLURM job missing from squeue has ended.
        if not slurm_state:
            op['state'] = 'failed'
            op['message'] = op.get('message') or 'The copy job ended before it finished.'
            op['slurm_out'] = sections.get('slurmout', [])[-10:]
    elif op.get('state') == 'running':
        here = (sections.get('host') or [''])[0].strip()
        age = (sections.get('logage') or ['0'])[0].strip()
        if here and here == op.get('host') and op.get('pid', '').isdigit():
            op['_check_pid'] = op['pid']
        elif age.isdigit() and int(age) > 300:
            op['state'] = 'failed'
            op['message'] = op.get('message') or 'The copy stopped before it finished.'
    lines = [l.rstrip() for l in sections.get('log', []) if l.strip()]
    # rsync --info=progress2 prints "   1,234,567  42%  ..." for the file in hand.
    pct = 0.0
    for l in reversed(lines):
        m = re.search(r'\s(\d{1,3})%\s', f' {l} ')
        if m:
            pct = float(m.group(1))
            break
    total = float(op.get('total_bytes') or 0)
    done = float(op.get('done_bytes') or 0)
    item = float(op.get('item_bytes') or 0)
    if op.get('state') == 'done':
        percent = 100.0
    elif total > 0:
        percent = min(100.0, 100.0 * (done + item * pct / 100.0) / total)
    else:
        percent = pct
    op['percent'] = round(percent, 1)
    # Drops rsync progress lines from the log shown.
    op['log'] = [l for l in lines if not re.match(r'^\s*[\d,]+\s+\d{1,3}%', l)][-40:]
    return op


def _read_op(conn, root: str) -> dict:
    """Returns the current or last copy's state, with its pid checked."""
    op = _probe(conn, root, '__none__')['op']
    return _settle_pid(conn, op)


def _settle_pid(conn, op: dict) -> dict:
    """Marks the op failed if its pid (checked on its own login node) is gone."""
    pid = op.pop('_check_pid', None)
    if pid:
        code, _ = _run(conn, f'kill -0 {int(pid)} 2>/dev/null')
        if code != 0:
            op['state'] = 'failed'
            op['message'] = op.get('message') or 'The copy stopped before it finished.'
    return op


# ---- Copy script: runs the tab-separated plan, writes op.status/op.log ----
COPY_SCRIPT = r'''#!/bin/bash
set -u
dir="$1"; plan="$dir/op.plan"; status="$dir/op.status"; log="$dir/op.log"
total=$(awk -F'\t' '$1=="copy"||$1=="files"{s+=$5} END{print s+0}' "$plan")
done_bytes=0
say() { { printf 'state=%s\npid=%s\nhost=%s\nop=%s\nlabel=%s\ntotal_bytes=%s\ndone_bytes=%s\nitem_bytes=%s\nmessage=%s\n' \
          "$1" "$$" "$(hostname)" "$OP" "$2" "$total" "$done_bytes" "$3" "$4"; } > "$status.tmp" && mv "$status.tmp" "$status"; }
fail() { say failed "$1" 0 "$2"; echo "FAILED: $2" >> "$log"; exit 1; }
OP="$(head -n 1 "$dir/op.kind" 2>/dev/null)"
: > "$log"
say running "Starting" 0 ""
while IFS=$'\t' read -r kind a b c d e f; do
  case "$kind" in
    copy)
      label="$a"; src="$b"; dst="$c"; bytes="$d"
      say running "$label" "$bytes" ""
      echo "== $label: $src -> $dst" >> "$log"
      mkdir -p "$(dirname "$dst")" || fail "$label" "could not make $(dirname "$dst")"
      if [ -d "$src" ]; then
        rsync -a --info=progress2 --no-inc-recursive "$src/" "$dst.partial/" >> "$log" 2>&1 || fail "$label" "copy of $src failed"
      else
        rsync -a --info=progress2 "$src" "$dst.partial" >> "$log" 2>&1 || fail "$label" "copy of $src failed"
      fi
      mv -T "$dst.partial" "$dst" || fail "$label" "could not put $dst in place"
      done_bytes=$(( done_bytes + bytes ))
      ;;
    files)
      label="$a"; src="$b"; dst="$c"; bytes="$d"; names="$e"
      say running "$label" "$bytes" ""
      echo "== $label: $src/{$names} -> $dst" >> "$log"
      mkdir -p "$dst.partial" || fail "$label" "could not make $dst"
      list=(); IFS=',' read -r -a want <<< "$names"
      for n in "${want[@]}"; do [ -e "$src/$n" ] && list+=("$src/$n"); done
      if [ ${#list[@]} -gt 0 ]; then
        rsync -a --info=progress2 "${list[@]}" "$dst.partial/" >> "$log" 2>&1 || fail "$label" "copy from $src failed"
      fi
      mv -T "$dst.partial" "$dst" || fail "$label" "could not put $dst in place"
      done_bytes=$(( done_bytes + bytes ))
      ;;
    move)
      echo "== rename $a -> $b" >> "$log"
      mv -T "$a" "$b" || fail "Renaming" "could not rename $a"
      ;;
    mkdir)
      mkdir -p "$a" || fail "Folders" "could not make $a"
      ;;
    new)
      label="$a"; dst="$b"
      say running "$label" 0 ""
      echo "== $label: $dst" >> "$log"
      mkdir -p "$(dirname "$dst")" && : > "$dst" || fail "$label" "could not create $dst"
      ;;
    occ)
      # An empty operon reference, written by the cluster's own scoring code.
      label="$a"; dst="$b"; py="$HOME/$c"; code="$HOME/$d"
      say running "$label" 0 ""
      echo "== $label: $dst" >> "$log"
      mkdir -p "$(dirname "$dst")" || fail "$label" "could not make $(dirname "$dst")"
      ( cd "$code" && "$py" -c 'import sys, c3_occ; r = c3_occ.new_reference(); c3_occ.finalize_reference(r); c3_occ.save_reference(r, sys.argv[1])' "$dst" ) >> "$log" 2>&1 \
        || fail "$label" "could not make an empty operon reference"
      ;;
    link)
      [ -e "$b" ] || [ -L "$b" ] || ln -s "$a" "$b" || fail "Links" "could not link $b"
      ;;
    pull)
      label="$a"; url="$b"; dst="$c"
      say running "$label" 0 ""
      echo "== $label: $url -> $dst" >> "$log"
      app=$(command -v apptainer || command -v singularity) || fail "$label" "apptainer is not installed here"
      mkdir -p "$(dirname "$dst")" || fail "$label" "could not make $(dirname "$dst")"
      # Its cache and scratch space beside this script, not in the small home folder.
      export APPTAINER_CACHEDIR="$dir/apptainer-cache" APPTAINER_TMPDIR="$dir/apptainer-tmp"
      mkdir -p "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR"
      "$app" pull --force "$dst.partial" "$url" >> "$log" 2>&1 || fail "$label" "could not pull $url"
      mv -T "$dst.partial" "$dst" || fail "$label" "could not put $dst in place"
      ;;
    repo)
      repo_url="$a"
      ;;
    env)
      # margie-build's settings for an account outside the group: these three only.
      case "$a" in MARGIE_RECORDS_DIR|MARGIE_OPERATOR|MARGIE_SHARED_GROUP) ;; *) fail "$a" "margie-build takes no setting $a" ;; esac
      v="$b"
      [ "$v" = "@user" ] && v="$USER"
      [ "$v" = "@group" ] && v="$(id -gn)"
      export "$a=$v"
      ;;
    build)
      label="$a"; mode="$b"; tool="$c"; sifdir="$d"; dbdir="$e"; statement="$f"
      say running "$label" 0 ""
      echo "== $label" >> "$log"
      # margie-build's own folder on the cluster (the lab's, or the user's clone),
      # used where it is: build.sh writes only to --sif-dir, --db-dir, its
      # --work-dir and the licence records. --local: this is already a SLURM
      # job, and build.sh must not submit another. CONFIG_FILE is an empty file of our own: whoever's
      # .build-config.sh is in that folder must not decide where this user's
      # builds go (build.sh looks for one unless CONFIG_FILE names a file).
      repo="${repo_url:-}"
      [ -f "$repo/build.sh" ] || fail "$label" "margie-build is not at ${repo:-any folder}; set it up on Install"
      : > "$dir/build-config.sh"
      accept=()
      [ -n "$statement" ] && accept=(--accept-"$tool"-licence --licence-statement "$statement")
      mkdir -p "$sifdir" "$dbdir" "$dir/apptainer-cache" "$dir/apptainer-tmp" || fail "$label" "could not make $sifdir or $dbdir"
      ( cd "$repo" && CONFIG_FILE="$dir/build-config.sh" APPTAINER_CACHEDIR="$dir/apptainer-cache" APPTAINER_TMPDIR="$dir/apptainer-tmp" \
          THREADS="${SLURM_CPUS_PER_TASK:-4}" ./build.sh --"$mode" "$tool" --local --work-dir "$dir/build-work" --sif-dir "$sifdir" --db-dir "$dbdir" \
          --audit-log "$dir/licence-acceptances.tsv" --no-color --quiet-notice ${accept[@]+"${accept[@]}"} ) >> "$log" 2>&1 \
        || fail "$label" "margie-build could not build $tool (the log above says why)"
      ;;
  esac
done < "$plan"
say done "Finished" 0 ""
echo "== finished" >> "$log"
'''


def _copy_cpus(cfg: dict | None) -> int:
    """Returns the copy job's cores: margie_sb.stores_copy_cpus, default 4, capped at 16 (the lab's limit)."""
    try:
        n = int(_cfg_get(cfg or {}, 'margie_sb.stores_copy_cpus') or 4)
    except (TypeError, ValueError):
        n = 4
    return max(1, min(16, n))


def _start(conn, root: str, kind: str, plan: list[list], after: dict, cfg: dict | None = None,
           walltime: str = '12:00:00', mem: str = '4G') -> None:
    """Writes the plan and starts the copy script: via sbatch when an account is set, else detached on the login node."""
    state = f'{root}/{STATE_DIR}'
    code, out = _run(conn, f'mkdir -p {shlex.quote(state)} && chmod 700 {shlex.quote(state)}')
    if code != 0:
        raise StoreError(f'Could not make {state}: {out.strip()}')
    ssh_sftp.write_remote_text_file(f'{state}/op.sh', COPY_SCRIPT, connection=conn)
    ssh_sftp.write_remote_text_file(
        f'{state}/op.plan', ''.join('\t'.join(str(x) for x in step) + '\n' for step in plan), connection=conn)
    ssh_sftp.write_remote_text_file(f'{state}/op.kind', kind + '\n', connection=conn)
    # Recorded by apply_finished once the copy is done.
    ssh_sftp.write_remote_text_file(f'{state}/op.after.json', json.dumps(after) + '\n', connection=conn)
    _run(conn, f'cd {shlex.quote(state)} && rm -f op.status op.log op.jobid op.slurm.out')
    account = str(_cfg_get(cfg or {}, 'compute.cluster_default.account') or '').strip()
    partition = str(_cfg_get(cfg or {}, 'compute.cluster_default.partition') or '').strip() or default_partition(conn)
    q = shlex.quote
    if account:
        cmd = (f'cd {q(state)} && sbatch --parsable --job-name=margie-databases --account={q(account)} '
               + (f'--partition={q(partition)} ' if partition else '')
               + f'--time={q(walltime)} --ntasks=1 --cpus-per-task={_copy_cpus(cfg)} --mem={q(mem)} --output={q(state)}/op.slurm.out '
               + f'op.sh {q(state)}')
        code, out = _run(conn, cmd)
        job = out.strip().split(';')[0].split()[-1] if out.strip() else ''
        if code != 0 or not job.isdigit():
            said = ' '.join(out.split())[:300]
            # Said on the page, rather than a wait for a job that never was.
            ssh_sftp.write_remote_text_file(
                f'{state}/op.status', f'state=failed\nop={kind}\nlabel=SLURM would not take the copy job\n'
                f'message=SLURM would not take the copy job (account {account}, partition {partition or "none"}): {said}\n',
                connection=conn)
            raise StoreError(f'SLURM would not take the copy job (account {account}, partition {partition or "none"}): {said}')
        ssh_sftp.write_remote_text_file(f'{state}/op.jobid', job + '\n', connection=conn)
        # Shows the job as queued until it starts, unless the script has started and said running.
        _run(conn, f'cd {q(state)} && [ -e op.status ] || '
                   f'printf "state=queued\\nop=%s\\nlabel=Waiting for a SLURM slot\\n" {q(kind)} > op.status')
        return
    code, out = _run(conn, f'cd {q(state)} && setsid nohup bash op.sh {q(state)} '
                            f'> /dev/null 2>&1 < /dev/null & echo started')
    if 'started' not in out:
        raise StoreError(f'Could not start the copy: {out.strip()}')
    # Waits briefly for the status file so the op is never seen in no state.
    for _ in range(20):
        if _read_text(conn, f'{state}/op.status'):
            break
        time.sleep(0.25)


def default_partition(conn) -> str:
    """Returns the partition a job goes to when none is set: the cluster's default (sinfo marks it
    with *), else 'cpu' where there is one; '' when neither. Some clusters mark no default
    and refuse a job without a partition."""
    _, out = _run(conn, 'sinfo -h -o %P 2>/dev/null')
    names = [n.strip() for n in out.split() if n.strip()]
    marked = next((n.rstrip('*') for n in names if n.endswith('*')), '')
    return marked or ('cpu' if 'cpu' in names else '')


def _size(conn, paths: list[str]) -> int:
    """Returns the total byte size of paths via du."""
    if not paths:
        return 0
    code, out = _run(conn, 'du -sbc ' + ' '.join(shlex.quote(p) for p in paths) + ' 2>/dev/null | tail -1 | cut -f1',
                     timeout=300)
    try:
        return int(out.strip() or 0)
    except ValueError:
        return 0


# ---- Page requests ----

def _config_paths(store: dict, target: str) -> dict:
    """Returns the config values for a store whose working copy is at target."""
    return {key: (posixpath.join(target, inner) if inner else target) if store['kind'] == 'dir' else target
            for key, inner in store['config'].items()}


def default_paths(root: str, user: str, short: bool = False) -> dict:
    """The settings of the databases folder as a first setup in root makes them: each store's first
    working copy (under the base's names, or the short ones for a setup not made from the base),
    and the run archives (OUTPUT_DIRS), for Settings to show while unset."""
    out: dict = {}
    for st in STORES:
        out.update(_config_paths(st, working_path(st, root, user, 1, short_stem(st) if short else None)))
    out.update({key: f'{root}/{sub}' for key, sub in OUTPUT_DIRS.items()})
    return out


def database_folders(root: str) -> list[str]:
    """The folders in the databases folder that a first setup fills (each store's and the archives')."""
    return sorted({f"{root}/{st['sub']}" for st in STORES} | {f'{root}/{sub}' for sub in OUTPUT_DIRS.values()})


def status(conn, cfg: dict, user: str) -> dict:
    """Returns each store's working version, latest backup and the copy under way."""
    root = scratch_root(conn, cfg)
    probe = _probe(conn, root, user, cfg)
    op = _settle_pid(conn, probe['op'])
    stores = []
    ready = True
    bases = {s['id']: resolve_base(conn, s, cfg) for s in STORES}
    found = {s['id']: f for s in STORES if s['id'] not in probe['present']
             and (f := own_copy(s, user, root, probe['here'][''], probe['here'].get(s['sub'], [])))}
    _check_own(conn, found, bases)
    for s in STORES:
        v, path = probe['wanted'].get(s['id'], (None, ''))
        present = s['id'] in probe['present']
        ready = ready and present
        backups = probe['backups'].get(s['id'], [])
        entry = probe['manifest'].get(s['id']) or {}
        stores.append({
            'id': s['id'],
            'label': s['label'],
            'note': s['note'],
            'version': v if present else None,
            'path': path if present else '',
            # What a run reads now: the store's setting (point_config keeps it on the working copy).
            'in_use': str(_cfg_get(cfg, next(iter(s['config']))) or ''),
            # A copy of it in the working folder that the next setup uses instead of copying.
            'found': found.get(s['id']),
            'base': bases[s['id']],
            'backup': ({'version': backups[-1][0],
                        'path': posixpath.join(backup_dir(s, cfg), versioned(s, user, *backups[-1]))}
                       if backups else None),
            # The name its working copy goes by: the base's, or the short one.
            'stem': stem_of(entry, s),
            'backups': len(backups),
        })
    return {'root': root, 'user': user, 'ready': ready, 'stores': stores, 'op': op or None}


def progress(conn, cfg: dict) -> dict | None:
    """Returns only the copy under way, for the progress bar's polling."""
    root = scratch_root(conn, cfg)
    return _read_op(conn, root) or None


def run_here(conn, cfg: dict) -> dict | None:
    """Cancels a queued SLURM copy job and runs the same script detached on the login node."""
    root = scratch_root(conn, cfg)
    op = _read_op(conn, root)
    if not op or op.get('state') != 'queued' or not op.get('job'):
        raise StoreError('There is no copy waiting in the queue.', 409)
    if op.get('slurm_state') != 'PENDING':
        raise StoreError('The copy has already started on a compute node.', 409)
    state = f'{root}/{STATE_DIR}'
    q = shlex.quote
    code, out = _run(conn, f'scancel {q(op["job"])} && cd {q(state)} && rm -f op.jobid op.slurm.out op.status '
                            f'&& (setsid nohup bash op.sh {q(state)} > /dev/null 2>&1 < /dev/null &) && echo started')
    if 'started' not in out:
        raise StoreError(f'Could not start the copy here: {out.strip()}')
    for _ in range(20):
        if _read_text(conn, f'{state}/op.status'):
            break
        time.sleep(0.25)
    return _read_op(conn, root) or None


def stop(conn, cfg: dict) -> dict | None:
    """Stops the copy under way, queued or running: its SLURM job cancelled, or its script (and the
    rsync it runs) ended on the login node it runs on, and waited for, so it cannot write its state
    after this. Only the half-copied items (<destination>.partial) are removed: what it finished
    stays, nothing is applied to the settings, and starting it again begins cleanly."""
    root = scratch_root(conn, cfg)
    op = _read_op(conn, root)
    if not _busy(op):
        raise StoreError('There is no copy under way to stop.', 409)
    state = f'{root}/{STATE_DIR}'
    q = shlex.quote
    if op.get('job'):
        job = q(op['job'])
        _run(conn, f'scancel {job}; for i in $(seq 1 30); do squeue -h -j {job} 2>/dev/null | grep -q . || exit 0; sleep 1; done',
             timeout=60)
    elif str(op.get('pid', '')).isdigit():
        pid = int(op['pid'])
        # The script runs in its own process group (setsid): ending the group ends its rsync too.
        kill = (f'kill -TERM -- -{pid} 2>/dev/null || kill -TERM {pid} 2>/dev/null; '
                f'for i in $(seq 1 20); do kill -0 {pid} 2>/dev/null || exit 0; sleep 0.5; done; '
                f'kill -KILL -- -{pid} 2>/dev/null; true')
        host = op.get('host') or ''
        _run(conn, f'if [ -z {q(host)} ] || [ "$(hostname)" = {q(host)} ]; then {kill}; '
                   f'else ssh -o BatchMode=yes -o ConnectTimeout=10 {q(host)} {q(kill)}; fi', timeout=60)
    # The plan's destinations are its 4th column (copy, files, pull); their .partial is what was in hand.
    _run(conn, f"cd {q(state)} && awk -F'\\t' '$1==\"copy\"||$1==\"files\"||$1==\"pull\"{{print $4}}' op.plan "
               f'| while IFS= read -r d; do [ -n "$d" ] && rm -rf -- "$d.partial"; done; rm -f op.after.json op.jobid; '
               f'echo "== stopped" >> op.log')
    ssh_sftp.write_remote_text_file(
        f'{state}/op.status',
        f"state=stopped\nop={op.get('op', '')}\nlabel=Stopped\nmessage=Stopped. What was copied stays; start it again whenever you like.\n",
        connection=conn)
    return _read_op(conn, root) or None


def _busy(op: dict | None) -> bool:
    """Returns True while a copy is queued or running."""
    return bool(op) and op.get('state') in ('queued', 'running')


def start_setup(conn, cfg: dict, user: str, fresh: bool = False) -> dict:
    """Copies every store missing on scratch from the user's newest backup, or else the base.

    fresh: every store starts empty instead, as the next version beside any it has (nothing is
    overwritten): a new lab's own databases, not the group's base copies or the shipped starter."""
    st = status(conn, cfg, user)
    if _busy(st['op']):
        raise StoreError('A copy is already under way.', 409)
    root = st['root']
    plan: list[list] = [['mkdir', f'{root}/{sub}'] for sub in OUTPUT_DIRS.values()]
    after: dict = {'kind': 'setup', 'versions': {}, 'names': {}}
    state = f'{root}/{STATE_DIR}'
    # Copies already in the working folder are used where they are.
    own = {s['id']: info['found'] for s, info in zip(STORES, st['stores'])
           if not fresh and not info['version'] and (info.get('found') or {}).get('ready')}
    if own:
        _run(conn, f'mkdir -p {shlex.quote(state)} && chmod 700 {shlex.quote(state)}')
        manifest = read_manifest(conn, root)
        for sid, found in own.items():
            manifest[sid] = {'version': adopt(conn, STORE_BY_ID[sid], found, root, user),
                             'name': adopted_stem(STORE_BY_ID[sid], found)}
        _write_manifest(conn, root, manifest)
    for s, info in zip(STORES, st['stores']):
        if s['id'] in own:
            continue
        if fresh:
            version = (info['version'] or 0) + 1
            dst = working_path(s, root, user, version, short_stem(s))
            _plan_fresh(plan, s, dst)
            after['versions'][s['id']] = version
            after['names'][s['id']] = short_stem(s)
            continue
        if info['version']:
            continue
        backups = _backups(conn, s, user, cfg)
        if backups:
            last, stem = backups[-1]
            src = posixpath.join(backup_dir(s, cfg), versioned(s, user, last, stem))
            version = last + 1
            label = f"{s['label']} (from your backup v{last})"
        else:
            # A source chosen in Settings (margie_sb.stores.base.<id>) wins over the group folder;
            # with neither, the store starts from MARGIE's own defaults (below).
            src = resolve_base(conn, s, cfg)
            version = 1
            label = s['label']
            # A copy of the group's base keeps the base's name; any other (new, or from a source of
            # the user's own) gets the short one.
            stem = s['name'] if src and in_group(src) else short_stem(s)
        dst = working_path(s, root, user, version, stem)
        after['names'][s['id']] = stem
        if not src:
            # No group folder and no chosen source: a fresh start.
            if s['id'] == 'occ':
                _, home = _run(conn, 'printf %s "$HOME"')
                starter = f'{home.strip()}/{STARTER_OCC}'
                code, _ = _run(conn, f'test -f {shlex.quote(starter)}')
                if code != 0:
                    raise StoreError('The starter operon reference is missing from the backend checkout on the cluster '
                                     f'({starter}); connect again so it is updated, or choose a source in Settings.', 409)
                plan.append(['copy', f"{s['label']} (MARGIE's starter, 29 genomes)", starter, dst, _size(conn, [starter])])
            elif s['kind'] == 'file':
                plan.append(['new', f"{s['label']} (new, empty)", dst])
            else:
                plan.append(['mkdir', dst])
                for sub in (s.get('base_files') or []) if s['id'] == 'genome_pool' else []:
                    plan.append(['mkdir', f'{dst}/{sub}'])
            after['versions'][s['id']] = version
            continue
        if s['kind'] == 'file':
            plan.append(['copy', label, src, dst, _size(conn, [src])])
            for c in s['companions']:
                code, _ = _run(conn, f'test -e {shlex.quote(src + c)}')
                if code == 0:
                    plan.append(['copy', f"{s['label']} ({c.lstrip('.')})", src + c, dst + c, _size(conn, [src + c])])
        elif s.get('base_files') and not backups:
            files = [posixpath.join(src, f) for f in s['base_files']]
            plan.append(['files', label, src, dst, _size(conn, files), ','.join(s['base_files'])])
        else:
            plan.append(['copy', label, src, dst, _size(conn, [src])])
        after['versions'][s['id']] = version
    if all(step[0] == 'mkdir' for step in plan):
        # Nothing to copy: the folders are made here, and the setup is done (apply_finished points the config).
        _run(conn, 'mkdir -p -- ' + ' '.join(shlex.quote(step[1]) for step in plan) + f' {shlex.quote(state)} '
                   f'&& rm -f {shlex.quote(state)}/op.after.json {shlex.quote(state)}/op.jobid')
        ssh_sftp.write_remote_text_file(f'{state}/op.status', 'state=done\nop=setup\nlabel=Finished\n', connection=conn)
        ssh_sftp.write_remote_text_file(f'{state}/op.log', '== your own copies are used where they are\n== finished\n', connection=conn)
        return status(conn, cfg, user)
    _start(conn, root, 'setup', plan, after, cfg)
    return status(conn, cfg, user)


# The scoring code on the cluster, which makes an empty operon reference (c3_occ.new_reference).
SCORING_DIR = 'bioinformatics-tools/bioinformatics_tools/workflow_tools/scoring'
CLUSTER_PYTHON = 'bioinformatics-tools/.venv/bin/python'


def _plan_fresh(plan: list[list], store: dict, dst: str) -> None:
    """Adds the steps that make one store empty at dst: a new SQLite file, an empty operon
    reference, or an empty folder (with the genome pool's subfolders)."""
    if store['id'] == 'occ':
        plan.append(['occ', f"{store['label']} (new, empty)", dst, CLUSTER_PYTHON, SCORING_DIR])
    elif store['kind'] == 'file':
        plan.append(['new', f"{store['label']} (new, empty)", dst])
    else:
        plan.append(['mkdir', dst])
        for sub in (store.get('base_files') or []) if store['id'] == 'genome_pool' else []:
            plan.append(['mkdir', f'{dst}/{sub}'])


_UNITS = {'B': 1, 'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4, 'PB': 1024 ** 5,
          'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4, 'P': 1024 ** 5}


def _bytes(text: str) -> int | None:
    """Parses a size such as '1.5TB' or '20G' into bytes."""
    m = re.fullmatch(r'([\d.]+)\s*([KMGTP]?B?)', text.strip(), re.I)
    return int(float(m.group(1)) * _UNITS.get(m.group(2).upper() or 'B', 1)) if m else None


def depot_free(conn, where: str = DEPOT) -> int | None:
    """Returns the free bytes on depot: the smaller of the group's quota headroom (myquota) and df."""
    group = where.split('/')[2] if where.startswith('/depot/') and len(where.split('/')) > 2 else ''
    # Uses the nearest existing folder; the backup folder may not exist yet.
    code, out = _run(conn, f'myquota 2>/dev/null; echo "@@df"; d={shlex.quote(where)}; '
                           f'while [ ! -e "$d" ] && [ "$d" != / ]; do d=$(dirname "$d"); done; '
                           f'df -B1 --output=avail "$d" 2>/dev/null | tail -1')
    quota_free = None
    head, _, df = out.partition('@@df')
    for line in head.splitlines():
        cols = line.split()
        if group and len(cols) >= 4 and cols[0] == 'depot' and cols[1] == group:
            used, limit = _bytes(cols[2]), _bytes(cols[3])
            if used is not None and limit is not None:
                quota_free = max(0, limit - used)
    try:
        fs_free = int(df.strip())
    except ValueError:
        fs_free = None
    known = [x for x in (quota_free, fs_free) if x is not None]
    return min(known) if known else None


def backup_check(conn, cfg: dict, user: str, store_id: str) -> dict:
    """Returns a backup's size, depot's free space and whether it fits."""
    s = STORE_BY_ID.get(store_id)
    if not s:
        raise StoreError('No such database.', 404)
    st = status(conn, cfg, user)
    info = next(i for i in st['stores'] if i['id'] == store_id)
    if not info['version']:
        raise StoreError(f"{s['label']} is not set up on scratch yet.", 409)
    src = info['path']
    paths = [src] + [src + c for c in (s.get('companions') or [])]
    size = _size(conn, paths)
    free = depot_free(conn, backup_root(cfg))
    # Keeps 5 GB free on the shared depot.
    margin = 5 * 1024 ** 3
    fits = free is None or free - margin >= size
    return {
        'id': store_id,
        'label': s['label'],
        'version': info['version'],
        'size': size,
        'free': free,
        'fits': fits,
        'target': posixpath.join(backup_dir(s, cfg), versioned(s, user, info['version'], info['stem'])),
    }


def start_backup(conn, cfg: dict, user: str, store_id: str) -> dict:
    """Copies the working vN to depot as <user>-<name>-vN, then renames the working copy to vN+1."""
    s = STORE_BY_ID.get(store_id)
    if not s:
        raise StoreError('No such database.', 404)
    st = status(conn, cfg, user)
    if _busy(st['op']):
        raise StoreError('A copy is already under way.', 409)
    if not backup_root(cfg):
        raise StoreError('No backup folder: set margie_sb.backup_root in Settings.', 409)
    check = backup_check(conn, cfg, user, store_id)
    if not check['fits']:
        gb = lambda n: f'{n / 1024 ** 3:.1f} GB'
        raise StoreError(f"Depot has {gb(check['free'])} left and this backup needs {gb(check['size'])} "
                         '(with 5 GB kept free): it would not fit.', 409)
    info = next(i for i in st['stores'] if i['id'] == store_id)
    v = info['version']
    if not v:
        raise StoreError(f"{s['label']} is not set up on scratch yet.", 409)
    root = st['root']
    stem = info['stem']
    src = working_path(s, root, user, v, stem)
    dst = posixpath.join(backup_dir(s, cfg), versioned(s, user, v, stem))
    code, _ = _run(conn, f'test -e {shlex.quote(dst)}')
    if code == 0:
        raise StoreError(f'{dst} already exists; nothing is overwritten.', 409)
    nxt = working_path(s, root, user, v + 1, stem)
    plan: list[list] = [['copy', f"{s['label']} v{v} to depot", src, dst, _size(conn, [src])]]
    companions = s.get('companions', []) if s['kind'] == 'file' else []
    for c in companions:
        code, _ = _run(conn, f'test -e {shlex.quote(src + c)}')
        if code == 0:
            plan.append(['copy', f"{s['label']} ({c.lstrip('.')})", src + c, dst + c, _size(conn, [src + c])])
    # The rename runs only after the backup copy succeeds.
    plan.append(['move', src, nxt])
    for c in companions:
        code, _ = _run(conn, f'test -e {shlex.quote(src + c)}')
        if code == 0:
            plan.append(['move', src + c, nxt + c])
    _start(conn, root, f'backup:{store_id}', plan, {'kind': 'backup', 'versions': {store_id: v + 1}, 'names': {store_id: stem}}, cfg)
    return status(conn, cfg, user)


def apply_finished(conn, cfg: dict, user: str) -> bool:
    """Records a finished copy's new versions and config changes; idempotent.
    Returns True when the config changed (the caller saves it)."""
    root = scratch_root(conn, cfg)
    op = _read_op(conn, root)
    if op.get('state') != 'done':
        return False
    state = f'{root}/{STATE_DIR}'
    after_text = _read_text(conn, f'{state}/op.after.json')
    changed = False
    if after_text:
        try:
            after = json.loads(after_text)
        except json.JSONDecodeError:
            after = {}
        manifest = read_manifest(conn, root)
        names = after.get('names') or {}
        for sid, version in (after.get('versions') or {}).items():
            entry = {'version': int(version)}
            name = names.get(sid) or (manifest.get(sid) or {}).get('name')
            if name:
                entry['name'] = name
            manifest[sid] = entry
        _write_manifest(conn, root, manifest)
        # Config keys set by a tool-assets copy.
        for key, value in (after.get('config') or {}).items():
            if _cfg_get(cfg, key) != value:
                _cfg_set(cfg, key, value)
                changed = True
        _run(conn, f'mv -f {shlex.quote(state)}/op.after.json {shlex.quote(state)}/op.applied.json')
    if op.get('op') == 'assets':
        # A tool-assets copy leaves the store settings alone.
        return changed
    return point_config(conn, cfg, user, root) or changed


def point_config(conn, cfg: dict, user: str, root: str | None = None) -> bool:
    """Sets every store's and output folder's config key to its path in the working folder.

    A run reads and writes everything in the working folder, so a key still pointing somewhere
    else (an earlier working folder, say) is brought here too; to keep the databases elsewhere,
    that folder is chosen as the working folder instead."""
    root = root or scratch_root(conn, cfg)
    manifest = read_manifest(conn, root)
    changed = False
    wanted: dict = {}
    for s in STORES:
        entry = manifest.get(s['id']) or {}
        v = entry.get('version')
        if v:
            wanted.update(_config_paths(s, working_path(s, root, user, v, stem_of(entry, s))))
    for key, sub in OUTPUT_DIRS.items():
        wanted[key] = f'{root}/{sub}'
    # Cached so later requests skip the cluster lookup.
    wanted['margie_sb.stores_root'] = root
    for key, value in wanted.items():
        if _cfg_get(cfg, key) != value:
            _cfg_set(cfg, key, value)
            changed = True
    return changed


def is_ready(conn, cfg: dict, user: str) -> bool:
    """Returns True when every store has a working copy on scratch."""
    return status(conn, cfg, user)['ready']
