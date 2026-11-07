"""Redraw all maps (routers/ssh.py): one SLURM job draws each listed genome's map and circular figure
again, four at a time, and counts what it drew; Results follows it. The job's script runs here, with
this checkout's drawing scripts, and the endpoint against a stubbed sbatch and squeue."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bioinformatics_tools.api.auth import get_current_user
from bioinformatics_tools.api.main import app
from bioinformatics_tools.api.routers import ssh
from bioinformatics_tools.api.services import user_stores

VIZ = Path(ssh.__file__).resolve().parents[2] / "workflow_tools" / "viz"
USER = {"user_id": 1, "username": "testuser", "cluster_host": "test.cluster.edu", "cluster_username": "testuser",
        "home_dir": "/home/testuser", "private_key_encrypted": "x"}
HEAD = ["organism_name", "gene_id", "RAST_feature_id", "RAST_start", "RAST_end", "RAST_strand", "CONFIDENCE_TIER", "RAST_na_sequence"]


def _genome(run: Path, name: str, tidied: bool) -> Path:
    """A genome's folder as a run leaves it: tidied (table, map and diagrams/ at the top) or not (scoring/)."""
    g = run / name
    table = g / ("" if tidied else "scoring") / "FINAL_ANNOTATION_WITH_CONFIDENCE.tsv"
    table.parent.mkdir(parents=True, exist_ok=True)
    rows = [[name, "c1_10+300", "fig|1.1.peg.1", "10", "309", "+", "high", "ATGGCGC" * 40],
            [name, "c1_400+90", "fig|1.1.peg.2", "400", "489", "-", "low", "ATGAAAT" * 12]]
    table.write_text("\n".join("\t".join(r) for r in [HEAD, *rows]) + "\n")
    if tidied:
        (g / "diagrams").mkdir()
        (g / "diagrams" / f"{name}_circular.png").write_bytes(b"old figure")
        (g / "FINAL_GENOME_VIEWER.html").write_text("<!doctype html>\n<!-- margie-viewer old -->")
    return g


def _bin(tmp_path: Path, squeue: str = "") -> Path:
    """sbatch that records its arguments and answers job 4242; squeue that lists `squeue`."""
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    (b / "sbatch").write_text(f'#!/bin/sh\necho "$@" > {tmp_path}/sbatch.args\necho 4242\n')
    (b / "squeue").write_text(f"#!/bin/sh\nprintf '%s' '{squeue}'\n")
    for f in ("sbatch", "squeue"):
        (b / f).chmod(0o755)
    return b


