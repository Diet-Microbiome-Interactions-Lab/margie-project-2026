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
    exit_code = stdout.channel.recv_exit_status()
    output = (stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')).strip()
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
        exit_code = stdout.channel.recv_exit_status()
        output = (stdout.read().decode(errors='replace') + stderr.read().decode(errors='replace')).strip()
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


