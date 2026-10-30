"""A run is started once and seen: a run the job history does not hold is not started (503), a
second resume or restart of a run while one is starting or going gets 409, and Run again on an
ended run resumes that genome alone, from copies of its own folders."""

import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from bioinformatics_tools.api.auth import get_current_user
from bioinformatics_tools.api.main import app
from bioinformatics_tools.api.routers import ssh
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.utilities import ssh_slurm

USER = {"user_id": 1, "username": "testuser", "cluster_host": "test.cluster.edu",
        "cluster_username": "testuser", "home_dir": "/home/testuser", "private_key_encrypted": "x"}
CONFIG = {"main_database": "~/my-db.db", "compute": {"cluster_default": {"account": "test-account"}}}
G = "Bacteroides_thetaiotaomicron_GCF_014131755.1--fa1:f9cb064d"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    from bioinformatics_tools.api import licensing
    monkeypatch.setenv("BSP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(licensing, "has_accepted_current_terms", lambda username: True)
    job_store._jobs.clear()
    app.dependency_overrides[get_current_user] = lambda: USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)
    job_store._jobs.clear()
    ssh._RELAUNCHING.clear()


def _quiet(conn, output: bytes = b""):
    stdout, stderr = MagicMock(), MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = output
    stderr.read.return_value = b""
    conn.return_value.connect.return_value.exec_command.return_value = (MagicMock(), stdout, stderr)


def _ended_job(status="failed", work_dir="/remote/out/2026-10-28-1020"):
    jid = str(uuid.uuid4())
    job_store.create(jid, "/remote/margie-input", user_id=1, workflow="margie_sb")
    job_store.update(jid, status=status, work_dir=work_dir)
    return jid


# ---- a run the history does not hold is not started ----

@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh.job_runner")
@patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
def test_a_run_missing_from_the_history_is_not_started(mock_sftp, mock_runner, mock_conn, api, monkeypatch):
    monkeypatch.setattr(ssh, "_in_history", lambda *args, **kwargs: False)
    mock_sftp.read_remote_yaml.return_value = dict(CONFIG)
    _quiet(mock_conn)
    jid = _ended_job()
    before = set(job_store._jobs)
    resp = api.post(f"/v1/ssh/resume_job/{jid}")
    assert resp.status_code == 503
    assert "did not start it" in resp.json()["detail"]
    mock_runner.submit_job.assert_not_called()
    assert set(job_store._jobs) == before
    sent = [c.args[0] for c in mock_conn.return_value.connect.return_value.exec_command.call_args_list]
    assert any(cmd.startswith("rmdir -- ") for cmd in sent)


def test_the_check_reads_the_run_back_from_the_history():
    real = ssh._in_history.real  # conftest stands in for it elsewhere
    with patch.object(ssh.job_history_client, "get_job", return_value={"job_id": "j"}) as got:
        assert real("conn", "~/db.db", "j", USER) is True
        assert got.call_args.kwargs == {"owner_username": "testuser", "owner_cluster_username": "testuser"}
    with patch.object(ssh.job_history_client, "get_job", return_value=None):
        assert real("conn", "~/db.db", "j", USER) is False


# ---- one relaunch at a time ----

@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh.job_runner")
def test_a_second_resume_while_the_first_is_under_way_gets_409(mock_runner, mock_conn, api):
    jid = _ended_job()
    ssh._RELAUNCHING.add(jid)
    for route in ("resume_job", "restart_job"):
        resp = api.post(f"/v1/ssh/{route}/{jid}")
        assert resp.status_code == 409, route
        assert "already" in resp.json()["detail"]
    mock_conn.assert_not_called()
    mock_runner.submit_job.assert_not_called()


def _child(jid, status, minutes_ago=1):
    when = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {"job_id": "c0ffee00-1111", "relaunched_from": jid, "status": status, "updated_at": when,
            "work_dir": "/remote/out/2026-10-28-1022"}


@pytest.mark.parametrize("status,minutes_ago,refused", [
    ("running", 600, True), ("pending", 2, True), ("pending", 60, False), ("failed", 1, False), ("cancelled", 1, False)])
def test_a_run_resumed_already_and_still_going_is_not_resumed_again(status, minutes_ago, refused, monkeypatch):
    jid = "a3d2a4d3-e2fe"
    monkeypatch.setattr(ssh, "_reconcile_running", lambda *args, **kwargs: None)
    monkeypatch.setattr(ssh.job_history_client, "list_jobs_and_count",
                        lambda *args, **kwargs: ([_child(jid, status, minutes_ago), {"job_id": "other", "status": "running"}], 2))
    if refused:
        with pytest.raises(HTTPException) as err:
            ssh._refuse_if_relaunched("conn", "~/db.db", jid, USER)
        assert err.value.status_code == 409
        assert "c0ffee00 (2026-10-28-1022)" in err.value.detail
    else:
        ssh._refuse_if_relaunched("conn", "~/db.db", jid, USER)


