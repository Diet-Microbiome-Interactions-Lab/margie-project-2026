"""GTDB-Tk and RASTtk come back from the MARGIE database genome by genome. They used to come back
only when every genome of a run was cached, so one new genome sent all the others through GTDB-Tk
and RASTtk again. A restored genome is named to margie_sb.smk (cached_gtdbtk, cached_rasttk), whose
gtdbtk_from_cache and rasttk_from_cache rules have no inputs: the GTDB-Tk batch, run over the other
genomes only, leaves it as it is. GTDB-Tk's results come back without their database token
(load_gtdbtk_to_db makes it), they are stored as soon as the batch is split, and results that
name only the domain, an older format, are run again. The last tests dry-run the real Snakefile."""

import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from bioinformatics_tools.workflow_tools.output_cache import store
from tests.test_workflow import _fake_launchers, wf  # noqa: F401 (fixture)

W = 'bioinformatics_tools.workflow_tools.workflow'
SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def test_each_genome_comes_back_on_its_own(wf, tmp_path):  # noqa: F811
    out = tmp_path / 'run'
    cached = {('g1', 'gtdbtk'), ('g1', 'rasttk'), ('g3', 'gtdbtk'), ('g3', 'rasttk'), ('g4', 'gtdbtk'), ('g4', 'rasttk')}

    def fake_restore(db_path, fasta, tool, paths, optional=()):
        if (Path(fasta).stem, tool) not in cached:
            return False
        for p in [*paths, *optional]:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text(FULL if p.endswith('gtdbtk_results.tsv') else 'cached\n')
        return True

    wf.conf = {'margie_sb': {'genome_info': {'g4': {'domain': 'Bacteria', 'genetic_code': '11'}}}}
    files = {g: f'/in/{g}.fna' for g in ('g1', 'g2', 'g3', 'g4')}
    with patch(f'{W}.restore', side_effect=fake_restore):
        gtdbtk, rasttk = wf._restore_gene_calls('/db', files, {'output_dir': str(out)}, prodigal_genomes={'g3'})
    assert gtdbtk == {'g1': True, 'g2': False, 'g3': True, 'g4': True}
    # g2: no GTDB-Tk to go with it | g3: Prodigal calls its genes | g4: the config names its domain and code
    assert rasttk == {'g1': True}
    g1 = out / 'g1'
    assert (g1 / 'gtdbtk' / 'gtdbtk_compute.tkn').exists() and (g1 / 'rasttk' / 'rasttk_compute.tkn').exists()
    times = {(g1 / p).stat().st_mtime for p in ('rasttk/rast.tsv', 'rasttk/rast.faa', 'rasttk/rasttk_db.tkn', 'rasttk/rasttk_compute.tkn')}
    assert len(times) == 1


FULL = 'genome\tGTDBTK_domain\tGTDBTK_classification\ng\tBacteria\td__Bacteria;p__Actinomycetota\n'
DOMAIN_ONLY = 'genome\tGTDBTK_domain\ng\tBacteria\n'


def _cached_gtdbtk(tmp_path, results: str) -> tuple[str, dict[str, str], Path]:
    """A MARGIE database holding GTDB-Tk's results and translation table for genome g, stored
    without the database token; returns (database, {g: fasta}, the run's gtdbtk folder)."""
    fasta = tmp_path / 'g.fna'
    fasta.write_text('>g_1\n' + 'ACGT' * 300 + '\n')
    old = tmp_path / 'old' / 'gtdbtk'
    old.mkdir(parents=True)
    (old / 'gtdbtk_results.tsv').write_text(results)
    (old / 'translation_table.tsv').write_text('user_genome\ttranslation_table\ng\t11\n')
    db = str(tmp_path / 'margie.db')
    store(db, str(fasta), 'gtdbtk', [str(old / 'gtdbtk_results.tsv'), str(old / 'translation_table.tsv')])
    return db, {'g': str(fasta)}, tmp_path / 'run' / 'g' / 'gtdbtk'


def test_results_stored_without_their_database_token_come_back(wf, tmp_path):  # noqa: F811
    db, files, run = _cached_gtdbtk(tmp_path, FULL)
    gtdbtk, _ = wf._restore_gene_calls(db, files, {'output_dir': str(tmp_path / 'run')}, prodigal_genomes={'g'})
    assert gtdbtk == {'g': True}
    assert (run / 'gtdbtk_results.tsv').read_text() == FULL and (run / 'gtdbtk_compute.tkn').exists()
    assert not (run / 'gtdbtk_db.tkn').exists()  # load_gtdbtk_to_db makes it


