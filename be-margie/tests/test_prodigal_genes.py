"""Prodigal writes its gene calls to prodigal/ (prodigal.tsv, .faa and .gff), not to RASTtk's
rasttk/rast.* files, and the later steps read each genome's own gene calls. The MARGIE database
keeps RASTtk-based results: a genome bound for Prodigal takes RASTtk's gene calls and results when
its sequence has them, so Prodigal annotates novel genomes; a Prodigal genome reads the protein
cache, its results are loaded without entering the caches, a later RASTtk load replaces them, and
a Prodigal load leaves RASTtk-based rows in place."""

import csv
import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from bioinformatics_tools.workflow_tools.workflow_helpers import gene_call_files
from tests.test_workflow import _fake_launchers, wf  # noqa: F401 (fixture)

W = 'bioinformatics_tools.workflow_tools.workflow'
TOOLS = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'
SMK = TOOLS / 'margie_sb.smk'
LOADER = TOOLS / 'load_to_db.py'
needs_snakemake = pytest.mark.skipif(importlib.util.find_spec('snakemake') is None, reason='snakemake is not installed')


def test_each_caller_has_its_own_folder():
    assert gene_call_files('out/g/', 'rasttk') == {
        'table': 'out/g/rasttk/rast.tsv', 'faa': 'out/g/rasttk/rast.faa', 'gff': 'out/g/rasttk/rast.gff',
        'computed': 'out/g/rasttk/rasttk_compute.tkn', 'loaded': 'out/g/rasttk/rasttk_db.tkn'}
    assert gene_call_files('out/g/', 'prodigal') == {
        'table': 'out/g/prodigal/prodigal.tsv', 'faa': 'out/g/prodigal/prodigal.faa',
        'gff': 'out/g/prodigal/prodigal.gff', 'computed': 'out/g/prodigal/prodigal_compute.tkn',
        'loaded': 'out/g/prodigal/prodigal_db.tkn'}


# ---- the real Snakefile, dry-run, GTDB-Tk off and no domain or genetic code: Prodigal ----

def _dry(tmp_path, files: list[str], targets: list[str], cached_rasttk: str = '') -> str:
    """Dry-runs margie_sb.smk over genome gA with `files` in the run folder; returns its output."""
    genomes, out = tmp_path / 'genomes', tmp_path / 'out'
    genomes.mkdir()
    (genomes / 'gA.fna').write_text('>gA_1\n' + 'ACGT' * 300 + '\n')
    os.utime(genomes / 'gA.fna', (1, 1))
    for rel in files:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text('x\n')
    (tmp_path / 'main.db').touch()
    (tmp_path / 'config.yaml').write_text(
        f'input_fasta: {genomes}\noutput_dir: {out}\nmain_database: {tmp_path}/main.db\nrun_quast: false\n'
        f'run_gtdbtk: false\nmargie_sb:\n  stores_root: {tmp_path}/stores\n'
        + (f'cached_rasttk: {cached_rasttk}\n' if cached_rasttk else ''))
    r = subprocess.run([sys.executable, '-m', 'snakemake', '-s', str(SMK), '--cores', '1', '--nolock', '-n', '-p',
                        '--configfile', str(tmp_path / 'config.yaml'), '--', *[str(out / t) for t in targets]],
                       capture_output=True, text=True, timeout=300, env={**os.environ, 'MARGIE_PYTHON': sys.executable})
    text = r.stdout + r.stderr
    assert r.returncode == 0, text[-2000:]
    return text


def _inputs(text: str, rule: str) -> str:
    block = text[text.index(f'rule {rule}:'):]
    return next(line for line in block.splitlines() if line.strip().startswith('input:'))


