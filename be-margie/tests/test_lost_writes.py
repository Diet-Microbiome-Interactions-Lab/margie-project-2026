"""A run's lost writes to the MARGIE database, read from its log and written again (lost_writes.py,
workflow.py's _rewrite_lost_writes)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from bioinformatics_tools.workflow_tools import workflow
from bioinformatics_tools.workflow_tools.lost_writes import lost_writes
from bioinformatics_tools.workflow_tools.workflow import WorkflowBase

LOG = """\
[16:59:05 INFO w] - Phase4+ cache restore for gB--fa1:bbbbbbbb: {'cog': True, 'interpro': False} (merged tables x)
[17:36:56 WARNING w] - Protein cache store failed for gA--fa1:aaaaaaaa / kegg: database is locked
[17:37:00 WARNING w] - Protein cache store failed for gA--fa1:aaaaaaaa / pfam: database is locked
[17:38:59 WARNING w] - Caching the rest of gB--fa1:bbbbbbbb failed (the run goes on without it): database is locked
[03:04:40 WARNING w] - Caching cog for gA--fa1:aaaaaaaa failed (the run goes on without it): database is locked
[03:05:00 WARNING w] - Caching GTDB-Tk for gA--fa1:aaaaaaaa failed (the run goes on without it): database is locked
[03:15:26 WARNING w] - Recording the proteins of gA--fa1:aaaaaaaa failed (the run goes on without it): database is locked
"""


def test_the_log_s_lost_writes_by_genome():
    lost = lost_writes(LOG)
    assert set(lost) == {'gA--fa1:aaaaaaaa', 'gB--fa1:bbbbbbbb'}
    a, b = lost['gA--fa1:aaaaaaaa'], lost['gB--fa1:bbbbbbbb']
    assert (a.proteins, a.results, a.every, a.records) == ({'kegg', 'pfam'}, {'cog'}, False, True)
    assert (b.proteins, b.every, b.restored) == (set(), True, {'cog'})


def test_the_lost_writes_are_written_again_from_the_finished_run_s_folders(tmp_path):
    run = tmp_path / 'run'
    log = tmp_path / 'run.log'
    log.write_text(LOG)
    # A finished run: the step folders under per-tool-phased-output/.
    for genome in ('gA--fa1:aaaaaaaa', 'gB--fa1:bbbbbbbb'):
        for tool in ('cog', 'interpro'):
            folder = run / genome / 'per-tool-phased-output' / tool
            folder.mkdir(parents=True)
            (folder / f'{tool}_results.tsv').write_text('x\n')
    wf = WorkflowBase.__new__(WorkflowBase)
    wf.conf = {}
    wf.failed = MagicMock()
    wf.succeeded = MagicMock()
    genome_files = {'gA--fa1:aaaaaaaa': '/in/gA.fna', 'gB--fa1:bbbbbbbb': '/in/gB.fna'}

    def cache_map(genome):
        top = f'{run.resolve()}/{genome}/'
        return {t: [f'{top}{t}/{t}_results.tsv'] for t in ('cog', 'interpro')}

    with patch.object(workflow.protein_cache, 'store', return_value=3) as proteins, \
            patch.object(workflow, 'store') as results, \
            patch.object(workflow.protein_cache, 'record_fingerprints') as prints, \
            patch.object(workflow.protein_cache, 'record_proteins') as records, \
            patch.object(workflow, 'fasta_hashes', return_value=['fa1:' + 'a' * 64]), \
            patch.object(workflow, 'gene_hashes', return_value={}), \
            patch.object(workflow, 'merged_inputs_fingerprint', return_value='m'):
        rc = wf._rewrite_lost_writes(str(log), {'main_database': '/db', 'output_dir': str(run)},
                                     genome_files, cache_map, set())

    assert rc == 0
    ptp = f'{run.resolve()}/gA--fa1:aaaaaaaa/per-tool-phased-output/'
    assert [(c.args[3], c.args[2]) for c in proteins.call_args_list] == [('kegg', ptp), ('pfam', ptp)]
    # gA's cog, and gB's results but cog, which came back from the cache in that run.
    assert sorted((c.args[2], c.args[3][0].split('/')[-4]) for c in results.call_args_list) == [
        ('cog', 'gA--fa1:aaaaaaaa'), ('interpro', 'gB--fa1:bbbbbbbb')]
    assert all('per-tool-phased-output' in c.args[3][0] for c in results.call_args_list)
    # GTDB-Tk's batch is not rewritten here; gA's records are.
    assert prints.call_count == 1 and records.call_count == 1
    assert records.call_args.args[1] == f'{ptp}labeling/labeled-genes.tsv'
    wf.succeeded.assert_called_once()
