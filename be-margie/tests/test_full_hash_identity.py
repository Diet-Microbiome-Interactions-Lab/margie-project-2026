"""Identities are whole SHA-256 hashes (64 hexadecimal digits). The fingerprint pools know a genome by
its full genome hash (--genome-hash, kept in <pool>.genomes.tsv), so two genomes whose names carry the
same short hash stay apart and a renamed genome replaces its entries; a member recorded before the
pools kept full hashes is known by the hash ending its name. Gene, operon, protein and descriptor
fingerprints, gene hashes, the protein cache's keys and the consolidation fingerprint are 64 digits;
a cached table written with the older 24-digit gene hashes is computed again."""

import csv
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from bioinformatics_tools.workflow_tools import output_cache, protein_cache
from bioinformatics_tools.workflow_tools.genome_identity import genome_hash

WT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'
HEX64 = re.compile(r'[0-9a-f]{64}')
A = 'fa1:a1b2' + '0' * 60
B = 'fa1:a1b2' + 'f' * 60


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, WT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(path):
    with open(path, newline='') as fh:
        return {r['fingerprint_hash']: r for r in csv.DictReader(fh, delimiter='\t')}


def test_two_genomes_with_the_same_short_hash_stay_apart(tmp_path):
    pool = _module('ufd_full_t1', 'fingerprint/update-fingerprint-database.py')
    db = tmp_path / 'fingerprint-database.tsv'
    pool.update_database({'h1': 2}, {'h1': 'A'}, 'coli--fa1:a1b2', db, A)
    pool.update_database({'h1': 1}, {'h1': 'A'}, 'dorei--fa1:a1b2', db, B)
    rows = _rows(db)
    assert rows['h1']['organism_counts'] == 'coli--fa1:a1b2=2|dorei--fa1:a1b2=1'
    assert rows['h1']['fingerprint_frequency'] == '3'
    members = (tmp_path / 'fingerprint-database.tsv.genomes.tsv').read_text().splitlines()
    assert members == ['organism\tgenome_hash', f'coli--fa1:a1b2\t{A}', f'dorei--fa1:a1b2\t{B}']


def test_a_renamed_genome_replaces_its_entries_by_full_hash(tmp_path):
    pool = _module('ufd_full_t2', 'fingerprint/update-fingerprint-database.py')
    db = tmp_path / 'fingerprint-database.tsv'
    pool.update_database({'h1': 2, 'h2': 1}, {'h1': 'A', 'h2': 'B'}, 'coli--fa1:a1b20000', db, A)
    pool.update_database({'h1': 2}, {'h1': 'A'}, 'ecoli_k12--fa1:a1b20000', db, A)
    rows = _rows(db)
    assert set(rows) == {'h1'} and rows['h1']['organisms'] == 'ecoli_k12--fa1:a1b20000'
    assert 'coli--fa1:a1b20000' not in (tmp_path / 'fingerprint-database.tsv.genomes.tsv').read_text()


def test_a_member_recorded_before_full_hashes_is_known_by_its_name(tmp_path):
    pool = _module('ufd_full_t3', 'fingerprint/update-fingerprint-database.py')
    db = tmp_path / 'fingerprint-database.tsv'
    pool.update_database({'h1': 2}, {'h1': 'A'}, 'coli--fa1:a1b2', db)   # no hash: a name-keyed member
    (tmp_path / 'fingerprint-database.tsv.genomes.tsv').unlink()
    pool.update_database({'h1': 1}, {'h1': 'A'}, 'coli--fa1:a1b20000', db, A)
    rows = _rows(db)
    assert rows['h1']['organism_counts'] == 'coli--fa1:a1b20000=1'


def test_the_operon_pools_know_a_genome_by_its_full_hash(tmp_path):
    pools = _module('uofd_full_t', 'fingerprint/update-operon-fingerprint-database.py')
    operons = {'k': {'evidence_ordered': 'e1', 'evidence_composition': 'e2', 'label_ordered': 'l1',
                     'label_composition': 'l2', 'members': 'a | b'}}
    db = tmp_path / 'operon-evidence-ordered.tsv'
    pools.update_pool(operons, 'coli--fa1:a1b2', db, 'evidence_ordered', A)
    pools.update_pool(operons, 'dorei--fa1:a1b2', db, 'evidence_ordered', B)
    row = next(iter(_rows(db).values()))
    assert row['organisms'] == 'coli--fa1:a1b2|dorei--fa1:a1b2' and row['fingerprint_frequency'] == '2'