def test_results_that_name_only_the_domain_are_run_again(wf, tmp_path):  # noqa: F811
    db, files, run = _cached_gtdbtk(tmp_path, DOMAIN_ONLY)
    gtdbtk, rasttk = wf._restore_gene_calls(db, files, {'output_dir': str(tmp_path / 'run')}, prodigal_genomes=set())
    assert gtdbtk == {'g': False} and rasttk == {}
    assert not (run / 'gtdbtk_results.tsv').exists() and not (run / 'translation_table.tsv').exists()


@patch(f'{W}.cache_sif_files')
@patch(f'{W}.locate_local_sif_files')
@patch(f'{W}.time.sleep')
def test_gtdbtk_is_stored_once_the_batch_is_split(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out = tmp_path / 'run'
    db = tmp_path / 'margie.db'
    db.write_text('')
    split = [out / 'g1' / 'gtdbtk' / f for f in ('gtdbtk_results.tsv', 'translation_table.tsv', 'gtdbtk_compute.tkn')]
    for f in split:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('x\n')
    # g1's Stage 1 wave never comes: no database token and no RASTtk, as when a run stops early.
    with patch.object(wf, '_restore_gene_calls', return_value=({}, {})), \
            patch(f'{W}.restore_all', side_effect=lambda db_path, f, m, **kw: {k: False for k in m}), \
            patch(f'{W}.cached_when', return_value={}), patch(f'{W}.store') as stored, patch(f'{W}.store_all'), \
            patch(f'{W}.log_workflow_run'), patch(f'{W}.is_already_processed', return_value=False), \
            patch(f'{W}.fasta_hashes', return_value='h'), patch(f'{W}.current_rast_genome_id', return_value=None), \
            patch(f'{W}.protein_cache.enabled', return_value=False), \
            _fake_launchers(wf):
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'main_database': str(db)},
                                          {'g1': '/g1.fa', 'g2': '/g2.fa'}, cache_map_fn=lambda s: {}, mode='dev')
    gtdbtk = [c.args for c in stored.call_args_list if c.args[2] == 'gtdbtk']
    assert [(a[1], a[3][:2]) for a in gtdbtk] == [('/g1.fa', [str(p) for p in split[:2]])]


@patch(f'{W}.cache_sif_files')
@patch(f'{W}.locate_local_sif_files')
@patch(f'{W}.time.sleep')
def test_the_run_names_its_restored_genomes_to_snakemake(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out = tmp_path / 'run'
    db = tmp_path / 'margie.db'
    db.write_text('')
    for g in ('g1', 'g2'):
        (out / g / 'rasttk').mkdir(parents=True)
    for f in ('gtdbtk/gtdbtk_results.tsv', 'gtdbtk/translation_table.tsv', 'gtdbtk/gtdbtk_db.tkn',
              'rasttk/rasttk_db.tkn', 'rasttk/rast.faa'):
        (out / 'g1' / f).parent.mkdir(parents=True, exist_ok=True)
        (out / 'g1' / f).write_text('x\n')
    with patch.object(wf, '_restore_gene_calls', return_value=({'g1': True, 'g2': False}, {'g1': True})), \
            patch(f'{W}.restore_all', side_effect=lambda db_path, f, m, **kw: {k: False for k in m}), \
            patch(f'{W}.cached_when', return_value={}), patch(f'{W}.store'), patch(f'{W}.store_all'), \
            patch(f'{W}.log_workflow_run'), patch(f'{W}.is_already_processed', return_value=False), \
            patch(f'{W}.fasta_hashes', return_value='h'), patch(f'{W}.current_rast_genome_id', return_value=None), \
            patch(f'{W}.protein_cache.enabled', return_value=False), \
            _fake_launchers(wf) as rec:
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'main_database': str(db)},
                                          {'g1': '/g1.fa', 'g2': '/g2.fa'}, cache_map_fn=lambda s: {}, mode='dev')
    stage1 = [' '.join(c) for c in rec['stage1']]
    assert stage1 and all('cached_gtdbtk=g1' in c and 'cached_rasttk=g1' in c for c in stage1)
    assert any(f'{out}/g1/genome_info/genome_info.tsv' in c for c in stage1)


# ---- the real Snakefile, dry-run ----

needs_snakemake = pytest.mark.skipif(importlib.util.find_spec('snakemake') is None, reason='snakemake is not installed')
CACHED = ['gA/gtdbtk/gtdbtk_results.tsv', 'gA/gtdbtk/translation_table.tsv', 'gA/gtdbtk/gtdbtk_db.tkn',
          'gA/gtdbtk/gtdbtk_compute.tkn', 'gA/rasttk/rast.tsv', 'gA/rasttk/rast.faa', 'gA/rasttk/rast.gff',
          'gA/rasttk/rasttk_db.tkn', 'gA/rasttk/rasttk_compute.tkn']