@needs_snakemake
def test_prodigal_writes_its_own_folder_and_loads_its_own_table(tmp_path):
    text = _dry(tmp_path, [], ['gA/prodigal/prodigal_db.tkn'])
    rules = re.findall(r'^rule (\w+):', text, re.M)
    assert sorted(rules) == ['load_prodigal_to_db', 'resolve_genome_info', 'run_prodigal']
    run = text[text.index('rule run_prodigal:'):text.index('rule load_prodigal_to_db:')]
    assert 'prodigal/prodigal.faa' in run and 'rasttk/' not in run and 'gene_caller.txt' not in run
    assert re.search(r'load_to_db\.py tsv \S+/gA/prodigal/prodigal\.tsv \S+ prodigal ', text)


@needs_snakemake
def test_the_tools_read_prodigals_proteins_and_load_as_prodigal(tmp_path):
    text = _dry(tmp_path, [], ['gA/cog/cog_db.tkn', 'gA/operon/operon_db.tkn'])
    assert 'gA/prodigal/prodigal.faa' in _inputs(text, 'run_cog')
    assert 'gA/prodigal/prodigal.gff' in _inputs(text, 'run_operon')
    assert 'rasttk' not in _inputs(text, 'run_operon')
    assert re.search(r'load_to_db\.py tsv \S+/gA/cog/cog_results\.tsv .* --gene-caller prodigal', text)


@needs_snakemake
def test_rasttks_gene_calls_from_the_database_stand_in_for_prodigal(tmp_path):
    cached = ['gA/rasttk/rast.tsv', 'gA/rasttk/rast.faa', 'gA/rasttk/rast.gff',
              'gA/rasttk/rasttk_db.tkn', 'gA/rasttk/rasttk_compute.tkn']
    text = _dry(tmp_path, cached, ['gA/cog/cog_db.tkn'], cached_rasttk='gA')
    rules = re.findall(r'^rule (\w+):', text, re.M)
    assert 'run_prodigal' not in rules and 'run_rasttk' not in rules
    assert 'gA/rasttk/rast.faa' in _inputs(text, 'run_cog')
    assert re.search(r'load_to_db\.py tsv \S+/gA/cog/cog_results\.tsv .* --gene-caller rasttk', text)


# ---- the loads: RASTtk replaces Prodigal; Prodigal leaves RASTtk ----

