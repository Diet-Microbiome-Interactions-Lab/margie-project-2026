"""A run keeps going when the MARGIE database is busy (workflow._safely), its log leaves out Snakemake's
scheduler chatter (workflow._chatter), and a reattach replays only the log's end (ssh_slurm.REPLAY_BYTES)."""

import sqlite3
from pathlib import Path

from bioinformatics_tools.utilities import ssh_slurm
from bioinformatics_tools.workflow_tools import output_cache
from bioinformatics_tools.workflow_tools.workflow import _FAILED, _chatter, _safely


def test_a_locked_database_is_logged_and_the_run_goes_on(caplog):
    def locked():
        raise sqlite3.OperationalError('database is locked')

    assert _safely('output cache store', locked) is _FAILED
    assert 'output cache store failed' in caplog.text


def test_a_read_that_works_returns_its_result():
    assert _safely('read', lambda a, b=0: a + b, 2, b=3) == 5
    assert _safely('read', lambda: None) is None


def test_scheduler_chatter_is_left_out():
    for line in ('Status query timing: 0.01 s', 'Resources before job selection: {...}',
                 'Ready jobs: 12', 'Selected jobs: 3', 'Select jobs to execute...',
                 'Solving job selection', 'Waiting for running jobs to complete.', 'Execute 3 jobs...'):
        assert _chatter(line), line


def test_steps_progress_job_ids_and_errors_go_through():
    for line in ('rule run_rasttk:', '12 of 340 steps (4%) done', 'Submitted job 7 with external jobid 123456.',
                 'Error in rule run_pfam:', '=== STAGE 2: genome 1/3 (g1) phase4-12 starting, up to 3 at a time ==='):
        assert not _chatter(line), line


def test_a_reattach_replays_at_most_twenty_megabytes():
    assert ssh_slurm.REPLAY_BYTES == 20_000_000
    src = Path(ssh_slurm.__file__).read_text()
    assert "tail -c {REPLAY_BYTES} -F {log}" in src
    assert 'tail -n +1 -F' not in src


def test_the_cache_waits_two_minutes_for_the_lock(tmp_path):
    conn = output_cache._get_connection(str(tmp_path / 'm.db'))
    try:
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 120_000
    finally:
        conn.close()
