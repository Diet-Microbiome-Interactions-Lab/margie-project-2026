"""Nothing a user's shell start-up prints reaches MARGIE (ssh_connection.marked / AfterMark): a
~/.bashrc that fails ("Error: ... shell extension not activated") or chats must not end up in
a job id, a home folder or JSON read back from the cluster."""

import io
import subprocess

from bioinformatics_tools.utilities import ssh_connection as sc

STARTUP = 'echo "Error: Liminal shell extension not activated from " >&2; echo "Welcome back!"'


class _File:
    """Like paramiko's channel files: readline() gives text, read() gives bytes."""

    def __init__(self, data: bytes):
        self._b = io.BytesIO(data)
        self.channel = object()

    def readline(self, *a):
        return self._b.readline().decode()

    def read(self, *a):
        return self._b.read()

    def __iter__(self):
        while True:
            line = self.readline()
            if not line:
                return
            yield line


def _run(command: str, startup: str = STARTUP):
    """Runs a marked command the way sshd would: the user's start-up first, then the command."""
    r = subprocess.run(["bash", "-c", f"{startup}\n{sc.marked(command)}"], capture_output=True)
    return sc.AfterMark(_File(r.stdout)), sc.AfterMark(_File(r.stderr))


def test_a_job_id_comes_back_clean():
    out, err = _run("echo 44604769")
    assert out.read() == b"44604769\n" and err.read() == b""


def test_the_commands_own_errors_are_kept():
    out, err = _run("echo partial; echo 'Permission denied' >&2; exit 3")
    assert out.read() == b"partial\n" and err.read() == b"Permission denied\n"


def test_reading_line_by_line_and_looping():
    out, _ = _run("printf 'a\\nb\\nc\\n'")
    assert out.readline() == "a\n"
    assert list(out) == ["b\n", "c\n"]


def test_multi_line_scripts_with_early_exits_still_work():
    out, _ = _run('cd /nonexistent 2>/dev/null || { echo NO_CHECKOUT; exit 0; }\necho never')
    assert out.read() == b"NO_CHECKOUT\n"


def test_without_a_mark_everything_is_kept():
    # The shell gave up before running the command: what it printed says why.
    r = subprocess.run(["bash", "-c", "echo 'cannot start' >&2; exit 1"], capture_output=True)
    assert sc.AfterMark(_File(r.stderr)).read() == b"cannot start\n"


def test_clients_mark_every_command():
    seen = []

    def exec_command(command, *a, **k):
        seen.append(command)
        r = subprocess.run(["bash", "-c", f"{STARTUP}\n{command}"], capture_output=True)
        return None, _File(r.stdout), _File(r.stderr)

    run = sc._clean_exec(exec_command)
    _, out, err = run("echo $((40 + 2))")
    assert seen[0].startswith("printf") and sc.OUTPUT_MARK in seen[0]
    assert out.read() == b"42\n" and err.read() == b""
    assert run.__wrapped__ is exec_command
