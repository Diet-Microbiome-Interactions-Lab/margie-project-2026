"""A genome counts once in the fingerprint databases: a later run of a genome already in a pool
(fingerprint/update-fingerprint-database.py, update-operon-fingerprint-database.py) leaves the pool
as it is, as the operon reference does, so frequencies do not grow with each run of one genome."""

import csv
import importlib.util
from pathlib import Path

FINGERPRINT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'fingerprint'


def _module(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, FINGERPRINT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(path):
    with open(path, newline='') as fh:
        return {r['fingerprint_hash']: r for r in csv.DictReader(fh, delimiter='\t')}


def test_a_gene_pool_counts_a_genome_once(tmp_path):
    pool = _module('update_fingerprint_database_t', 'update-fingerprint-database.py')
    db = tmp_path / 'fingerprint-database.tsv'
    pool.update_database({'h1': 2, 'h2': 1}, {'h1': 'A', 'h2': 'B'}, 'coli--fa1:a1b2', db)
    pool.update_database({'h1': 1}, {'h1': 'A'}, 'dorei--fa1:c3d4', db)
    before = db.read_text()
    pool.update_database({'h1': 2, 'h2': 1}, {'h1': 'A', 'h2': 'B'}, 'coli--fa1:a1b2', db)
    assert db.read_text() == before
    rows = _rows(db)
    assert rows['h1']['fingerprint_frequency'] == '3' and rows['h1']['organisms'] == 'coli--fa1:a1b2|dorei--fa1:c3d4'
    assert rows['h2']['fingerprint_frequency'] == '1'


def test_an_operon_pool_counts_a_genome_once(tmp_path):
    pool = _module('update_operon_fingerprint_database_t', 'update-operon-fingerprint-database.py')
    db = tmp_path / 'operon-fingerprint-database-label-ordered.tsv'
    operons = {'op1': {'label_ordered': 'h1', 'members': 'A -> B'}, 'op2': {'label_ordered': 'h2', 'members': 'C -> D'}}
    pool.update_pool(operons, 'coli--fa1:a1b2', db, 'label_ordered')
    pool.update_pool({'op1': {'label_ordered': 'h1', 'members': 'A -> B'}}, 'dorei--fa1:c3d4', db, 'label_ordered')
    before = db.read_text()
    pool.update_pool(operons, 'coli--fa1:a1b2', db, 'label_ordered')
    assert db.read_text() == before
    rows = _rows(db)
    assert rows['h1']['fingerprint_frequency'] == '2' and rows['h2']['fingerprint_frequency'] == '1'
