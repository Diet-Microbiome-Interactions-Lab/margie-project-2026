"""
Unit tests for the log parsing in bioinformatics_tools.api.services.job_runner.
"""
from bioinformatics_tools.api.services.job_runner import (
    SLURM_SUBMIT_RE, RULE_NAME_FROM_LOG_PATH_RE, SEQUENTIAL_GENOME_RE)


class TestSlurmSubmitRegex:
    """Tests SLURM_SUBMIT_RE (slurm_id, log_path) and RULE_NAME_FROM_LOG_PATH_RE applied
    to the log path, the two-step extraction used in run_ssh_task."""

    def test_captures_slurm_id_and_full_log_path(self):
        line = (
            "SLURM jobid 39603778 (log: /path/.snakemake/slurm_logs/"
            "rule_run_quast_batch/39603778.log)."
        )
        slurm_id, log_path = SLURM_SUBMIT_RE.search(line).groups()
        assert slurm_id == "39603778"
        assert log_path == "/path/.snakemake/slurm_logs/rule_run_quast_batch/39603778.log"

    def test_ungrouped_rule_captures_full_rule_name(self):
        log_path = "/path/.snakemake/slurm_logs/rule_run_quast_batch/39603778.log"
        rule_name, group_name = RULE_NAME_FROM_LOG_PATH_RE.search(log_path).groups()
        assert rule_name == "run_quast_batch"
        assert group_name is None

    def test_grouped_rule_captures_only_the_short_group_name(self):
        """Checks that a grouped job shows the group's short name ("rasttk"), not the
        concatenated rule names Snakemake generates."""
        log_path = "/path/.snakemake/slurm_logs/group_rasttk_load_rasttk_to_db_run_rasttk/39608085.log"
        rule_name, group_name = RULE_NAME_FROM_LOG_PATH_RE.search(log_path).groups()
        assert rule_name is None
        assert group_name == "rasttk"

    def test_grouped_rule_kegg(self):
        log_path = "/path/.snakemake/slurm_logs/group_kegg_load_kegg_to_db_run_kegg/39607504.log"
        rule_name, group_name = RULE_NAME_FROM_LOG_PATH_RE.search(log_path).groups()
        assert rule_name is None
        assert group_name == "kegg"

    def test_displayed_name_resolution_prefers_rule_over_group(self):
        """Mirrors the `rule_name or group_name` expression in run_ssh_task."""
        ungrouped_path = "/p/.snakemake/slurm_logs/rule_run_quast_batch/1.log"
        grouped_path = "/p/.snakemake/slurm_logs/group_rasttk_load_rasttk_to_db_run_rasttk/2.log"

        rule_name, group_name = RULE_NAME_FROM_LOG_PATH_RE.search(ungrouped_path).groups()
        assert (rule_name or group_name) == "run_quast_batch"

        rule_name, group_name = RULE_NAME_FROM_LOG_PATH_RE.search(grouped_path).groups()
        assert (rule_name or group_name) == "rasttk"

    def test_real_full_line_with_uuid_jobid_prefix(self):
        """Checks a real log line where the Snakemake jobid of a group job is a UUID."""
        line = (
            "[2026-06-23 04:53:32] INFO bioinformatics_tools.workflow_tools.workflow: "
            "[snakemake] Job f2bd3300-d2be-5a07-91a9-b299cb448c4f has been submitted "
            "with SLURM jobid 39684417 (log: /scratch/cluster/user/margie/output/"
            "2026-06-23-0453/.snakemake/slurm_logs/"
            "group_rasttk_load_rasttk_to_db_run_rasttk/39684417.log)."
        )
        slurm_id, log_path = SLURM_SUBMIT_RE.search(line).groups()
        assert slurm_id == "39684417"
        rule_name, group_name = RULE_NAME_FROM_LOG_PATH_RE.search(log_path).groups()
        assert (rule_name or group_name) == "rasttk"


class TestSequentialGenomeRegex:
    """Tests the per-genome marker line printed by workflow.py's _run_pipeline_batch_sequential."""

    def test_matches_marker_line(self):
        line = "=== SEQUENTIAL: genome 3/12 (Genus_species) phase4-8 starting ==="
        match = SEQUENTIAL_GENOME_RE.search(line)
        assert match is not None
        assert match.groups() == ("3", "12")

    def test_no_match_on_unrelated_line(self):
        line = "5 of 20 steps (25%) done"
        assert SEQUENTIAL_GENOME_RE.search(line) is None


class TestResumeCopyPhase:
    """A Resume's copy job writes the run's log before the driver starts: the copy settings reach
    the launch, and the run's phase says the earlier results are being copied."""

    def test_the_copy_reaches_the_launch_and_shows_as_a_phase(self):
        from unittest.mock import MagicMock, patch

        from bioinformatics_tools.api.services import job_runner, run_mail
        from bioinformatics_tools.api.services.job_store import job_store

        job_store.create('copy-1', '/g', user_id=7)
        seen = []

        def lines(**kw):
            seen.append(kw)
            yield '__LAUNCHED__'
            yield "Resume: copying the earlier run's folder /a into /b, 16 folders at a time, on a001"
            seen.append(job_store.get('copy-1')['phase'])
            yield 'Resume: done in 3 min; the run starts next'
            seen.append(job_store.get('copy-1')['phase'])
            yield '__EXIT_CODE__:0'

        with patch.object(job_runner.ssh_slurm, 'submit_ssh_job', side_effect=lines), \
                patch.object(job_runner, '_slurm_status_checker'), patch.object(run_mail, 'notify'):
            job_runner.run_ssh_task('copy-1', 'dane_wf margie sb', MagicMock(), copy_from='/a', copy_to='/b')

        assert seen[0]['copy_from'] == '/a' and seen[0]['copy_to'] == '/b'
        assert seen[1:] == ["Copying the earlier run's results", 'Starting the run']