# ---- Run again on an ended run: that genome alone ----

def test_genome_names_carry_their_hash_label():
    assert ssh._GENOME_NAME.match(G)
    for bad in ("../x", "a/b", "", "-x", "a b"):
        assert not ssh._GENOME_NAME.match(bad), bad


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh.job_runner")
@patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
def test_run_again_on_an_ended_run_resumes_that_genome_alone(mock_sftp, mock_runner, mock_conn, api):
    mock_sftp.read_remote_yaml.return_value = dict(CONFIG)
    mock_sftp.stage_genome_links.return_value = "/home/testuser/.margie/selections/20261028-testuser"
    _quiet(mock_conn, f"{G}.fna\t/remote/margie-input/Bacteroides_thetaiotaomicron_GCF_014131755.1.fna\n".encode())
    jid = _ended_job()
    resp = api.post(f"/v1/ssh/resume_job/{jid}", json={"genomes": [G]})
    assert resp.status_code == 200, resp.text
    links = mock_sftp.stage_genome_links.call_args.args[0]
    assert links == {"Bacteroides_thetaiotaomicron_GCF_014131755.1.fna":
                     "/remote/margie-input/Bacteroides_thetaiotaomicron_GCF_014131755.1.fna"}
    submit = mock_runner.submit_job.call_args
    assert submit.kwargs["copy_from"] == "/remote/out/2026-10-28-1020"
    assert submit.kwargs["copy_only"] == [G, f"original_container_outputs/{G}"]
    assert "input: /home/testuser/.margie/selections/20261028-testuser" in submit.args[1]
    assert "margie_sb.resume: true" in submit.args[1]
    assert job_store.get(resp.json()["job_id"])["relaunched_from"] == jid


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh.job_runner")
def test_run_again_refuses_a_name_that_is_not_a_genome(mock_runner, mock_conn, api):
    jid = _ended_job()
    resp = api.post(f"/v1/ssh/resume_job/{jid}", json={"genomes": ["../../etc"]})
    assert resp.status_code == 400
    mock_runner.submit_job.assert_not_called()


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh.job_runner")
@patch("bioinformatics_tools.api.routers.ssh.ssh_sftp")
def test_a_genome_without_its_file_in_the_run_folder_is_refused(mock_sftp, mock_runner, mock_conn, api):
    mock_sftp.read_remote_yaml.return_value = dict(CONFIG)
    _quiet(mock_conn, b"")
    jid = _ended_job()
    resp = api.post(f"/v1/ssh/resume_job/{jid}", json={"genomes": [G]})
    assert resp.status_code == 400
    assert ".margie-input" in resp.json()["detail"]
    mock_runner.submit_job.assert_not_called()


def test_the_copy_of_chosen_genomes_copies_only_theirs(tmp_path):
    src, dst = tmp_path / "run1", tmp_path / "run2"
    for rel in (f"{G}/cog/cog.tsv", f"original_container_outputs/{G}/cog/x.txt",
                "other--fa1:00000000/cog/cog.tsv", "original_container_outputs/other--fa1:00000000/y.txt",
                f"original_container_outputs/{G}/stage/big.bin", f"{G}/.snakemake/log"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(f"{src}/{rel}\n")
    script = ssh_slurm.build_copy_script(str(src), str(dst), python="python3",
                                         only=[G, f"original_container_outputs/{G}", "absent--fa1:11111111"])
    run = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "SLURM_CPUS_PER_TASK": "2"})
    assert run.returncode == 0, run.stdout + run.stderr
    got = sorted(str(p.relative_to(dst)) for p in dst.rglob("*") if p.is_file())
    assert got == [f"{G}/cog/cog.tsv", f"original_container_outputs/{G}/cog/x.txt"]
    assert (dst / G / "cog" / "cog.tsv").read_text() == f"{dst}/{G}/cog/cog.tsv\n"


@pytest.mark.parametrize("bad", ["/etc", "../x", "a/../../b", "x\ny"])
def test_the_copy_refuses_paths_outside_the_run_folder(bad):
    with pytest.raises(ValueError):
        ssh_slurm.build_copy_script("/s/run1", "/s/run2", only=[bad])
