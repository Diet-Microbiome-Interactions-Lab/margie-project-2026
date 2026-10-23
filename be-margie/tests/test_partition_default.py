"""A cluster that marks no default partition refuses a job without one, so an empty partition setting
takes the cluster's default (else cpu); a copy job SLURM refuses says so instead of waiting forever."""

from unittest.mock import patch

import pytest

from bioinformatics_tools.api.services import user_stores as us


def _sinfo(out):
    return patch.object(us, "_run", return_value=(0, out))


def test_the_marked_default_partition_is_taken():
    with _sinfo("cms\ncpu\nshared*\ngpu\n"):
        assert us.default_partition(None) == "shared"


def test_cpu_is_taken_when_none_is_marked():
    with _sinfo("cms\ncpu\ngpu\nhighmem\nlogin\nprofiling\n"):
        assert us.default_partition(None) == "cpu"


def test_an_empty_setting_is_filled_and_a_chosen_one_kept():
    cfg = {"compute": {"cluster_default": {"account": "lab", "partition": ""}}}
    with _sinfo("cpu\ngpu\n"):
        assert us.fill_default_partition(None, cfg)
        assert cfg["compute"]["cluster_default"]["partition"] == "cpu"
        cfg["compute"]["cluster_default"]["partition"] = "highmem"
        assert not us.fill_default_partition(None, cfg)
    assert cfg["compute"]["cluster_default"]["partition"] == "highmem"


def test_a_wait_with_no_slurm_job_behind_it_reads_as_failed():
    op = us._op_from({"status": ["state=queued", "op=setup", "label=Waiting for a SLURM slot"]}, "/r")
    assert op["state"] == "failed" and "no SLURM job behind it" in op["message"]


def test_a_refused_copy_job_is_said_on_the_page():
    written = {}
    runs = []

    def run(conn, cmd, timeout=60.0):
        runs.append(cmd)
        if cmd.startswith("sinfo"):
            return 0, "cpu\ngpu\n"
        if "sbatch" in cmd:
            return 1, "sbatch: error: Batch job submission failed: Invalid account"
        return 0, ""

    cfg = {"compute": {"cluster_default": {"account": "lab"}}}
    with patch.object(us, "_run", side_effect=run), \
            patch.object(us.ssh_sftp, "write_remote_text_file", side_effect=lambda p, t, connection=None: written.update({p: t})):
        with pytest.raises(us.StoreError, match="Invalid account"):
            us._start(None, "/r", "setup", [["mkdir", "/r/x"]], {}, cfg)
    assert any("--partition=cpu" in c for c in runs if "sbatch" in c)
    status = written["/r/.margie/op.status"]
    assert "state=failed" in status and "Invalid account" in status
