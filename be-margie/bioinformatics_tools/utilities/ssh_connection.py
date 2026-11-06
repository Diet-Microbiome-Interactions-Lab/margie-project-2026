"""
Centralized SSH connection configuration.

Provides a single place to manage host, username, and connection setup
instead of hardcoding paramiko boilerplate in every function.

All SSH/SFTP operations are API-layer only. The CLI runs directly on the
cluster and has no need to establish outbound SSH connections.

API usage:
    Call make_user_connection(host, username, private_key_str), which reads
    the user's cluster credentials from the database record, loads the
    decrypted private key into memory (never written to disk), and returns
    a ready SSHConnection.
"""
import io
import logging
import os
import shlex
import threading
import time

import paramiko

LOGGER = logging.getLogger(__name__)

# The repository each cluster account runs MARGIE from, so the API and the workflow share one
# codebase: cloned into ~/margie-project-2026, its backend (be-margie/) linked as
# ~/bioinformatics-tools, where every command the API sends looks for it.
_DANE_WF_REPO_URL = os.getenv('BSP_MARGIE_REPO_URL', 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026.git')
_CLONE_DIR = 'margie-project-2026'
_BACKEND_DIR = 'be-margie'
# Branch the clones track (BSP_MARGIE_SB_REF).
_MARGIE_SB_REF = os.getenv('BSP_MARGIE_SB_REF', 'main')

# ---- What a user's shell start-up prints never reaches MARGIE ----
# sshd runs every command through the user's own shell, which first reads their start-up files
# (~/.bashrc): one that prints, or fails ("... not activated"), would add lines to what MARGIE
# reads back (a job id, a path, JSON). Each command therefore prints this line first, on its
# output and on its errors, and everything before it is dropped.
OUTPUT_MARK = '__margie_command_output__'


def marked(command: str) -> str:
    """The command, printing OUTPUT_MARK on stdout and stderr before it runs."""
    return f"printf '%s\\n' {OUTPUT_MARK}; printf '%s\\n' {OUTPUT_MARK} >&2; {command}"


class AfterMark:
    """A command's stdout or stderr from OUTPUT_MARK on. Lines before it (the user's shell
    start-up) are dropped; with no mark at all (the shell never ran the command), nothing is,
    since those lines say why. read() gives bytes and readline() text, as paramiko's files do."""

    def __init__(self, f):
        self._f = f
        self.channel = f.channel
        self._held: list = []
        self._looked = False

    def _look(self) -> None:
        if self._looked:
            return
        self._looked = True
        while True:
            line = self._f.readline()
            if not line:
                return
            text = line.decode(errors='replace') if isinstance(line, bytes) else line
            if text.rstrip('\r\n') == OUTPUT_MARK:
                self._held = []
                return
            self._held.append(text)

    def readline(self, *args):
        self._look()
        return self._held.pop(0) if self._held else self._f.readline(*args)

    def read(self, *args) -> bytes:
        self._look()
        head = ''.join(self._held).encode()
        self._held = []
        return head + self._f.read(*args)

    def readlines(self):
        return list(self)

    def __iter__(self):
        self._look()
        while self._held:
            yield self._held.pop(0)
        yield from self._f

    def __getattr__(self, name):
        return getattr(self._f, name)


def _clean_exec(exec_command):
    """Wraps a client's exec_command: the command marked, its stdout and stderr after the mark."""
    def run(command, *args, **kwargs):
        stdin, stdout, stderr = exec_command(marked(command), *args, **kwargs)
        return stdin, AfterMark(stdout), AfterMark(stderr)
    run.__wrapped__ = exec_command
    return run


# ---- Connection pool: clients reused per (host, username, key) ----
_POOL: dict = {}
_POOL_LOCK = threading.Lock()
# Keepalives detect dropped clients; a working one is kept indefinitely.
_KEEPALIVE_SECONDS = 30
# Connections per user, used in turn; one busy page can exceed sshd MaxSessions.
_POOL_SIZE = 4


def _alive(client) -> bool:
    try:
        transport = client.get_transport()
        return transport is not None and transport.is_active() and transport.is_authenticated()
    except Exception:
        return False


def _pool_key(host, username, pkey, key_filename):
    # Keyed by fingerprint so the key material is not held in the dict key.
    fp = None
    if pkey is not None:
        try:
            fp = pkey.get_fingerprint().hex()
        except Exception:
            fp = id(pkey)
    return (host, username, fp, key_filename)


def close_pooled_connections():
    """Closes every pooled client, for shutdown and tests."""
    with _POOL_LOCK:
        for entry in _POOL.values():
            for client in entry['slots']:
                if client is None:
                    continue
                try:
                    client.close()
                except Exception:
                    pass
        _POOL.clear()

def close_user_connections(host: str, username: str) -> None:
    """Closes and forgets one cluster account's pooled clients (its MARGIE account was deleted)."""
    with _POOL_LOCK:
        for key in [k for k in _POOL if k[0] == host and k[1] == username]:
            for client in _POOL.pop(key)['slots']:
                if client is None:
                    continue
                try:
                    client.close()
                except Exception:
                    pass


def remove_margie_files(conn: 'SSHConnection', timeout: float = 300.0) -> str:
    """Removes what the website keeps in the cluster account's home: the stored language-model keys
    (~/.config/bioinformatics-tools/secrets) and the copy of MARGIE (~/margie-project-2026, with the
    ~/bioinformatics-tools link to it). config.yaml, databases and results stay.

    Every MARGIE account on this cluster account, on the website or in the desktop app, runs from
    that copy, so nothing is removed while a MARGIE run of the cluster account is in SLURM or the
    desktop app's server is running (its ~/.local/share/bsp/api-endpoint.json). The copy is renamed
    aside at once and deleted in the background, so a removal cut short leaves no half-deleted copy.
    Returns '' when done, else what stopped it."""
    command = f'''repo="$HOME/{_CLONE_DIR}"; link="$HOME/bioinformatics-tools"; advert="$HOME/.local/share/bsp/api-endpoint.json"
if squeue -h -u "$USER" -o %j 2>/dev/null | grep -q '^margie-'; then
    echo "A MARGIE run of this cluster account is in SLURM; stop it, or wait for it to end, first."; exit 5
fi
if [ -f "$advert" ]; then
    echo "The desktop app's MARGIE server is running on this cluster account ($(cat "$advert" 2>/dev/null)); close the desktop app first."; exit 6
fi
rm -rf -- "$HOME/.config/bioinformatics-tools/secrets" || exit 1
if [ -L "$link" ] && [ "$(readlink -f "$link")" = "$(readlink -f "$repo/{_BACKEND_DIR}")" ]; then rm -f -- "$link" || exit 1; fi
if [ -e "$repo" ]; then
    gone="$HOME/.margie-removed-$(date +%Y%m%d-%H%M%S)-$$"
    mv -- "$repo" "$gone" || exit 1
    (nohup rm -rf -- "$gone" >/dev/null 2>&1 &)
fi
echo REMOVED'''
    try:
        ssh = conn.connect()
        _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        stdout.channel.settimeout(timeout)
        out = stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')
        code = stdout.channel.recv_exit_status()
    except Exception as exc:
        return str(exc) or type(exc).__name__
    return '' if code == 0 and 'REMOVED' in out else (out.strip() or f'exit {code}')


_KEY_CLASSES = (
    paramiko.RSAKey,
    paramiko.Ed25519Key,
    paramiko.ECDSAKey,
)


def load_private_key(key_str: str) -> paramiko.PKey:
    """
    Auto-detect SSH key type and return a paramiko PKey object.
    Tries RSA, Ed25519, ECDSA, and DSS in order.
    Raises ValueError if none succeed.
    """
    for key_class in _KEY_CLASSES:
        try:
            return key_class.from_private_key(io.StringIO(key_str.strip()))
        except (paramiko.SSHException, Exception):
            continue
    raise ValueError('Unsupported or invalid SSH private key format')


class SSHConnection:
    """Manages paramiko SSH connections with configurable host/user/key."""

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        pkey: paramiko.PKey | None = None,
        key_filename: str | None = None,
    ):
        self.host = host
        self.username = username
        self.pkey = pkey               # in-memory key object (API usage)
        self.key_filename = key_filename   # file path (CLI fallback)

    def _handshake(self) -> paramiko.SSHClient:
        """Builds and authenticates a new client, outside the pool."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = {'username': self.username}
        if self.pkey:
            connect_kwargs['pkey'] = self.pkey
        elif self.key_filename:
            connect_kwargs['key_filename'] = self.key_filename
        # If neither is set, paramiko falls back to the system SSH agent (CLI default)
        ssh.connect(self.host, **connect_kwargs)
        # Every command it runs is read from OUTPUT_MARK on (see above).
        ssh.exec_command = _clean_exec(ssh.exec_command)
        transport = ssh.get_transport()
        if transport is not None:
            transport.set_keepalive(_KEEPALIVE_SECONDS)
        LOGGER.debug('Connected to %s as %s', self.host, self.username)
        return ssh

    def connect(self, pooled: bool = True) -> paramiko.SSHClient:
        """Returns a live SSH connection, reusing a pooled one when possible.

        pooled=False returns a private client outside the pool, for callers that
        hold it beyond one request (e.g. ssh_slurm.submit_ssh_job for a whole run).
        """
        if not self.host or not self.username:
            raise ValueError(
                'SSHConnection requires host and username. '
                'Use make_user_connection() in API context, or set host/username '
                'from the user config for CLI usage.'
            )
        if not pooled:
            return self._handshake()

        key = _pool_key(self.host, self.username, self.pkey, self.key_filename)
        with _POOL_LOCK:
            entry = _POOL.setdefault(key, {'slots': [None] * _POOL_SIZE, 'next': 0,
                                           'making': [threading.Lock() for _ in range(_POOL_SIZE)]})
            slot = entry['next']
            entry['next'] = (slot + 1) % _POOL_SIZE
            client = entry['slots'][slot]
        # A closed client has _transport None, so is_active() alone is not enough.
        if client is not None and _alive(client):
            LOGGER.debug('Reusing pooled SSH connection %d to %s', slot, self.host)
            return client
        # One handshake per slot at a time; concurrent requests wait for it.
        with entry['making'][slot]:
            with _POOL_LOCK:
                current = entry['slots'][slot]
            if current is not None and _alive(current):
                return current
            if current is not None:
                # Only dead clients are closed; a live one may still be in use.
                try:
                    current.close()
                except Exception:
                    pass
            ssh = self._handshake()
            with _POOL_LOCK:
                entry['slots'][slot] = ssh
            return ssh


def runs_here(connection: 'SSHConnection') -> bool:
    """Returns True when this process runs on the connection's cluster as the same
    user (the desktop app's API on a login node), so files can be read directly."""
    import getpass
    import socket
    if not connection.username or connection.username != getpass.getuser():
        return False
    host = (connection.host or '').lower()
    fqdn = socket.getfqdn().lower()
    return bool(host) and (fqdn == host or fqdn.endswith('.' + host))


def make_user_connection(
    cluster_host: str,
    cluster_username: str,
    private_key_str: str,
) -> SSHConnection:
    """
    Build an SSHConnection for a specific user's cluster account.

    Accepts the plaintext (already-decrypted) private key string, loads it
    into a paramiko PKey object in memory, and returns an SSHConnection.
    The key is never written to disk.
    """
    pkey = load_private_key(private_key_str)
    return SSHConnection(host=cluster_host, username=cluster_username, pkey=pkey)


def ensure_remote_dane_wf(conn: SSHConnection, *, repo_url: str = _DANE_WF_REPO_URL, ref: str = _MARGIE_SB_REF,
                          timeout: float = 900.0) -> str:
    """
    Ensures the user's cluster account runs MARGIE's backend from its own clone of the
    repository: clones it into ~/margie-project-2026 (branch `ref`), builds the backend's
    environment (`uv sync`) and links ~/bioinformatics-tools to its be-margie/ folder.

    A link to an older checkout (a clone of bioinformatics-tools) is moved over to the new
    clone; the old checkout stays where it is. A folder of the user's own at
    ~/bioinformatics-tools, or a linked checkout with edits, is never replaced.
    BSP_SKIP_DANE_WF_SYNC=1 (API and cluster on one machine) only checks that dane_wf is built.
    Returns 'ready', 'linked', 'kept-own' or 'kept-edited'; raises RuntimeError with the
    remote output on failure.
    """
    if os.environ.get('BSP_SKIP_DANE_WF_SYNC'):
        command = 'test -x "$HOME/bioinformatics-tools/.venv/bin/dane_wf" && echo READY'
    else:
        command = f'''set -e
repo="$HOME/{_CLONE_DIR}"; code="$repo/{_BACKEND_DIR}"; link="$HOME/bioinformatics-tools"
same() {{ [ -n "$(readlink -f "$1" 2>/dev/null)" ] && [ "$(readlink -f "$1" 2>/dev/null)" = "$(readlink -f "$2" 2>/dev/null)" ]; }}
if same "$link" "$code" && [ -x "$code/.venv/bin/dane_wf" ]; then echo READY; exit 0; fi
if [ -e "$link" ] && [ ! -L "$link" ]; then
    [ -x "$link/.venv/bin/dane_wf" ] && {{ echo KEPT_OWN; exit 0; }}
    echo "$link is a folder of your own without MARGIE built in it; move it aside and connect again." >&2; exit 4
fi
if [ -L "$link" ] && ! same "$link" "$code" && [ -x "$link/.venv/bin/dane_wf" ] \\
   && [ -n "$(git -C "$link" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    echo KEPT_EDITED; exit 0
fi
if [ ! -d "$repo/.git" ]; then
    [ -e "$repo" ] && {{ echo "$repo is there and is not a clone of MARGIE; move it aside and connect again." >&2; exit 3; }}
    GIT_TERMINAL_PROMPT=0 git clone -q -b {shlex.quote(ref)} {shlex.quote(repo_url)} "$repo"
fi
cd "$code"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
fi
command -v uv >/dev/null 2>&1
uv sync --quiet
test -x "$code/.venv/bin/dane_wf"
# The checkout's own keys (.env, git-ignored): the older checkout's, so nothing it signed
# changes, else made now; dane_wf would make them on its first run anyway.
if [ ! -e "$code/.env" ]; then
    if [ -f "$link/.env" ]; then cp -p "$link/.env" "$code/.env"
    else "$code/.venv/bin/python" -c 'from bioinformatics_tools.workflow_tools.env_keys import ensure_api_keys; ensure_api_keys()' >/dev/null 2>&1 || true
    fi
fi
ln -sfn "$code" "$link"
echo LINKED
'''
    ssh = conn.connect()
    _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    stdout.channel.settimeout(timeout)
    output = (stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')).strip()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        raise RuntimeError(
            f'Could not provision dane_wf on the remote account (exit {exit_code}): {output or "(no output)"}'
        )
    for marker, result in (('LINKED', 'linked'), ('KEPT_OWN', 'kept-own'), ('KEPT_EDITED', 'kept-edited')):
        if marker in output:
            LOGGER.info('Cluster checkout for %s@%s: %s', conn.username, conn.host, result)
            return result
    return 'ready'


# ---- Each account's clone, made or moved over in the background ----
_PROVISIONING: dict = {}
_PROVISIONING_LOCK = threading.Lock()
# A failed attempt is tried again after this long, not on every request.
_RETRY_SECONDS = 600


def provision_in_background(conn: SSHConnection) -> None:
    """Starts ensure_remote_dane_wf for this account in a thread, once per API process (again
    after a failure, at most every _RETRY_SECONDS). Returns at once; wait_provisioned() waits."""
    key = (conn.host, conn.username)
    with _PROVISIONING_LOCK:
        state = _PROVISIONING.get(key)
        if state and (state['thread'].is_alive() or state['ok'] or time.monotonic() - state['at'] < _RETRY_SECONDS):
            return
        state = {'ok': False, 'at': time.monotonic()}

        def run() -> None:
            try:
                ensure_remote_dane_wf(conn)
                state['ok'] = True
            except Exception as exc:
                LOGGER.warning('Could not set up MARGIE in %s@%s: %s', conn.username, conn.host, exc)

        state['thread'] = threading.Thread(target=run, name=f'provision-{conn.username}', daemon=True)
        _PROVISIONING[key] = state
        state['thread'].start()


def wait_provisioned(conn: SSHConnection, timeout: float = 900.0) -> None:
    """Waits (up to `timeout` seconds) for this account's background set-up, if one is running."""
    with _PROVISIONING_LOCK:
        state = _PROVISIONING.get((conn.host, conn.username))
    if state and state['thread'].is_alive():
        state['thread'].join(timeout)


def sync_remote_dane_wf(conn: SSHConnection, *, ref: str = _MARGIE_SB_REF, repo_url: str = _DANE_WF_REPO_URL,
                        timeout: float = 30.0) -> str:
    """
    Fast-forwards the clone ~/bioinformatics-tools is in to `ref` on origin when it is behind
    and has no edits to tracked files.

    Cheap in the common case (a `git fetch` plus a SHA comparison); the
    `git reset --hard` + `uv sync` runs only when a new deployment has landed.
    Never raises. Returns 'unprovisioned', 'not-a-git-checkout', 'other-repo' (a checkout
    of another repository, which ensure_remote_dane_wf moves over), 'up-to-date',
    'dirty-skipped', 'updated', 'disabled' or 'error: <detail>'.

    BSP_SKIP_DANE_WF_SYNC=1 disables it, for a developer whose API and cluster
    are one machine (scripts/dev-local/start.sh sets it).
    """
    if os.environ.get('BSP_SKIP_DANE_WF_SYNC'):
        LOGGER.info('dane_wf version-sync check disabled by BSP_SKIP_DANE_WF_SYNC')
        return 'disabled'
    bare = repo_url[:-4] if repo_url.endswith('.git') else repo_url
    command = f'''cd "$HOME/bioinformatics-tools" 2>/dev/null || {{ echo NO_CHECKOUT; exit 0; }}
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {{ echo NOT_GIT; exit 0; }}
case "$(git remote get-url origin 2>/dev/null)" in
    {shlex.quote(bare)}|{shlex.quote(bare + '.git')}) ;;
    *) echo OTHER_REPO; exit 0 ;;
esac
git fetch origin {shlex.quote(ref)} --quiet 2>&1
local_sha=$(git rev-parse HEAD 2>/dev/null)
remote_sha=$(git rev-parse origin/{shlex.quote(ref)} 2>/dev/null)
if [ -z "$remote_sha" ] || [ "$local_sha" = "$remote_sha" ]; then
    echo UP_TO_DATE
    exit 0
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo DIRTY_SKIPPED
    exit 0
fi
git checkout {shlex.quote(ref)} --quiet 2>/dev/null || true
git reset --hard "$remote_sha" --quiet
export PATH="$HOME/.local/bin:$PATH"
uv sync --quiet
echo "UPDATED $remote_sha"
'''
    try:
        ssh = conn.connect()
        _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        stdout.channel.settimeout(timeout)
        output = (stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')).strip()
        exit_code = stdout.channel.recv_exit_status()
    except Exception as exc:
        LOGGER.warning('dane_wf version-sync check raised, skipping: %s', exc)
        return f'error: {exc}'

    if exit_code != 0:
        LOGGER.warning('dane_wf version-sync check failed (exit %s): %s', exit_code, output)
        return f'error: exit {exit_code}: {output}'

    if 'NO_CHECKOUT' in output:
        return 'unprovisioned'
    if 'NOT_GIT' in output:
        return 'not-a-git-checkout'
    if 'OTHER_REPO' in output:
        return 'other-repo'
    if 'DIRTY_SKIPPED' in output:
        LOGGER.info('Remote ~/bioinformatics-tools has local changes; skipped auto-update.')
        return 'dirty-skipped'
    if 'UPDATED' in output:
        LOGGER.info('Updated remote ~/bioinformatics-tools: %s', output)
        return 'updated'
    return 'up-to-date'


# ---- The account's copy of MARGIE: what it is, and an update on request ----
# The folder an update moves a replaced copy into, one subfolder per update, named for its time.
PREVIOUS_VERSIONS_DIR = 'margie-previous-versions'

_CHECK_SCRIPT = r'''link="$HOME/bioinformatics-tools"; repo="$HOME/__CLONE__"; code="$repo/__BACKEND__"
echo "HOME=$HOME"
if [ -L "$link" ]; then echo "KIND=link"; echo "TARGET=$(readlink -f "$link" 2>/dev/null)"
elif [ -d "$link" ]; then echo "KIND=folder"
else echo "KIND=missing"; fi
top=$(git -C "$link" rev-parse --show-toplevel 2>/dev/null)
[ "$top" = "$HOME" ] && top=""
if [ -n "$top" ]; then
    echo "TOP=$top"
    echo "COMMIT=$(git -C "$top" rev-parse HEAD 2>/dev/null)"
    echo "DATE=$(git -C "$top" log -1 --format=%cs 2>/dev/null)"
    echo "ORIGIN=$(git -C "$top" remote get-url origin 2>/dev/null)"
    git -C "$top" status --porcelain --untracked-files=no 2>/dev/null | head -n 20 | sed 's/^/EDIT=/'
fi
echo "CODE=$(readlink -f "$code" 2>/dev/null)"
if [ -e "$repo" ]; then
    echo "REPO=1"
    if [ -d "$repo/.git" ]; then
        echo "REPO_ORIGIN=$(git -C "$repo" remote get-url origin 2>/dev/null)"
        [ -n "$(git -C "$repo" status --porcelain --untracked-files=no 2>/dev/null)" ] && echo "REPO_EDITED=1"
    fi
fi
echo "LATEST=$(GIT_TERMINAL_PROMPT=0 timeout 30 git ls-remote __URL__ refs/heads/__REF__ 2>/dev/null | cut -f1)"
'''

# Moves the copy in use (and an edited or foreign ~/margie-project-2026) into a time-named folder
# of ~/margie-previous-versions, installs the latest MARGIE and links ~/bioinformatics-tools to
# it. A failed step puts the moved folders back, so the copy in use before stays in use.
_UPDATE_SCRIPT = r'''link="$HOME/bioinformatics-tools"; repo="$HOME/__CLONE__"; code="$repo/__BACKEND__"
backup="$HOME/__PREVIOUS__/$(date +%Y-%m-%d-%H%M%S)"
same() { [ -n "$(readlink -f "$1" 2>/dev/null)" ] && [ "$(readlink -f "$1" 2>/dev/null)" = "$(readlink -f "$2" 2>/dev/null)" ]; }
ours() { case "$(git -C "$1" remote get-url origin 2>/dev/null)" in __URL_BARE__|__URL_BARE__.git) return 0 ;; esac; return 1; }
moved_link=""; moved_repo=""; old_target=""; carry=""
fail() {
    echo "FAILED $1"
    if [ -n "$moved_repo" ]; then
        [ -e "$repo" ] && mv "$repo" "$backup/__CLONE__-incomplete"
        mv "$backup/__CLONE__" "$repo"
    fi
    if [ -n "$moved_link" ]; then
        [ -L "$link" ] && rm -f "$link"
        mv "$backup/bioinformatics-tools" "$link"
    elif [ -n "$old_target" ]; then
        ln -sfn "$old_target" "$link"
    fi
    [ -n "$carry" ] && rm -f "$carry"
    [ -n "$moved_link$moved_repo" ] && echo "RESTORED"
    rmdir "$backup" "$HOME/__PREVIOUS__" 2>/dev/null
    exit 1
}
# The copy's own keys (.env) go with it into the new copy, so nothing it signed changes.
if [ -f "$link/.env" ]; then carry=$(mktemp "$HOME/.margie-keys.XXXXXX") && cp -p "$link/.env" "$carry" || carry=""; fi
if [ -d "$link" ] && [ ! -L "$link" ]; then
    mkdir -p "$backup" && mv "$link" "$backup/bioinformatics-tools" || fail "could not move $link aside"
    moved_link=1; echo "MOVED $link|$backup/bioinformatics-tools"
fi
if [ -e "$repo" ] && { [ ! -d "$repo/.git" ] || ! ours "$repo" || [ -n "$(git -C "$repo" status --porcelain --untracked-files=no 2>/dev/null)" ]; }; then
    mkdir -p "$backup" && mv "$repo" "$backup/__CLONE__" || fail "could not move $repo aside"
    moved_repo=1; echo "MOVED $repo|$backup/__CLONE__"
fi
if [ -L "$link" ] && ! same "$link" "$code"; then
    old_target=$(readlink "$link"); rm -f "$link" || fail "could not relink $link"
    echo "UNLINKED $old_target"
fi
if [ ! -d "$repo/.git" ]; then
    GIT_TERMINAL_PROMPT=0 git clone -q -b __REF__ __URL__ "$repo" || fail "could not download MARGIE"
fi
cd "$repo" || fail "could not open $repo"
GIT_TERMINAL_PROMPT=0 git fetch -q origin __REF__ || fail "could not reach the MARGIE repository"
git checkout -q __REF__ 2>/dev/null || git checkout -q -b __REF__ origin/__REF__ || fail "could not switch to __REF__"
git reset -q --hard origin/__REF__ || fail "could not update $repo"
cd "$code" || fail "could not open $code"
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
command -v uv >/dev/null 2>&1 || fail "could not install uv"
uv sync --quiet || fail "could not build MARGIE's environment (uv sync)"
[ -x "$code/.venv/bin/dane_wf" ] || fail "dane_wf is missing after the build"
if [ ! -e "$code/.env" ]; then
    if [ -n "$carry" ]; then cp -p "$carry" "$code/.env"
    else "$code/.venv/bin/python" -c 'from bioinformatics_tools.workflow_tools.env_keys import ensure_api_keys; ensure_api_keys()' >/dev/null 2>&1 || true
    fi
fi
[ -n "$carry" ] && rm -f "$carry"
ln -sfn "$code" "$link" || fail "could not link $link"
echo "UPDATED $(git -C "$repo" rev-parse HEAD)"
[ -n "$moved_link$moved_repo" ] && echo "BACKUP $backup"
exit 0
'''


def _fill(script: str, repo_url: str, ref: str) -> str:
    """The script with the repository, branch and folder names in place."""
    bare = repo_url[:-4] if repo_url.endswith('.git') else repo_url
    return (script.replace('__URL_BARE__', shlex.quote(bare)).replace('__URL__', shlex.quote(repo_url))
            .replace('__REF__', shlex.quote(ref)).replace('__CLONE__', _CLONE_DIR)
            .replace('__BACKEND__', _BACKEND_DIR).replace('__PREVIOUS__', PREVIOUS_VERSIONS_DIR))


def _same_repo(url: str, repo_url: str) -> bool:
    strip = lambda u: (u or '').strip().removesuffix('/').removesuffix('.git')
    return bool(url) and strip(url) == strip(repo_url)


def check_remote_dane_wf(conn: SSHConnection, *, ref: str = _MARGIE_SB_REF, repo_url: str = _DANE_WF_REPO_URL,
                         timeout: float = 60.0) -> dict:
    """
    Describes the copy of MARGIE the account runs (~/bioinformatics-tools) beside the latest on
    `ref`, and what an update would move into ~/margie-previous-versions/<time>/.

    state: 'latest'; 'behind' (MARGIE's clone, updated before the next run); 'own-folder' (a
    folder of the user's own); 'edited' (MARGIE's clone with edited files); 'other-copy' (a link
    to another checkout); 'missing' (set up at sign-in). The last four are kept as they are
    until the user updates (update_remote_dane_wf).
    """
    _, stdout, stderr = conn.connect().exec_command(_fill(_CHECK_SCRIPT, repo_url, ref), timeout=timeout)
    stdout.channel.settimeout(timeout)
    out = stdout.read().decode(errors='replace')
    stderr.read()
    facts: dict = {}
    edits: list[str] = []
    for line in out.splitlines():
        key, sep, value = line.partition('=')
        if not sep:
            continue
        if key == 'EDIT':
            edits.append(value.strip())
        else:
            facts[key] = value.strip()
    home = facts.get('HOME', '')
    link = f'{home}/bioinformatics-tools'
    repo = f'{home}/{_CLONE_DIR}'
    kind = facts.get('KIND', '')
    commit, latest = facts.get('COMMIT', ''), facts.get('LATEST', '')
    ours = facts.get('TARGET') and facts.get('TARGET') == facts.get('CODE')
    if kind == 'folder':
        state = 'own-folder'
    elif kind == 'link' and ours:
        state = 'edited' if edits else 'behind' if latest and commit and commit != latest else 'latest'
    elif kind == 'link':
        state = 'other-copy'
    else:
        state = 'missing'
    # What an update moves aside: the folder in use when it is the user's own, and the clone
    # when it has edits or is a clone of something else.
    moves = []
    if kind == 'folder':
        moves.append(link)
    if facts.get('REPO') and (not facts.get('REPO_ORIGIN') or facts.get('REPO_EDITED')
                              or not _same_repo(facts.get('REPO_ORIGIN', ''), repo_url)):
        moves.append(repo)
    return {
        'state': state,
        'home': home,
        'path': link,
        'points_to': facts.get('TARGET', '') if kind == 'link' else link if kind == 'folder' else '',
        'checkout': facts.get('TOP', ''),
        'from_margie': _same_repo(facts.get('ORIGIN', ''), repo_url),
        'current': {'commit': commit, 'date': facts.get('DATE', '')} if commit else None,
        'latest': {'commit': latest} if latest else None,
        'edited': edits,
        'moves': moves,
        'install': f'{repo}/{_BACKEND_DIR}',
        'previous_versions': f'{home}/{PREVIOUS_VERSIONS_DIR}',
    }


def update_remote_dane_wf(conn: SSHConnection, *, ref: str = _MARGIE_SB_REF, repo_url: str = _DANE_WF_REPO_URL,
                          timeout: float = 900.0) -> dict:
    """
    Installs the latest MARGIE on `ref` as the account's copy: the copy in use, when it is a
    folder of the user's own, and an edited or foreign ~/margie-project-2026 move into
    ~/margie-previous-versions/<time>/ first, with their files as they were. Returns {'ok',
    'commit', 'backup', 'moved': [[from, to]], 'restored', 'message'}; a failed step puts the
    moved folders back (restored).
    """
    _, stdout, stderr = conn.connect().exec_command(_fill(_UPDATE_SCRIPT, repo_url, ref), timeout=timeout)
    stdout.channel.settimeout(timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    code = stdout.channel.recv_exit_status()
    lines = out.splitlines()
    pick = lambda word: next((ln[len(word) + 1:].strip() for ln in lines if ln.startswith(word + ' ')), '')
    moved = [ln[6:].split('|', 1) for ln in lines if ln.startswith('MOVED ') and '|' in ln]
    result = {
        'ok': code == 0 and bool(pick('UPDATED')),
        'commit': pick('UPDATED'),
        'backup': pick('BACKUP'),
        'moved': moved,
        'restored': 'RESTORED' in lines,
        'message': pick('FAILED') or (err.strip().splitlines()[-1] if code and err.strip() else ''),
    }
    LOGGER.info('MARGIE update for %s@%s: %s', conn.username, conn.host, result)
    return result


# ---- Each account's update, run in the background and followed by the site ----
_UPDATES: dict = {}
_UPDATES_LOCK = threading.Lock()


def update_state(conn: SSHConnection) -> dict | None:
    """The account's update under way or last finished in this API, or None."""
    with _UPDATES_LOCK:
        state = _UPDATES.get((conn.host, conn.username))
        return {k: v for k, v in state.items() if k != 'thread'} if state else None


def start_update(conn: SSHConnection, on_done=None) -> dict:
    """Starts update_remote_dane_wf for this account in a thread (one at a time) and returns its
    state; on_done(result) runs when it ends."""
    key = (conn.host, conn.username)
    with _UPDATES_LOCK:
        state = _UPDATES.get(key)
        if state and state['state'] == 'running':
            return {k: v for k, v in state.items() if k != 'thread'}
        state = {'state': 'running', 'started': time.time(), 'finished': None, 'result': None}
        _UPDATES[key] = state

    def run() -> None:
        try:
            # The sign-in's own set-up of the clone finishes first.
            wait_provisioned(conn)
            result = update_remote_dane_wf(conn)
        except Exception as exc:
            LOGGER.warning('MARGIE update for %s@%s raised: %s', conn.username, conn.host, exc)
            result = {'ok': False, 'commit': '', 'backup': '', 'moved': [], 'restored': False, 'message': str(exc)}
        with _UPDATES_LOCK:
            state.update(state='done' if result['ok'] else 'failed', finished=time.time(), result=result)
        if on_done:
            try:
                on_done(result)
            except Exception as exc:
                LOGGER.debug('After the MARGIE update: %s', exc)

    state['thread'] = threading.Thread(target=run, name=f'update-{conn.username}', daemon=True)
    state['thread'].start()
    return {k: v for k, v in state.items() if k != 'thread'}