BATCH = ['original_container_outputs/gtdbtk/gtdbtk_results.tsv',
         'original_container_outputs/gtdbtk/gtdbtk.translation_table_summary.tsv',
         'original_container_outputs/gtdbtk/gtdbtk_batch.done']


def _dry(tmp_path, files: dict[str, float], targets: list[str], cached: str = '') -> tuple[list[str], str]:
    """Dry-runs margie_sb.smk over genomes gA and gB with `files` (path -> seconds ago) in the run
    folder; returns the rules Snakemake would run and its output."""
    genomes, out = tmp_path / 'genomes', tmp_path / 'out'
    genomes.mkdir()
    old = time.time() - 10000
    for g in ('gA', 'gB'):
        (genomes / f'{g}.fna').write_text(f'>{g}_1\n' + 'ACGT' * 300 + '\n')
        os.utime(genomes / f'{g}.fna', (old, old))
    now = time.time()
    for rel, ago in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text('x\n')
        os.utime(out / rel, (now - ago, now - ago))
    (tmp_path / 'main.db').touch()
    (tmp_path / 'config.yaml').write_text(
        f'input_fasta: {genomes}\noutput_dir: {out}\nmain_database: {tmp_path}/main.db\nrun_quast: false\n'
        f'run_gtdbtk: true\nmargie_sb:\n  stores_root: {tmp_path}/stores\n'
        + ''.join(f'{k}: {v}\n' for k, v in (('cached_gtdbtk', cached), ('cached_rasttk', cached)) if v))
    # The Snakefile wants the repository's .venv Python unless MARGIE_PYTHON names one.
    r = subprocess.run([sys.executable, '-m', 'snakemake', '-s', str(SMK), '--cores', '1', '--nolock', '-n',
                        '--configfile', str(tmp_path / 'config.yaml'), '--', *[str(out / t) for t in targets]],
                       capture_output=True, text=True, timeout=300, env={**os.environ, 'MARGIE_PYTHON': sys.executable})
    text = r.stdout + r.stderr
    assert r.returncode == 0, text[-2000:]
    return ([] if 'Nothing to be done' in text else re.findall(r'^rule (\w+):', text, re.M)), text


@needs_snakemake
def test_a_cached_genome_stays_as_it_is_after_the_batch_for_the_others(tmp_path):
    files = {**{f: 300 for f in CACHED}, **{f: 50 for f in BATCH}}
    rules, _ = _dry(tmp_path, files, ['gA/genome_info/genome_info.tsv', 'gA/rasttk/rasttk_db.tkn', 'gA/gtdbtk/gtdbtk_db.tkn'],
                    cached='gA')
    assert rules == ['resolve_genome_info']


@needs_snakemake
def test_results_without_their_database_token_are_loaded_not_run_again(tmp_path):
    files = {f: 300 for f in CACHED if not f.endswith('gtdbtk_db.tkn')}
    rules, _ = _dry(tmp_path, files, ['gA/genome_info/genome_info.tsv', 'gA/rasttk/rasttk_db.tkn', 'gA/gtdbtk/gtdbtk_db.tkn'],
                    cached='gA')
    assert sorted(rules) == ['load_gtdbtk_to_db', 'resolve_genome_info']


@needs_snakemake
def test_the_gtdbtk_batch_runs_over_the_other_genomes(tmp_path):
    rules, text = _dry(tmp_path, {f: 300 for f in CACHED}, ['gB/rasttk/rasttk_db.tkn'], cached='gA')
    assert rules[0] == 'run_gtdbtk_batch' and 'run_rasttk' in rules
    batch = text[text.index('rule run_gtdbtk_batch:'):]
    inputs = next(line for line in batch.splitlines() if line.strip().startswith('input:'))
    assert 'gB.fna' in inputs and 'gA.fna' not in inputs


@needs_snakemake
def test_without_the_cache_rules_a_later_batch_would_redo_the_genome(tmp_path):
    files = {**{f: 300 for f in CACHED}, 'gA/genome_info/genome_info.tsv': 250, **{f: 50 for f in BATCH}}
    rules, _ = _dry(tmp_path, files, ['gA/rasttk/rasttk_db.tkn'])
    assert 'split_gtdbtk_batch_per_genome' in rules and 'run_rasttk' in rules
