"""Stopping a database copy (user_stores.stop): its SLURM job cancelled or its script ended where it
runs, only the half-copied items removed, nothing applied to the settings."""

import subprocess
from unittest.mock import patch

import pytest

from bioinformatics_tools.api.services import user_stores
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

ROOT = "/scratch/c/u/margie-databases"


def _stop(op, after=None):
    """Runs stop() against a stand-in cluster; returns (commands run, files written)."""
    ran, wrote = [], {}
    reads = iter([op, after if after is not None else {**op, "state": "stopped"}])
    with patch.object(user_stores, "scratch_root", return_value=ROOT), \
            patch.object(user_stores, "_read_op", side_effect=lambda *a: next(reads)), \
            patch.object(user_stores, "_run", side_effect=lambda conn, cmd, timeout=60: ran.append(cmd) or (0, "")), \
            patch.object(user_stores.ssh_sftp, "write_remote_text_file", side_effect=lambda path, text, connection: wrote.update({path: text})):
        result = user_stores.stop(object(), {})
    return ran, wrote, result


def test_a_slurm_copy_is_cancelled_and_waited_for():
    ran, wrote, result = _stop({"state": "running", "job": "4242", "op": "setup"})
    assert ran[0].startswith("scancel 4242;") and "squeue -h -j 4242" in ran[0]
    assert "state=stopped" in wrote[f"{ROOT}/.margie/op.status"] and "op=setup" in wrote[f"{ROOT}/.margie/op.status"]
    assert result["state"] == "stopped"


def test_a_queued_copy_can_be_stopped_too():
    ran, _, _ = _stop({"state": "queued", "job": "77", "slurm_state": "PENDING"})
    assert ran[0].startswith("scancel 77;")


def test_a_login_node_copy_is_ended_with_its_rsync():
    ran, _, _ = _stop({"state": "running", "pid": "5150", "host": "login03.cluster"})
    kill = ran[0]
    assert "kill -TERM -- -5150" in kill and "kill -0 5150" in kill
    # On another login node, it is ended there.
    assert "ssh -o BatchMode=yes -o ConnectTimeout=10 login03.cluster" in kill


def test_nothing_to_stop():
    with patch.object(user_stores, "scratch_root", return_value=ROOT), \
            patch.object(user_stores, "_read_op", return_value={"state": "done"}):
        with pytest.raises(user_stores.StoreError) as e:
            user_stores.stop(object(), {})
    assert e.value.status == 409


def test_only_the_half_copied_items_are_removed(tmp_path):
    state = tmp_path / ".margie"
    state.mkdir()
    done_db, half_db = tmp_path / "sqlite" / "u-base-v1.db", tmp_path / "pool" / "u-pool-v1"
    done_db.parent.mkdir()
    half_db.parent.mkdir()
    done_db.write_text("finished copy")
    (tmp_path / "sqlite" / "u-base-v1.db.partial").write_text("left from an earlier try")
    (half_db.parent / "u-pool-v1.partial").mkdir()
    (half_db.parent / "u-pool-v1.partial" / "a.fna").write_text(">a\n")
    (state / "op.plan").write_text(
        f"mkdir\t{tmp_path}/out\n"
        f"copy\tMARGIE database\t/depot/base.db\t{done_db}\t100\n"
        f"files\tGenome pool\t/depot/pool\t{half_db}\t50\ta.fna,b.fna\n"
    )
    (state / "op.after.json").write_text("{}")
    (state / "op.log").write_text("== MARGIE database\n")
    ran, _, _ = _stop({"state": "running", "job": "1"})
    cleanup = ran[1].replace(f"cd {user_stores.shlex.quote(ROOT + '/.margie')}", f"cd {state}")
    subprocess.run(["bash", "-c", cleanup], check=True)
    assert done_db.read_text() == "finished copy"
    assert not (tmp_path / "sqlite" / "u-base-v1.db.partial").exists()
    assert not (half_db.parent / "u-pool-v1.partial").exists()
    assert not (state / "op.after.json").exists()
    assert (state / "op.log").read_text().endswith("== stopped\n")


def test_the_page_can_stop_it(authed_client):  # noqa: F811
    with patch("bioinformatics_tools.api.routers.ssh._build_connection"), \
            patch("bioinformatics_tools.api.routers.ssh._stores_user_config", return_value={}), \
            patch.object(user_stores, "stop", return_value={"state": "stopped", "percent": 40.0, "log": []}) as stop:
        r = authed_client.post("/v1/ssh/stores/stop")
    assert r.status_code == 200 and r.json()["op"]["state"] == "stopped"
    stop.assert_called_once()
