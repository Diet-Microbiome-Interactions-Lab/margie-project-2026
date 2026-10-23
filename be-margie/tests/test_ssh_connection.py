"""Each cluster account's own clone of the repository: made at sign-up, an older checkout moved
over to it, a folder of the user's own or a checkout with edits left alone, and kept at main.
The shell runs for real here, in a temporary home folder, cloning a local repository; a
stand-in `uv` builds the environment."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bioinformatics_tools.utilities import ssh_connection as sc


class _Out:
    def __init__(self, data: bytes, code: int = 0):
        self._data = data
        self.channel = SimpleNamespace(recv_exit_status=lambda: code, settimeout=lambda t: None)

    def read(self) -> bytes:
        return self._data


class LocalConn:
    """Runs the commands meant for the cluster in a local shell with HOME set to `home`."""

    host = "cluster"

    def __init__(self, home: Path):
        self.home = home
        self.username = home.name
        self.commands: list[str] = []

    def connect(self, pooled: bool = True):
        return self

    def exec_command(self, command, timeout=None):
        self.commands.append(command)
        env = {"HOME": str(self.home), "PATH": f"{self.home}/.local/bin:/usr/bin:/bin:/usr/local/bin",
               "GIT_CONFIG_NOSYSTEM": "1"}
        r = subprocess.run(["bash", "-c", command], capture_output=True, env=env, timeout=120)
        return None, _Out(r.stdout, r.returncode), _Out(r.stderr)


def _git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A repository like margie-project-2026 (branch main, backend in be-margie/), a home
    folder with a stand-in uv, and the clone settings pointed at them."""
    monkeypatch.delenv("BSP_SKIP_DANE_WF_SYNC", raising=False)
    origin = tmp_path / "origin"
    (origin / "be-margie").mkdir(parents=True)
    (origin / "be-margie" / "pyproject.toml").write_text("[project]\nname='x'\n")
    (origin / "fe-margie").mkdir()
    (origin / "fe-margie" / "README.md").write_text("web\n")
    _git("init", "-q", "-b", "main", cwd=origin)
    _git("add", ".", cwd=origin)
    _git("commit", "-q", "-m", "first", cwd=origin)
    home = tmp_path / "home" / "user"
    (home / ".local" / "bin").mkdir(parents=True)
    uv = home / ".local" / "bin" / "uv"
    uv.write_text('#!/bin/bash\nmkdir -p .venv/bin && printf "#!/bin/bash\\n" > .venv/bin/dane_wf && chmod +x .venv/bin/dane_wf\n')
    uv.chmod(0o755)
    monkeypatch.setattr(sc, "_DANE_WF_REPO_URL", str(origin))
    return SimpleNamespace(origin=origin, home=home, conn=LocalConn(home))


def _built(folder: Path) -> None:
    """Makes `folder` look like a checkout with MARGIE built in it."""
    (folder / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
    (folder / ".venv" / "bin" / "dane_wf").write_text("#!/bin/bash\n")
    (folder / ".venv" / "bin" / "dane_wf").chmod(0o755)


def _ensure(world):
    return sc.ensure_remote_dane_wf(world.conn, repo_url=str(world.origin), ref="main", timeout=60)


def test_a_new_account_gets_its_own_clone_linked(world):
    assert _ensure(world) == "linked"
    link = world.home / "bioinformatics-tools"
    assert link.is_symlink() and link.resolve() == (world.home / "margie-project-2026" / "be-margie").resolve()
    assert (link / ".venv" / "bin" / "dane_wf").exists()
    assert _ensure(world) == "ready"


def test_an_older_checkout_is_moved_over_and_kept(world):
    old = world.home / "margie-backend"
    _built(old)
    (old / ".env").write_text("BSP_SECRET_KEY=old\n")
    (world.home / "bioinformatics-tools").symlink_to(old)
    assert _ensure(world) == "linked"
    assert (world.home / "bioinformatics-tools").resolve() == (world.home / "margie-project-2026" / "be-margie").resolve()
    assert old.exists()
    # Its keys come along, so the cluster-side helpers keep working.
    assert (world.home / "bioinformatics-tools" / ".env").read_text() == "BSP_SECRET_KEY=old\n"


def test_an_older_checkout_with_edits_is_left_alone(world):
    old = world.home / "margie-backend"
    old.mkdir()
    (old / "margie_sb.smk").write_text("rule a\n")
    _git("init", "-q", cwd=old)
    _git("add", ".", cwd=old)
    _git("commit", "-q", "-m", "x", cwd=old)
    (old / "margie_sb.smk").write_text("rule edited\n")
    _built(old)
    (world.home / "bioinformatics-tools").symlink_to(old)
    assert _ensure(world) == "kept-edited"
    assert (world.home / "bioinformatics-tools").resolve() == old.resolve()


def test_a_folder_of_ones_own_is_never_replaced(world):
    own = world.home / "bioinformatics-tools"
    _built(own)
    assert _ensure(world) == "kept-own"
    assert own.is_dir() and not own.is_symlink()


def test_a_folder_of_ones_own_without_margie_is_reported(world):
    (world.home / "bioinformatics-tools").mkdir()
    with pytest.raises(RuntimeError, match="folder of your own"):
        _ensure(world)


def test_the_clone_is_kept_at_main_and_an_older_checkout_is_named(world):
    assert _ensure(world) == "linked"
    sync = lambda: sc.sync_remote_dane_wf(world.conn, ref="main", repo_url=str(world.origin))  # noqa: E731
    assert sync() == "up-to-date"
    (world.origin / "be-margie" / "new.py").write_text("x = 1\n")
    _git("add", ".", cwd=world.origin)
    _git("commit", "-q", "-m", "second", cwd=world.origin)
    assert sync() == "updated"
    assert (world.home / "bioinformatics-tools" / "new.py").exists()
    # Untracked files (logs) do not count as edits; an edit to a tracked file does.
    (world.home / "bioinformatics-tools" / ".margie-api.log").write_text("log\n")
    (world.origin / "be-margie" / "new.py").write_text("x = 2\n")
    _git("commit", "-qam", "third", cwd=world.origin)
    assert sync() == "updated"
    (world.home / "bioinformatics-tools" / "new.py").write_text("x = 'mine'\n")
    (world.origin / "be-margie" / "new.py").write_text("x = 3\n")
    _git("commit", "-qam", "fourth", cwd=world.origin)
    assert sync() == "dirty-skipped"
    # A checkout of another repository is named so that it can be moved over.
    other = world.home / "elsewhere"
    other.mkdir()
    _git("init", "-q", cwd=other)
    _git("remote", "add", "origin", "https://github.com/someone/bioinformatics-tools.git", cwd=other)
    (world.home / "bioinformatics-tools").unlink()
    (world.home / "bioinformatics-tools").symlink_to(other)
    assert sync() == "other-repo"


def test_setting_up_runs_once_in_the_background(world, monkeypatch):
    calls = []
    monkeypatch.setattr(sc, "_PROVISIONING", {})
    monkeypatch.setattr(sc, "ensure_remote_dane_wf", lambda conn: calls.append(conn) or "linked")
    sc.provision_in_background(world.conn)
    sc.wait_provisioned(world.conn)
    sc.provision_in_background(world.conn)
    sc.wait_provisioned(world.conn)
    assert len(calls) == 1


def test_one_machine_for_api_and_cluster_only_checks(world, monkeypatch):
    monkeypatch.setenv("BSP_SKIP_DANE_WF_SYNC", "1")
    with pytest.raises(RuntimeError):
        _ensure(world)
    assert "git clone" not in world.conn.commands[-1]
