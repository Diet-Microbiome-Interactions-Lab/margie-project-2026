"""The job history lives in the working folder: the records in <working>/job-history, each job's run
files in job-history/jobs (~/.local/share/bsp/jobs points there), and a cleared history's backups in
job-history/backups. The shell parts run here in a home of their own, with squeue stubbed."""

import os
import sqlite3
import subprocess
from unittest.mock import patch

from bioinformatics_tools.api.services import job_history, user_stores
from bioinformatics_tools.utilities import ssh_slurm


def _shell(cmd: str, home, jobs: str = ""):
    """Runs cmd with HOME=home and a squeue that lists `jobs`."""
    bin_ = home / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "squeue").write_text(f"#!/bin/sh\nprintf '%s' '{jobs}'\n")
    (bin_ / "squeue").chmod(0o755)
    env = {**os.environ, "HOME": str(home), "USER": "u", "PATH": f"{bin_}:{os.environ['PATH']}"}
    return subprocess.run(["bash", "-c", cmd], env=env, capture_output=True, text=True)


def _layout(tmp_path):
    home, working = tmp_path / "home", tmp_path / "scratch" / "margie"
    home.mkdir()
    working.mkdir(parents=True)
    return home, working, working / "job-history" / "jobs", home / ".local" / "share" / "bsp" / "jobs"


def _link(working, jobs):
    return ssh_slurm.link_run_files_sh(str(working), str(jobs))


def test_a_new_account_writes_its_run_files_in_the_working_folder(tmp_path):
    home, working, jobs, j = _layout(tmp_path)
    r = _shell(_link(working, jobs), home)
    assert r.returncode == 0 and r.stdout == ""
    assert j.is_symlink() and os.readlink(j) == str(jobs) and jobs.is_dir()
    # A launch writes through the link.
    _shell(ssh_slurm._RUN_DIR_READY + "echo hi > $HOME/.local/share/bsp/jobs/run1.log", home)
    assert (jobs / "run1.log").read_text() == "hi\n"


def test_run_files_from_before_move_in_only_while_no_job_runs(tmp_path):
    home, working, jobs, j = _layout(tmp_path)
    j.mkdir(parents=True)
    (j / "old.log").write_text("old")
    _shell(_link(working, jobs), home, jobs="12345")
    assert j.is_dir() and not j.is_symlink() and (j / "old.log").exists()
    _shell(_link(working, jobs), home)
    assert j.is_symlink() and (jobs / "old.log").read_text() == "old"


def test_the_link_follows_a_new_working_folder_and_a_vanished_one_gives_way(tmp_path):
    home, working, jobs, j = _layout(tmp_path)
    _shell(_link(working, jobs), home)
    other = tmp_path / "scratch" / "margie-2"
    other.mkdir()
    _shell(_link(other, other / "job-history" / "jobs"), home)
    assert os.readlink(j) == str(other / "job-history" / "jobs")
    # The working folder renamed away: nothing is made where it was, and a launch still has a folder.
    os.rename(other, tmp_path / "scratch" / "margie-3")
    _shell(_link(other, other / "job-history" / "jobs"), home)
    assert not other.exists()
    r = _shell(ssh_slurm._RUN_DIR_READY + "echo x > $HOME/.local/share/bsp/jobs/run2.log", home)
    assert r.returncode == 0 and j.is_dir() and not j.is_symlink()


def test_the_history_records_go_to_the_working_folder_from_the_earlier_file(tmp_path):
    working = tmp_path / "margie"
    (working / "margie-databases" / "sqlite").mkdir(parents=True)
    main = working / "margie-databases" / "sqlite" / "u-margie-v1.db"
    sqlite3.connect(main).close()
    cfg = tmp_path / "config.yaml"
    with patch.object(job_history.getpass, "getuser", return_value="u"):
        # Before: beside the MARGIE database, with one job.
        with patch.object(job_history, "CONFIG", str(tmp_path / "none.yaml")):
            job_history.dispatch("create", {"db_path": str(main), "job_id": "j1", "workflow": "margie_sb"})
        earlier = main.parent / "u-job-history.db"
        assert earlier.exists()
        cfg.write_text(f"margie_sb:\n  working_folder: {working}\n")
        with patch.object(job_history, "CONFIG", str(cfg)):
            assert job_history.history_path(str(main)) == str(working / "job-history" / "u-job-history.db")
            job_history.dispatch("create", {"db_path": str(main), "job_id": "j2", "workflow": "margie_sb"})
            got = job_history.dispatch("list", {"db_path": str(main)})
    ids = {r["job_id"] for r in (got if isinstance(got, list) else got.get("jobs", got.get("rows", [])))}
    assert {"j1", "j2"} <= ids
    assert (working / "job-history" / "u-job-history.db").exists() and earlier.exists()


def test_a_new_working_folder_takes_the_job_history_with_it(tmp_path):
    before, after = tmp_path / "margie", tmp_path / "margie-new"
    (before / "job-history" / "jobs").mkdir(parents=True)
    (before / "job-history" / "u-job-history.db").write_text("db")
    (before / "job-history" / "jobs" / "r.log").write_text("log")
    run = lambda conn, cmd, timeout=60: (lambda r: (r.returncode, r.stdout + r.stderr))(  # noqa: E731
        subprocess.run(["bash", "-c", cmd], capture_output=True, text=True))
    with patch.object(user_stores, "_run", side_effect=run):
        user_stores.carry_job_history(None, str(before), str(after))
        assert (after / "job-history" / "jobs" / "r.log").read_text() == "log"
        assert (before / "job-history" / "u-job-history.db").exists()
        # One already there is left as it is.
        (after / "job-history" / "u-job-history.db").write_text("mine")
        user_stores.carry_job_history(None, str(before), str(after))
    assert (after / "job-history" / "u-job-history.db").read_text() == "mine"


def test_the_slurm_account_is_set_when_there_is_only_one():
    for listing, expected in (("lindems\n", "lindems"), ("lab-a\nlab-b\n", None), ("", None)):
        cfg = {}
        with patch.object(user_stores, "_run", return_value=(0, listing)):
            changed = user_stores.fill_default_account(None, cfg)
        assert changed is (expected is not None)
        assert user_stores._cfg_get(cfg, "compute.cluster_default.account") == expected
    # One chosen in Settings stays.
    cfg = {"compute": {"cluster_default": {"account": "mine"}}}
    with patch.object(user_stores, "_run", return_value=(0, "other\n")):
        assert user_stores.fill_default_account(None, cfg) is False
    assert cfg["compute"]["cluster_default"]["account"] == "mine"