def test_the_snakefile_passes_each_genome_hash_to_the_pools():
    smk = (WT / 'margie_sb.smk').read_text()
    assert smk.count('--genome-hash {params.genome_hash}') == 2


def test_fingerprints_and_keys_are_64_digits(tmp_path):
    gene = _module('agf_full_t', 'fingerprint/add-gene-fingerprint.py')
    operon = _module('aof_full_t', 'fingerprint/add-operon-fingerprint.py')
    final = _module('mfa_full_t', 'scoring/make-final-annotation-with-confidence.py')
    assert HEX64.fullmatch(gene._sha256('RAST: x | PGAP: y'))
    assert HEX64.fullmatch(operon._sha256('a | b'))
    assert HEX64.fullmatch(final._desc_fp('Ribosomal protein L14'))
    assert HEX64.fullmatch(protein_cache.tool_key('pfam', {}))
    gff, faa = tmp_path / 'g.gff', tmp_path / 'g.faa'
    gff.write_text('c1\tRAST\tCDS\t1\t90\t.\t+\t0\tID=fig|6666666.1.peg.1\n')
    faa.write_text('>fig|6666666.1.peg.1\nMKV\n')
    assert HEX64.fullmatch(output_cache.gene_hashes(str(gff), str(faa))['fig|6666666.1.peg.1'])


def test_a_table_cached_with_24_digit_gene_hashes_is_computed_again():
    blob = b'feature_id\tx\nmargie-gene:' + b'a' * 24 + b'\t1\n'
    assert output_cache._from_gene_hashes(blob, {'b' * 64: 'fig|6666666.2.peg.1'}) is None
    full = b'feature_id\tx\nmargie-gene:' + b'b' * 64 + b'\t1\n'
    assert output_cache._from_gene_hashes(full, {'b' * 64: 'fig|6666666.2.peg.1'}) == b'feature_id\tx\nfig|6666666.2.peg.1\t1\n'


needs_snakemake = pytest.mark.skipif(importlib.util.find_spec('snakemake') is None, reason='snakemake is not installed')


@needs_snakemake
def test_a_dry_run_passes_the_genome_hash_to_both_pool_updates(tmp_path):
    genomes, out = tmp_path / 'genomes', tmp_path / 'out'
    genomes.mkdir()
    fna = genomes / 'gA.fna'
    fna.write_text('>gA_1\n' + 'ACGT' * 300 + '\n')
    for rel in ('labeled-genes-fingerprint-hash-label.tsv', 'fingerprint_compute.tkn',
                'labeled-genes-operon-fingerprint.tsv', 'operon_fingerprint_compute.tkn'):
        (out / 'gA' / 'fingerprint').mkdir(parents=True, exist_ok=True)
        (out / 'gA' / 'fingerprint' / rel).write_text('x\n')
    (tmp_path / 'main.db').touch()
    (tmp_path / 'config.yaml').write_text(
        f'input_fasta: {genomes}\noutput_dir: {out}\nmain_database: {tmp_path}/main.db\nrun_quast: false\n'
        f'run_gtdbtk: false\nmargie_sb:\n  stores_root: {tmp_path}/stores\n')
    targets = [out / 'gA/fingerprint/fingerprint_database_updated.tkn',
               out / 'gA/fingerprint/operon_fingerprint_database_updated.tkn']
    r = subprocess.run([sys.executable, '-m', 'snakemake', '-s', str(WT / 'margie_sb.smk'), '--cores', '1', '--nolock',
                        '-n', '-p', '--configfile', str(tmp_path / 'config.yaml'), '--', *map(str, targets)],
                       capture_output=True, text=True, timeout=300, env={**os.environ, 'MARGIE_PYTHON': sys.executable})
    text = r.stdout + r.stderr
    assert r.returncode == 0, text[-2000:]
    assert text.count(f'--genome-hash {genome_hash(fna)}') == 2
