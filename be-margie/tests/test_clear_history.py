"""Clearing the job list (job_history.clear_jobs): the owner's finished jobs go into a backup
file first and are then removed; a job still going and other users' jobs stay."""

import sqlite3

import pytest

from bioinformatics_tools.api.services import job_history as jh


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "margie.db")
    jh.ensure_table(path)
    for job_id, owner, status in [("a1", "ada", "completed"), ("a2", "ada", "failed"),
                                  ("a3", "ada", "running"), ("b1", "someone", "completed")]:
        jh.record_job_created(path, job_id, "margie_sb", None, f"/scratch/c/{owner}/out", owner, owner)
        jh.record_job_updated(path, job_id, status=status)
    return path


def _ids(path):
    return sorted(r[0] for r in sqlite3.connect(path).execute("SELECT job_id FROM api_jobs"))


def test_finished_jobs_are_backed_up_then_removed(db, tmp_path):
    backup = str(tmp_path / "backups" / "job-history-1.db")
    out = jh.clear_jobs(db, backup, "ada", "ada")
    assert out == {"backup": backup, "removed": 2, "kept": 1}
    assert _ids(db) == ["a3", "b1"]
    assert _ids(backup) == ["a1", "a2"]


def test_nothing_to_clear_leaves_no_backup(db, tmp_path):
    jh.clear_jobs(db, str(tmp_path / "first.db"), "ada", "ada")
    second = tmp_path / "second.db"
    assert jh.clear_jobs(db, str(second), "ada", "ada") == {"backup": "", "removed": 0, "kept": 1}
    assert not second.exists()


def test_an_existing_backup_is_never_overwritten(db, tmp_path):
    backup = tmp_path / "taken.db"
    backup.write_text("")
    with pytest.raises(ValueError):
        jh.clear_jobs(db, str(backup), "ada", "ada")
    assert _ids(db) == ["a1", "a2", "a3", "b1"]
