"""What a run left unwritten in the MARGIE database, read from its log, and made from its folder
with its closing steps (lost_writes.py, workflow.py's _finish_from_log)."""
from unittest.mock import MagicMock, patch

from bioinformatics_tools.workflow_tools import workflow
from bioinformatics_tools.workflow_tools.lost_writes import read_run_log
from bioinformatics_tools.workflow_tools.workflow import WorkflowBase

A, B, C = 'gA--fa1:aaaaaaaa', 'gB--fa1:bbbbbbbb', 'gC--fa1:cccccccc'
LOG = f"""\
[16:57:16 INFO w] - Starting sequential batch workflow "margie_sb" run_id=run-1 genomes=3
[16:59:05 INFO w] - Phase4+ cache restore for {B}: {{'cog': True, 'interpro': False}} (merged tables x)
[16:59:06 INFO w] - Phase4+ cache restore for {C}: {{'cog': False, 'interpro': False}} (merged tables x)
[17:00:00 INFO w] - Starting Stage 2 (phase4_12_one_genome) for {A}: snakemake --rerun-triggers mtime --config cached_gtdbtk={A},{B} cached_rasttk={A}
[17:36:56 WARNING w] - Protein cache store failed for {A} / kegg: database is locked
[17:37:00 WARNING w] - Protein cache store failed for {A} / pfam: database is locked
[17:38:59 WARNING w] - Caching the rest of {B} failed (the run goes on without it): database is locked
[03:04:40 WARNING w] - Caching cog for {A} failed (the run goes on without it): database is locked
[03:05:00 WARNING w] - Caching GTDB-Tk for {A} failed (the run goes on without it): database is locked
[03:15:26 WARNING w] - Recording the proteins of {A} failed (the run goes on without it): database is locked
[03:20:00 INFO w] - === LOADS: {A} loaded: its results are in the MARGIE database ===
[03:21:00 INFO o] - Logged workflow run: margie_sb run_id=run-1 status=success rules_completed=2 (hash fa1:aaaaaaaa...)
[03:22:00 INFO w] - === LOADS: {B} loaded: its results are in the MARGIE database ===
[03:23:00 INFO o] - Logged workflow run: margie_sb run_id=run-1 status=success rules_completed=2 (hash fa1:bbbbbbbb...)
[03:24:00 INFO w] - === LOADS: {C} loaded: its results are in the MARGIE database ===
"""


def test_the_log_s_writes_to_make_by_genome():
    run = read_run_log(LOG)
    assert set(run.lost) == {A, B, C}
    a, b, c = run.lost[A], run.lost[B], run.lost[C]
    assert (a.proteins, a.results, a.every, a.records, a.whole) == ({'kegg', 'pfam'}, {'cog'}, False, True, False)
    assert (b.proteins, b.every, b.restored, b.whole) == (set(), True, {'cog'}, False)
    # gC was loaded but the writer had not reached it: no run log row.
    assert c.whole and c.restored == set()
    assert (run.run_id, run.loaded, run.failed, run.closed) == ('run-1', [A, B, C], [], False)
    assert run.config == {'cached_gtdbtk': f'{A},{B}', 'cached_rasttk': A} and run.rerun_triggers == 'mtime'


def _finish(tmp_path, log_text):
    run = tmp_path / 'run'
    log = tmp_path / 'run.log'
    log.write_text(log_text)
    # gA and gB from a finished run (step folders under per-tool-phased-output/), gC from a stopped one.
    for genome, sub in ((A, 'per-tool-phased-output/'), (B, 'per-tool-phased-output/'), (C, '')):
        for tool in ('cog', 'interpro'):
            folder = run / genome / sub / tool
            folder.mkdir(parents=True)
            (folder / f'{tool}_results.tsv').write_text('x\n')
            (folder / f'{tool}_db.tkn').write_text('')
    wf = WorkflowBase.__new__(WorkflowBase)
    wf.conf = {}
    wf.failed = MagicMock()
    wf.succeeded = MagicMock()
    wf._finalize = MagicMock()
    genome_files = {A: '/in/gA.fna', B: '/in/gB.fna', C: '/in/gC.fna'}

    def cache_map(genome):
        top = f'{run.resolve()}/{genome}/'
        return {t: [f'{top}{t}/{t}_results.tsv'] for t in ('cog', 'interpro')}

    calls = {}
    with patch.object(workflow.protein_cache, 'TOOLS', ['cog', 'interpro']), \
            patch.object(workflow.protein_cache, 'store', return_value=3) as calls['proteins'], \
            patch.object(workflow, 'store') as calls['results'], \
            patch.object(workflow, 'log_workflow_run') as calls['run_log'], \
            patch.object(workflow.protein_cache, 'record_fingerprints') as calls['prints'], \
            patch.object(workflow.protein_cache, 'record_proteins') as calls['records'], \
            patch.object(workflow, 'fasta_hashes', return_value=['fa1:' + 'a' * 64]), \
            patch.object(workflow, 'gene_hashes', return_value={}), \
            patch.object(workflow, 'merged_inputs_fingerprint', return_value='m'):
        rc = wf._finish_from_log(str(log), {'main_database': '/db', 'output_dir': str(run)}, genome_files, cache_map, set())
    return rc, wf, calls, run.resolve()


def test_the_writes_are_made_from_the_run_s_folders_and_the_closing_steps_follow(tmp_path):
    rc, wf, calls, run = _finish(tmp_path, LOG)
    assert rc == 0
    ptp = f'{run}/{A}/per-tool-phased-output/'
    proteins = [(c.args[3], c.args[2], c.kwargs['ran']) for c in calls['proteins'].call_args_list]
    # gA's lost tools; gC's every tool with a database token, from the folder as the stopped run left it.
    assert proteins == [('kegg', ptp, True), ('pfam', ptp, True), ('cog', f'{run}/{C}/', True), ('interpro', f'{run}/{C}/', True)]
    # gA's cog, gB's results but the cog that came back from the cache, and all of gC's.
    assert sorted((c.args[2], c.args[3][0].split('/')[-3 if '/per-tool' not in c.args[3][0] else -4])
                  for c in calls['results'].call_args_list) == [
        ('cog', A), ('cog', C), ('interpro', B), ('interpro', C)]
    # GTDB-Tk's batch is not made here; gC's run log row is, under the run's id.
    assert [c.args[1] for c in calls['run_log'].call_args_list] == ['run-1']
    assert calls['prints'].call_count == 2 and calls['records'].call_count == 2
    # The closing steps get the run's Snakemake settings and its three loaded genomes.
    args = wf._finalize.call_args.args
    assert args[1]['cached_gtdbtk'] == f'{A},{B}' and args[5] == 'mtime' and args[6:] == (3, False, [A, B, C])
    wf.succeeded.assert_called_once()


def test_a_run_that_began_its_closing_steps_does_not_take_them_again(tmp_path):
    _, wf, _, _ = _finish(tmp_path, LOG + '[19:00:00 INFO w] - === FINALIZE: queue background sqlite snapshot backup ===\n')
    wf._finalize.assert_not_called()
