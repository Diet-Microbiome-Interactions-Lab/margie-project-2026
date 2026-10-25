"""A run keeps going when the MARGIE database is busy (workflow._safely), its log leaves out Snakemake's
scheduler chatter (workflow._chatter), the follow leaves it out on the cluster
(ssh_slurm.LOG_CHATTER), and the API joins log lines when a job is read (job_store)."""

import re
import sqlite3
from pathlib import Path

from bioinformatics_tools.api.services.job_store import JobStore
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


def test_the_follow_leaves_chatter_out_on_the_cluster():
    src = Path(ssh_slurm.__file__).read_text()
    assert "tail -n +1 -F {log} 2>/dev/null | grep --line-buffered -vE '{LOG_CHATTER}'" in src
    pattern = re.compile(ssh_slurm.LOG_CHATTER.replace('[[:space:]]', r'\s'))
    prefix = '[10:12:01 INFO bioinformatics_tools.workflow_tools.workflow] - [snakemake] '
    for line in ('Ready jobs: 11', 'Selected jobs: 0', 'Waiting for running jobs to complete.',
                 "Resources before job selection: {'margie_sb_phase4_slot': 4}", 'Execute 2 jobs...'):
        assert pattern.search(prefix + line), line
    for line in ('Job 7 has been submitted with SLURM jobid 44647986 (log: /x/slurm_logs/rule_run_pfam/g1/1.log).',
                 '12 of 340 steps (4%) done', 'Error in rule run_pfam:', 'localrule resolve_genome_info:'):
        assert not pattern.search(prefix + line), line


def test_log_lines_are_joined_when_the_job_is_read():
    store = JobStore()
    store.create('j1', '/g')
    store.update('j1', logs='')
    for i in range(3):
        store.append_log('j1', f'line {i}')
    assert store.get('j1')['logs'] == 'line 0\nline 1\nline 2\n'
    store.append_log('j1', 'line 3')
    store.update('j1', logs='fresh\n')
    store.append_log('j1', 'after')
    assert store.get('j1')['logs'] == 'fresh\nafter\n'


def test_the_cache_waits_two_minutes_for_the_lock(tmp_path):
    conn = output_cache._get_connection(str(tmp_path / 'm.db'))
    try:
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 120_000
    finally:
        conn.close()