def _local_run(tmp_path: Path, squeue: str = ""):
    """user_stores._run on this machine, with the stubs first on PATH."""
    env = {**os.environ, "PATH": f"{_bin(tmp_path, squeue)}:{os.environ['PATH']}"}

    def run(conn, cmd, timeout=60):
        r = subprocess.run(["bash", "-c", cmd], env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    return run


def test_the_job_draws_each_genome_again_and_counts_them(tmp_path):
    run = tmp_path / "run"
    tidied, fresh = _genome(run, "g1--fa1:aa", True), _genome(run, "g2--fa1:bb", False)
    state = tmp_path / "state"
    state.mkdir()
    (state / "redraw.sh").write_text(ssh._REDRAW_SCRIPT)
    (state / "env.sh").write_text(f"PY={sys.executable}; VIZ={VIZ}; AT_ONCE=2\n")
    (state / "folders.txt").write_text(f"{tidied}\n{fresh}\n{run / 'gone'}\n")
    r = subprocess.run(["bash", str(state / "redraw.sh"), str(state)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    status = dict(line.split("=", 1) for line in (state / "status").read_text().split())
    assert (status["state"], status["total"], status["done"], status["failed"]) == ("done", "3", "2", "1")
    assert (state / "failed.txt").read_text().strip() == str(run / "gone")
    # Each map drawn by this version, beside its table; the circular figure redrawn where it was.
    assert "margie-viewer old" not in (tidied / "FINAL_GENOME_VIEWER.html").read_text()
    assert (fresh / "FINAL_GENOME_VIEWER.html").read_text().startswith("<!doctype html>\n<!-- margie-viewer ")
    assert (tidied / "diagrams" / "g1--fa1:aa_circular.png").read_bytes()[:4] == b"\x89PNG"
    assert not list(tidied.rglob("*.new*"))


def test_the_status_says_how_far_it_has_got(tmp_path):
    state = tmp_path / "state"
    with patch.object(user_stores, "_run", _local_run(tmp_path)):
        assert ssh._redraw_status(None, str(state)) == {"state": "none"}
        state.mkdir()
        (state / "status").write_text("state=running\ntotal=3\njob=4242\n")
        (state / "done.txt").write_text("/a\n")
        (state / "failed.txt").write_text("/b\n")
    with patch.object(user_stores, "_run", _local_run(tmp_path, squeue="RUNNING")):
        s = ssh._redraw_status(None, str(state))
        assert (s["state"], s["total"], s["done"], s["failed"], s["failedFolders"]) == ("running", 3, 1, 1, ["/b"])
    # SLURM no longer has the job and it never said it finished: it ended early.
    with patch.object(user_stores, "_run", _local_run(tmp_path, squeue="")):
        s = ssh._redraw_status(None, str(state))
        assert s["state"] == "failed" and "ended before it finished" in s["note"]


@pytest.fixture()
def api(tmp_path, monkeypatch):
    from bioinformatics_tools.api import licensing
    monkeypatch.setenv("BSP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(licensing, "has_accepted_current_terms", lambda username: True)
    app.dependency_overrides[get_current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)


def _cluster(tmp_path, config, squeue=""):
    state_root = tmp_path / "scratch"
    return [
        patch.object(ssh, "_build_connection", return_value=None),
        patch.object(ssh, "_read_config", return_value=config),
        patch.object(ssh, "_stores_call", side_effect=lambda fn, conn, cfg: str(state_root)),
        patch.object(ssh, "_resolve_browse_path", side_effect=lambda p, user: p),
        patch.object(ssh, "sync_remote_dane_wf"),
        patch.object(ssh.ssh_sftp, "write_remote_text_file", side_effect=lambda path, text, connection=None: Path(path).write_text(text)),
        patch.object(user_stores, "_run", _local_run(tmp_path, squeue)),
    ]


def test_one_slurm_job_with_the_account_and_the_list(api, tmp_path):
    config = {"compute": {"cluster_default": {"account": "lab-acct", "partition": "cpu"}}}
    patches = _cluster(tmp_path, config, squeue="PENDING")
    for p in patches:
        p.start()
    try:
        r = api.post("/v1/ssh/genome-viewer/refresh-all", json={"folders": ["/r/g1", "/r/g2", "/r/g1"]})
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "queued" and r.json()["total"] == 2 and r.json()["job"] == "4242"
        state = tmp_path / "scratch" / ssh.MAP_REDRAWS
        assert (state / "folders.txt").read_text() == "/r/g1\n/r/g2\n"
        args = (tmp_path / "sbatch.args").read_text()
        assert "--account=lab-acct" in args and "--partition=cpu" in args and f"--cpus-per-task={ssh._REDRAW_AT_ONCE}" in args
        assert "AT_ONCE=4" in (state / "env.sh").read_text() and (state / "redraw.sh").read_text() == ssh._REDRAW_SCRIPT
        # One at a time: a second is refused while the first waits.
        again = api.post("/v1/ssh/genome-viewer/refresh-all", json={"folders": ["/r/g1"]})
        assert again.status_code == 409 and "already" in again.json()["detail"]
        assert api.get("/v1/ssh/genome-viewer/refresh-all").json()["state"] == "queued"
    finally:
        for p in patches:
            p.stop()


def test_no_job_without_a_slurm_account(api, tmp_path):
    patches = _cluster(tmp_path, {"compute": {"cluster_default": {}}})
    for p in patches:
        p.start()
    try:
        r = api.post("/v1/ssh/genome-viewer/refresh-all", json={"folders": ["/r/g1"]})
        assert r.status_code == 409 and "SLURM account" in r.json()["detail"]
        assert not (tmp_path / "sbatch.args").exists()
    finally:
        for p in patches:
            p.stop()
