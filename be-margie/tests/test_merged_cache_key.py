"""Consolidation and labeling are cached under a fingerprint of the tool tables they merge
(workflow.merged_inputs_fingerprint), so a run with a different tool set, or with a tool's
changed output, reruns them instead of bringing back a merge of other tables."""

from unittest.mock import patch

from bioinformatics_tools.workflow_tools import workflow as w
from tests.test_workflow import _fake_launchers, wf  # noqa: F401 (fixture)


def _genome(root, tables: dict):
    for tool, text in tables.items():
        name = 'rast.tsv' if tool == 'rasttk' else f'{tool}_results.tsv'
        (root / tool).mkdir(parents=True, exist_ok=True)
        (root / tool / name).write_text(text)
    (root / 'genome_info').mkdir(exist_ok=True)
    (root / 'genome_info' / 'genome_info.tsv').write_text('GTDBTK_domain\nBacteria\n')
    return str(root)


def test_the_same_tables_give_the_same_key(tmp_path):
    a = _genome(tmp_path / 'a', {'rasttk': 'r', 'pfam': 'p', 'cog': 'c'})
    b = _genome(tmp_path / 'b', {'rasttk': 'r', 'pfam': 'p', 'cog': 'c'})
    assert w.merged_inputs_fingerprint(a) == w.merged_inputs_fingerprint(b)


def test_another_tool_or_another_output_changes_it(tmp_path):
    base = w.merged_inputs_fingerprint(_genome(tmp_path / 'a', {'rasttk': 'r', 'pfam': 'p'}))
    assert w.merged_inputs_fingerprint(_genome(tmp_path / 'b', {'rasttk': 'r', 'pfam': 'p', 'kegg': 'k'})) != base
    assert w.merged_inputs_fingerprint(_genome(tmp_path / 'c', {'rasttk': 'r', 'pfam': 'p2'})) != base


def test_what_consolidation_does_not_read_does_not_count(tmp_path):
    root = tmp_path / 'a'
    before = w.merged_inputs_fingerprint(_genome(root, {'rasttk': 'r', 'pfam': 'p'}))
    (root / 'consolidation').mkdir()
    (root / 'consolidation' / 'consolidated-merged-all-columns.tsv').write_text('old merge')
    (root / 'scoring').mkdir()
    (root / 'scoring' / 'scoring_results.tsv').write_text('x')
    assert w.merged_inputs_fingerprint(str(root)) == before


def test_only_consolidation_and_labeling_are_keyed_by_their_inputs():
    assert w.cache_name('consolidation@abc', 'f1') == 'consolidation@abc#f1'
    assert w.cache_name('labeling@def', 'f1') == 'labeling@def#f1'
    assert w.cache_name('pfam', 'f1') == 'pfam'


@patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
@patch('bioinformatics_tools.workflow_tools.workflow.locate_local_sif_files')
@patch('bioinformatics_tools.workflow_tools.workflow.time.sleep')
def test_a_run_restores_the_tools_first_and_stores_merges_under_their_tables(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out = tmp_path / 'run'
    db = tmp_path / 'margie.db'
    db.write_text('')
    g = out / 'g1'
    _genome(g, {'rasttk': 'r', 'pfam': 'p'})
    (g / 'rasttk' / 'rasttk_db.tkn').write_text('')
    merged = [f'{g}/consolidation/consolidated-merged-all-columns.tsv']
    cache_map = lambda s: {'pfam': [f'{g}/pfam/pfam_results.tsv'], 'consolidation@abc': merged}
    calls, stored = [], []

    def fake_restore_all(db_path, genome_file, mapping, **kw):
        calls.append(list(mapping))
        return {k: k == 'pfam' for k in mapping}

    def fake_store(db_path, genome_file, name, paths, **kw):
        stored.append(name)

    def fake_stage2(cmd):  # Stage 2 writes the merge
        (g / 'consolidation').mkdir(exist_ok=True)
        (g / 'consolidation' / 'consolidated-merged-all-columns.tsv').write_text('merged')

    with patch.object(wf, '_restore_gene_calls', return_value=({}, {})), \
            patch(f'{w.__name__}.restore', return_value=False), \
            patch(f'{w.__name__}.restore_all', side_effect=fake_restore_all), \
            patch(f'{w.__name__}.cached_when', return_value={}), \
            patch(f'{w.__name__}.store', side_effect=fake_store), \
            patch(f'{w.__name__}.store_all', side_effect=lambda db_path, f, m, **kw: stored.extend(m)), \
            patch(f'{w.__name__}.log_workflow_run'), \
            patch(f'{w.__name__}.is_already_processed', return_value=False), patch(f'{w.__name__}.fasta_hashes', return_value='h'), \
            patch(f'{w.__name__}.current_rast_genome_id', return_value=None), \
            patch(f'{w.__name__}.protein_cache.enabled', return_value=False), \
            _fake_launchers(wf) as rec:
        fake_stage2(None)
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'main_database': str(db), 'run_gtdbtk': False},
                                          {'g1': '/g1.fa'}, cache_map_fn=cache_map, mode='dev')
    fp = w.merged_inputs_fingerprint(str(g))
    assert calls[0] == ['pfam']                                   # the tools first
    assert calls[1] == [f'consolidation@abc#{fp}']                # then the merge, keyed by its tables
    assert f'consolidation@abc#{fp}' in stored and 'consolidation@abc' not in stored