def _load(db: Path, table: str, rows: list[dict], fasta: Path, *extra: str) -> str:
    tsv = db.parent / f'{table}-{len(list(db.parent.glob("*.tsv")))}.tsv'
    with tsv.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    r = subprocess.run([sys.executable, str(LOADER), 'tsv', str(tsv), str(db), table, '--fasta', str(fasta),
                        '--delete-organism', 'gA', *extra], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _count(db: Path, table: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    finally:
        conn.close()


def test_rasttk_replaces_prodigal_and_prodigal_leaves_rasttk(tmp_path):
    db, fasta = tmp_path / 'main.db', tmp_path / 'gA.fna'
    fasta.write_text('>c1\n' + 'ACGT' * 200 + '\n')
    # A novel genome: Prodigal's gene calls and a tool's results on them are loaded.
    _load(db, 'prodigal', [{'organism': 'gA', 'feature_id': 'c1_1'}, {'organism': 'gA', 'feature_id': 'c1_2'}], fasta)
    _load(db, 'cog', [{'organism_name': 'gA', 'feature_id': 'c1_1', 'COG_id': 'COG1'}], fasta, '--gene-caller', 'prodigal')
    assert (_count(db, 'prodigal'), _count(db, 'cog')) == (2, 1)
    # RASTtk on the same genome: its gene calls replace Prodigal's, its results replace theirs.
    out = _load(db, 'rasttk', [{'organism': 'gA', 'feature_id': 'fig|6666666.1.peg.1'}], fasta)
    assert 'Prodigal' in out
    _load(db, 'cog', [{'organism_name': 'gA', 'feature_id': 'fig|6666666.1.peg.1', 'COG_id': 'COG2'},
                      {'organism_name': 'gA', 'feature_id': 'fig|6666666.1.peg.2', 'COG_id': 'COG3'}],
          fasta, '--gene-caller', 'rasttk')
    assert (_count(db, 'prodigal'), _count(db, 'rasttk'), _count(db, 'cog')) == (0, 1, 2)
    # Prodigal again: the RASTtk-based rows stay.
    out = _load(db, 'cog', [{'organism_name': 'gA', 'feature_id': 'c1_9', 'COG_id': 'COG9'}], fasta, '--gene-caller', 'prodigal')
    assert out.startswith('Kept cog')
    conn = sqlite3.connect(db)
    assert sorted(r[0] for r in conn.execute('SELECT COG_id FROM cog')) == ['COG2', 'COG3']
    conn.close()


# ---- consolidation: the gene caller's table is the merge's gene list ----

def _consolidation():
    sys.path.insert(0, str(TOOLS / 'consolidation'))
    try:
        import _shared
        spec = importlib.util.spec_from_file_location('merge_all_columns', TOOLS / 'consolidation' / 'merge-all-columns.py')
        merge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(merge)
        return _shared, merge
    finally:
        sys.path.remove(str(TOOLS / 'consolidation'))


def _table(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter='\t')
        w.writeheader()
        w.writerows(rows)


def test_consolidation_builds_on_prodigals_genes(tmp_path):
    _shared, merge = _consolidation()
    gene = {'organism': 'gA', 'feature_id': 'c1_1', 'gene_id': 'c1_1+300', 'RAST_strand': '+', 'RAST_description': '',
            'gene_start': '1', 'gene_end': '300', 'partial': '00'}
    _table(tmp_path / 'prodigal' / 'prodigal.tsv', [gene])
    _table(tmp_path / 'cog' / 'cog_results.tsv', [{'feature_id': 'c1_1', 'cog_id': 'COG1'}])
    pairs = _shared.discover_tool_tables(tmp_path, set())
    assert [name for name, _ in pairs] == ['cog', 'prodigal']
    rows, cols = merge.build_merged_rows([_shared.load_tool_table(n, p) for n, p in pairs], 'gA', 'Bacteria')
    assert len(rows) == 1 and rows[0]['gene_start'] == '1' and rows[0]['RAST_strand'] == '+'
    assert rows[0]['RAST_description'] == '' and 'PRODIGAL_partial' in cols


def test_with_both_gene_tables_rasttks_is_the_one_merged(tmp_path):
    _shared, _ = _consolidation()
    _table(tmp_path / 'prodigal' / 'prodigal.tsv', [{'organism': 'gA', 'feature_id': 'c1_1'}])
    _table(tmp_path / 'rasttk' / 'rast.tsv', [{'organism': 'gA', 'feature_id': 'fig|6666666.1.peg.1'}])
    assert [name for name, _ in _shared.discover_tool_tables(tmp_path, set())] == ['rasttk']


# ---- the run: RASTtk's gene calls stand in for Prodigal's; Prodigal adds nothing to the caches ----

@patch(f'{W}.cache_sif_files')
@patch(f'{W}.locate_local_sif_files')
@patch(f'{W}.time.sleep')
def test_a_prodigal_genome_with_rasttk_in_the_database_takes_it(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out, db = tmp_path / 'run', tmp_path / 'margie.db'
    db.write_text('')

    def fake_restore(db_path, fasta, tool, paths, optional=()):
        if tool != 'rasttk' or Path(fasta).stem != 'g1':
            return False
        for p in paths:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text('cached\n')
        return True

    with patch(f'{W}.restore', side_effect=fake_restore), \
            patch(f'{W}.restore_all', side_effect=lambda db_path, f, m, **kw: {k: False for k in m}), \
            patch(f'{W}.cached_when', return_value={}), patch(f'{W}.store'), patch(f'{W}.store_all'), \
            patch(f'{W}.log_workflow_run'), patch(f'{W}.is_already_processed', return_value=False), \
            patch(f'{W}.fasta_hashes', return_value=['h']), patch(f'{W}.current_rast_genome_id', return_value=None), \
            patch(f'{W}.protein_cache.enabled', return_value=False), \
            _fake_launchers(wf) as rec:
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'main_database': str(db), 'run_gtdbtk': False},
                                          {'g1': '/in/g1.fna', 'g2': '/in/g2.fna'}, cache_map_fn=lambda s: {'cog': []},
                                          mode='dev', prodigal_genomes={'g1', 'g2'})
    stage1 = ' '.join(' '.join(c) for c in rec['stage1'])
    assert 'cached_rasttk=g1' in stage1
    assert f'{out}/g1/rasttk/rasttk_db.tkn' in stage1 and f'{out}/g1/prodigal/' not in stage1
    assert f'{out}/g2/prodigal/prodigal_db.tkn' in stage1


@patch(f'{W}.cache_sif_files')
@patch(f'{W}.locate_local_sif_files')
@patch(f'{W}.time.sleep')
def test_a_prodigal_genome_reads_the_caches_and_adds_nothing(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out, db = tmp_path / 'run', tmp_path / 'margie.db'
    db.write_text('')
    # g1 is Prodigal's, g2 RASTtk's; both called and loaded, and cog's results loaded.
    for rel in ('g1/prodigal/prodigal_db.tkn', 'g1/prodigal/prodigal.faa', 'g1/cog/cog_db.tkn',
                'g2/rasttk/rasttk_db.tkn', 'g2/rasttk/rast.faa', 'g2/cog/cog_db.tkn'):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text('x\n')
    restored_with: dict = {}

    def fake_restore_all(db_path, fasta, tools, **kw):
        restored_with.setdefault(Path(fasta).stem, {}).update(tools)
        return {k: False for k in tools}

    with patch.object(wf, '_restore_gene_calls', return_value=({}, {})), \
            patch(f'{W}.restore', return_value=False), patch(f'{W}.restore_all', side_effect=fake_restore_all), \
            patch(f'{W}.cached_when', return_value={}), patch(f'{W}.store'), patch(f'{W}.store_all') as store_all, \
            patch(f'{W}.log_workflow_run'), patch(f'{W}.is_already_processed', return_value=False), \
            patch(f'{W}.fasta_hashes', return_value=['h']), patch(f'{W}.current_rast_genome_id', return_value=None), \
            patch(f'{W}.gene_hashes', return_value={}), \
            patch(f'{W}.protein_cache.enabled', return_value=True), patch(f'{W}.protein_cache.TOOLS', ['cog']), \
            patch(f'{W}.protein_cache.split', return_value={'cog': (3, 2)}) as split, \
            patch(f'{W}.protein_cache.store', return_value=1) as pc_store, \
            patch(f'{W}.protein_cache.link_genome') as link, \
            patch(f'{W}.protein_cache.record_fingerprints') as fingerprints, \
            patch(f'{W}.protein_cache.record_proteins') as proteins, \
            _fake_launchers(wf):
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'main_database': str(db), 'run_gtdbtk': False},
                                          {'g1': '/in/g1.fna', 'g2': '/in/g2.fna'},
                                          cache_map_fn=lambda s: {'cog': [str(out / s / 'cog/cog_results.tsv')]},
                                          mode='dev', prodigal_genomes={'g1'})
    # The protein cache serves both; Prodigal's proteins are not kept.
    assert sorted(Path(c.args[1]).name for c in split.call_args_list) == ['prodigal.faa', 'rast.faa']
    assert [Path(c.args[1]).name for c in pc_store.call_args_list] == ['rast.faa']
    # Genome-level results: none come back to or go from the Prodigal genome.
    assert 'g1' not in restored_with and 'cog' in restored_with['g2']
    assert [c.args[1] for c in store_all.call_args_list] == ['/in/g2.fna']
    for recorder in (link, fingerprints, proteins):
        assert recorder.call_count == 1 and '/run/g2/' in str(recorder.call_args)
