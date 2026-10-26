"""RASTtk needs a genome's domain and genetic code, not its taxonomy, and GTDB-Tk's first step
(identify) writes both within minutes of a batch that runs for hours. The run reads them there
(workflow_helpers.identify_calls: the translation table, and the domain whose single-copy markers
it found the larger share of, as GTDB-Tk decides it), keeps them in a file the rest of the run's
Snakemake invocations read (gtdbtk_early), and starts those genomes' gene calling while GTDB-Tk
goes on to finish their taxonomy, which is then split, loaded and cached as before."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

from bioinformatics_tools.workflow_tools import workflow as workflow_module
from bioinformatics_tools.workflow_tools.workflow_helpers import (
    GTDBTK_EARLY, genome_calls, identify_calls, read_early_calls, write_early_calls)
from tests.test_cached_gene_calls import SMK, W, needs_snakemake
from tests.test_workflow import _fake_launchers, wf  # noqa: F401 (fixture)

HEAD = ('name\tnumber_unique_genes\tnumber_multiple_genes\tnumber_multiple_unique_genes\tnumber_missing_genes\t'
        'list_unique_genes\tlist_multiple_genes\tlist_multiple_unique_genes\tlist_missing_genes\n')


def _identify(folder: Path, tables: dict[str, str], bac: dict[str, tuple[int, int]], ar: dict[str, tuple[int, int]]) -> Path:
    """Writes GTDB-Tk identify files as classify_wf leaves them: (unique, multiple identical) markers per genome."""
    here = folder / 'container_outputs' / 'gtdbtk' / 'raw' / 'identify'
    here.mkdir(parents=True, exist_ok=True)
    for name, counts in (('bac120', bac), ('ar53', ar)):
        rows = [f'{g}\t{u}\t0\t{m}\t0\t' + ','.join(f'm{i}' for i in range(u)) + '\t\t'
                + ','.join(f'q{i}' for i in range(m)) + '\t\n' for g, (u, m) in counts.items()]
        (here / f'gtdbtk.{name}.markers_summary.tsv').write_text(HEAD + ''.join(rows))
    (here / 'gtdbtk.translation_table_summary.tsv').write_text(''.join(f'{g}\t{t}\n' for g, t in tables.items()))
    return here


def test_the_domain_is_the_larger_share_of_single_copy_markers(tmp_path):
    _identify(tmp_path, {'bac': '11', 'arc': '11', 'tie': '4', 'nomark': '11'},
              bac={'bac': (100, 10), 'arc': (5, 0), 'tie': (0, 0)},
              ar={'bac': (3, 0), 'arc': (40, 5), 'tie': (0, 0)})
    calls = identify_calls(tmp_path)
    # 110/120 against 3/53; 5/120 against 45/53; a tie goes to Bacteria, as in GTDB-Tk's genome_domain.
    assert calls == {'bac': {'domain': 'Bacteria', 'genetic_code': '11'},
                     'arc': {'domain': 'Archaea', 'genetic_code': '11'},
                     'tie': {'domain': 'Bacteria', 'genetic_code': '4'}}


def test_nothing_is_read_before_the_step_is_whole_or_from_an_older_batch(tmp_path):
    here = _identify(tmp_path, {'g': '11'}, bac={'g': (90, 0)}, ar={'g': (1, 0)})
    assert identify_calls(tmp_path, newer_than=time.time() + 3600) == {}
    (here / 'gtdbtk.ar53.markers_summary.tsv').unlink()
    assert identify_calls(tmp_path) == {}
    assert identify_calls(tmp_path / 'nothing-here') == {}


def test_the_genome_table_wins_and_the_first_step_fills_the_rest(tmp_path):
    early = tmp_path / 'early.tsv'
    write_early_calls(early, {'g1': {'domain': 'Archaea', 'genetic_code': '11'},
                              'g2': {'domain': 'Bacteria', 'genetic_code': '4'}})
    assert read_early_calls(early)['g2'] == {'domain': 'Bacteria', 'genetic_code': '4'}
    config = {'run_gtdbtk': True, GTDBTK_EARLY: str(early),
              'margie_sb': {'genome_info': {'g1.fna': {'domain': 'Bacteria'}}}}
    calls = genome_calls({'g1': '/in/g1.fna', 'g2': '/in/g2.fna', 'g3': '/in/g3.fna'}, config)
    assert calls['g1'] == {'domain': 'Bacteria', 'genetic_code': '11', 'gene_caller': 'rasttk', 'source': 'metadata'}
    assert calls['g2'] == {'domain': 'Bacteria', 'genetic_code': '4', 'gene_caller': 'rasttk', 'source': 'gtdbtk'}
    assert calls['g3']['domain'] == '' and calls['g3']['source'] == 'gtdbtk'
    # GTDB-Tk off: its first step is not read.
    assert genome_calls({'g2': '/in/g2.fna'}, {**config, 'run_gtdbtk': False})['g2']['domain'] == ''


class _Proc:
    def __init__(self, until: threading.Event | None = None):
        self.until = until

    def poll(self):
        return None if self.until is not None and not self.until.is_set() else 0

    def wait(self):
        if self.until is not None:
            self.until.wait()
        return 0


def test_gene_calling_starts_from_the_first_step_while_the_batch_goes_on():
    batch_running = threading.Event()
    launched = []

    def launch(targets, label, calls):
        launched.append((label, list(targets), calls))
        if label == 'GTDB-Tk batch':
            return _Proc(batch_running)
        if label.startswith("RASTtk, from GTDB-Tk's first step"):
            # The batch is still going when its first step's genomes start; it ends after.
            assert not batch_running.is_set()
            batch_running.set()
        return _Proc()

    looks = iter([{}, {'g1': {'domain': 'Bacteria', 'genetic_code': '11'}}, {'g1': {'domain': 'Bacteria', 'genetic_code': '11'}}])
    with patch(f'{W}.time.sleep'):
        waves = workflow_module._Stage1Waves(launch, ['batch.done'], ['ready-target'], ['g1', 'g2'],
                                             lambda genomes: [f'{g}-calls' for g in genomes], lambda: next(looks))
        assert waves.wait() == 0
    assert [(label, targets) for label, targets, _ in launched] == [
        ('GTDB-Tk batch', ['batch.done']),
        ('RASTtk, GTDB-Tk not needed or already available', ['ready-target']),
        ("RASTtk, from GTDB-Tk's first step", ['g1-calls']),
        ('RASTtk, after GTDB-Tk batch', ['g2-calls']),
    ]
    assert launched[2][2] == {'g1': {'domain': 'Bacteria', 'genetic_code': '11'}}


def test_without_a_first_step_the_genomes_wait_for_the_batch():
    order = []

    def launch(targets, label, calls):
        order.append(label)
        return _Proc()

    with patch(f'{W}.time.sleep'):
        waves = workflow_module._Stage1Waves(launch, ['batch.done'], [], ['g1'], lambda gs: list(gs), lambda: {})
        waves.wait()
    assert order == ['GTDB-Tk batch', 'RASTtk, after GTDB-Tk batch']


@patch(f'{W}.cache_sif_files')
@patch(f'{W}.locate_local_sif_files')
@patch(f'{W}.time.sleep')
def test_the_run_writes_the_first_steps_values_and_loads_gtdbtk_in_its_batch(mock_sleep, mock_locate, mock_cache, wf, tmp_path):  # noqa: F811
    out = tmp_path / 'run'
    _identify(out / 'original_container_outputs' / 'gtdbtk', {'g1': '11', 'g2': '4'},
              bac={'g1': (110, 0), 'g2': (2, 0)}, ar={'g1': (0, 0), 'g2': (50, 0)})
    smk_config = {'output_dir': str(out), 'main_database': ''}
    with _fake_launchers(wf) as rec:
        wf._run_pipeline_batch_sequential('margie_sb', smk_config, {'g1': '/g1.fa', 'g2': '/g2.fa'},
                                          cache_map_fn=lambda s: {}, mode='dev')
    early = out / 'original_container_outputs' / 'gtdbtk' / 'domain-and-genetic-code.tsv'
    assert read_early_calls(early) == {'g1': {'domain': 'Bacteria', 'genetic_code': '11'},
                                       'g2': {'domain': 'Archaea', 'genetic_code': '4'}}
    waves = [' '.join(c) for c in rec['stage1']]
    batch = next(c for c in waves if 'gtdbtk_batch.done' in c)
    # The batch splits and loads GTDB-Tk's results; the gene calling, started from its first step,
    # waits for none of it, and the later Snakemake invocations read the same values.
    assert f'{out}/g1/gtdbtk/gtdbtk_db.tkn' in batch and f'{out}/g2/gtdbtk/gtdbtk_db.tkn' in batch
    first = next(c for c in waves if f'{out}/g1/rasttk/rasttk_db.tkn' in c)
    assert f'{GTDBTK_EARLY}={early}' in first and 'gtdbtk_db.tkn' not in first
    assert smk_config[GTDBTK_EARLY] == str(early)


# ---- the real Snakefile, dry-run ----

def _dry(tmp_path, targets: list[str], extra: str = '') -> list[str]:
    genomes, out = tmp_path / 'genomes', tmp_path / 'out'
    genomes.mkdir()
    for g in ('gA', 'gB'):
        (genomes / f'{g}.fna').write_text(f'>{g}_1\n' + 'ACGT' * 300 + '\n')
    (tmp_path / 'main.db').touch()
    (tmp_path / 'config.yaml').write_text(
        f'input_fasta: {genomes}\noutput_dir: {out}\nmain_database: {tmp_path}/main.db\nrun_quast: false\n'
        f'run_gtdbtk: true\nmargie_sb:\n  stores_root: {tmp_path}/stores\n' + extra)
    r = subprocess.run([sys.executable, '-m', 'snakemake', '-s', str(SMK), '--cores', '1', '--nolock', '-n',
                        '--configfile', str(tmp_path / 'config.yaml'), '--', *[str(out / t) for t in targets]],
                       capture_output=True, text=True, timeout=300, env={**os.environ, 'MARGIE_PYTHON': sys.executable})
    text = r.stdout + r.stderr
    assert r.returncode == 0, text[-2000:]
    import re
    return re.findall(r'^rule (\w+):', text, re.M)


@needs_snakemake
def test_a_genome_with_first_step_values_calls_its_genes_without_the_batch(tmp_path):
    early = tmp_path / 'early.tsv'
    write_early_calls(early, {'gB': {'domain': 'Bacteria', 'genetic_code': '11'}})
    rules = _dry(tmp_path, ['gB/rasttk/rasttk_db.tkn'], f'{GTDBTK_EARLY}: {early}\n')
    assert 'run_rasttk' in rules and 'resolve_genome_info' in rules
    assert not {'run_gtdbtk_batch', 'split_gtdbtk_batch_per_genome'} & set(rules)


@needs_snakemake
def test_a_genome_the_table_describes_calls_its_genes_without_the_batch(tmp_path):
    rules = _dry(tmp_path, ['gB/rasttk/rasttk_db.tkn'],
                 '  genome_info:\n    gB.fna:\n      domain: Bacteria\n      genetic_code: 11\n')
    assert 'run_rasttk' in rules and 'run_gtdbtk_batch' not in rules


@needs_snakemake
def test_a_genome_without_them_waits_for_the_batch(tmp_path):
    rules = _dry(tmp_path, ['gB/rasttk/rasttk_db.tkn'])
    assert rules[0] == 'run_gtdbtk_batch' and 'split_gtdbtk_batch_per_genome' in rules
