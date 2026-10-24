"""A run's cache report (workflow_tools/cache_report.py): for each genome and step, whether its
results were restored from the MARGIE database (genome or protein level), run fresh, partly
each, kept from an earlier attempt, or not run; written to <output_dir>/cache-report.tsv."""

import csv
from unittest.mock import patch

from bioinformatics_tools.workflow_tools import cache_report as cr
from tests.test_workflow import _fake_launchers, wf  # noqa: F401 (fixture)

DB = '/scratch/c/u/margie/margie-databases/sqlite/u-base-v1.db'


def _rows(path):
    with open(path) as fh:
        return {(r['genome'], r['step']): r for r in csv.DictReader(fh, delimiter='\t')}


def test_protein_level_counts_read_as_restored_partly_or_fresh():
    assert cr.proteins(3904, 0) == {'source': cr.RESTORED, 'level': cr.PROTEIN_LEVEL,
                                    'detail': 'all 3,904 proteins from the protein cache'}
    partly = cr.proteins(812, 3092)
    assert partly['source'] == cr.PARTLY and partly['level'] == cr.PROTEIN_LEVEL
    assert partly['detail'] == '812 of 3,904 proteins from the protein cache; 3,092 annotated now'
    assert cr.proteins(0, 50)['source'] == cr.FRESH and 'level' not in cr.proteins(0, 50)


def test_rows_say_their_stage_and_only_cached_ones_name_the_database(tmp_path):
    r = cr.CacheReport(str(tmp_path), DB)
    r.set('g1', 'gtdbtk', cr.RESTORED, 'same genome', '2026-10-01T10:00:00+00:00', cr.GENOME_LEVEL)
    r.set('g1', 'rasttk', cr.FRESH)
    r.set('g1', 'pfam', **cr.proteins(5, 5))
    r.write()
    rows = _rows(tmp_path / cr.FILE)
    assert rows[('g1', 'gtdbtk')]['stage'] == 'before gene calling' and rows[('g1', 'gtdbtk')]['database'] == DB
    assert rows[('g1', 'rasttk')]['stage'] == 'gene calling' and rows[('g1', 'rasttk')]['database'] == ''
    assert rows[('g1', 'pfam')]['stage'] == 'after gene calling' and rows[('g1', 'pfam')]['level'] == 'protein'
    assert rows[('g1', 'gtdbtk')]['cached_at'].startswith('2026-10-01')


def test_a_stopped_run_marks_what_it_did_not_finish(tmp_path):
    r = cr.CacheReport(str(tmp_path), DB)
    r.set('g1', 'cog', cr.RESTORED, 'x', level=cr.GENOME_LEVEL)
    r.set('g1', 'pfam', cr.FRESH)
    r.unfinished('g1')
    assert cr.UNFINISHED in r.rows[('g1', 'pfam')]['detail'] and cr.UNFINISHED not in r.rows[('g1', 'cog')]['detail']


def test_the_log_line_names_each_level_and_the_database():
    r = cr.CacheReport('', DB)
    r.set('g1', 'rasttk', cr.RESTORED, level=cr.GENOME_LEVEL)
    r.set('g1', 'cog', **cr.proteins(9, 0))
    r.set('g1', 'kegg', **cr.proteins(2, 7))
    r.set('g1', 'scoring', cr.FRESH)
    r.set('g1', 'merops', cr.NOT_RUN)
    line = r.summary('g1')
    assert 'restored, genome level: rasttk' in line and 'restored, protein level: cog' in line
    assert 'partly restored, protein level: kegg' in line and 'run fresh: scoring' in line
    assert 'merops' not in line and DB in line


def test_quast_runs_beside_the_pipeline():
    assert cr.stage_of('quast') == 'beside the pipeline'
    assert cr.stage_of('gtdbtk') == 'before gene calling'


def test_no_folder_no_file():
    cr.CacheReport('', DB).write()  # nothing to write to, and no error


@patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
@patch('bioinformatics_tools.workflow_tools.workflow.locate_local_sif_files')
@patch('bioinformatics_tools.workflow_tools.workflow.time.sleep')
def test_a_run_writes_where_each_step_came_from(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out = tmp_path / 'run'
    db = tmp_path / 'margie.db'
    db.write_text('')
    g = out / 'g1'
    (g / 'rasttk').mkdir(parents=True)
    (g / 'rasttk' / 'rasttk_db.tkn').write_text('')
    (g / 'rasttk' / 'rast.faa').write_text('>p1\nMK\n')
    w = 'bioinformatics_tools.workflow_tools.workflow'
    cache_map = lambda s: {t: [f'{out}/{s}/{t}/{t}_results.tsv'] for t in ('cog', 'pfam', 'kegg', 'merops')} | {
        'consolidation@abc': [f'{out}/{s}/consolidation/x.tsv']}
    restored = {'cog': True, 'pfam': False, 'kegg': False, 'merops': False, 'consolidation@abc': True}
    with patch.object(wf, '_restore_gene_calls', return_value=({'g1': True}, {'g1': True})), \
            patch(f'{w}.restore', return_value=True), \
            patch(f'{w}.restore_all', side_effect=lambda db_path, f, m: {k: restored.get(k.split('#')[0], False) for k in m}), \
            patch(f'{w}.cached_when', return_value={'gtdbtk': '2026-09-01T00:00:00+00:00', 'cog': '2026-09-02T00:00:00+00:00'}), \
            patch(f'{w}.store'), patch(f'{w}.store_all'), patch(f'{w}.log_workflow_run'), \
            patch(f'{w}.is_already_processed', return_value=False), patch(f'{w}.fasta_hashes', return_value='h'), \
            patch(f'{w}.current_rast_genome_id', return_value=None), \
            patch(f'{w}.protein_cache.enabled', return_value=True), \
            patch(f'{w}.protein_cache.split', return_value={'pfam': (40, 0), 'kegg': (10, 30)}), \
            patch(f'{w}.protein_cache.store', return_value=0), patch(f'{w}.protein_cache.clear'), \
            _fake_launchers(wf):
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'main_database': str(db), 'run_merops': False},
                                          {'g1': '/g1.fa'}, cache_map_fn=cache_map, mode='dev')
    rows = _rows(out / cr.FILE)
    assert rows[('g1', 'gtdbtk')]['source'] == 'restored' and rows[('g1', 'gtdbtk')]['level'] == 'genome'
    assert rows[('g1', 'gtdbtk')]['cached_at'].startswith('2026-09-01') and rows[('g1', 'gtdbtk')]['database'] == str(db)
    assert rows[('g1', 'rasttk')]['source'] == 'restored' and rows[('g1', 'rasttk')]['stage'] == 'gene calling'
    assert rows[('g1', 'cog')]['source'] == 'restored' and rows[('g1', 'cog')]['level'] == 'genome'
    assert rows[('g1', 'consolidation')]['source'] == 'restored'
    assert rows[('g1', 'pfam')]['source'] == 'restored' and rows[('g1', 'pfam')]['level'] == 'protein'
    assert rows[('g1', 'kegg')]['source'] == 'partly restored' and '10 of 40 proteins' in rows[('g1', 'kegg')]['detail']
    assert rows[('g1', 'merops')]['source'] == 'not run'
    assert rows[('g1', 'scoring')]['source'] == 'fresh'
