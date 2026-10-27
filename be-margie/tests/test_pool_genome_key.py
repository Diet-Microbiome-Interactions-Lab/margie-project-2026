"""The fingerprint pools (fingerprint/update-fingerprint-database.py, update-operon-fingerprint-database.py)
know a genome by the genome hash ending its name (<name>--fa1:xxxx): a genome seen again, re-annotated or
renamed, has its previous entries replaced, so it counts once and follows its current annotation. A pool
written before per-genome counts were kept is read, its counts estimated. Pools are written through a
temporary file and os.replace."""

import csv
import importlib.util
import os
from pathlib import Path

FINGERPRINT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'fingerprint'


def _module(name, file):
    spec = importlib.util.spec_from_file_location(name, FINGERPRINT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(path):
    with open(path, newline='') as fh:
        return {r['fingerprint_hash']: r for r in csv.DictReader(fh, delimiter='\t')}


def test_a_reannotated_or_renamed_genome_replaces_its_entries(tmp_path):
    pool = _module('update_fingerprint_database_key_t', 'update-fingerprint-database.py')
    db = tmp_path / 'fingerprint-database.tsv'
    pool.update_database({'h1': 2, 'h2': 1}, {'h1': 'A', 'h2': 'B'}, 'coli--fa1:a1b2', db)
    pool.update_database({'h1': 1}, {'h1': 'A'}, 'dorei--fa1:c3d4', db)
    # Re-annotated under the same name: h2 is gone from it, h3 is new.
    pool.update_database({'h1': 1, 'h3': 4}, {'h1': 'A', 'h3': 'C'}, 'coli--fa1:a1b2', db)
    rows = _rows(db)
    assert set(rows) == {'h1', 'h3'}
    assert rows['h1']['fingerprint_frequency'] == '2' and rows['h3']['fingerprint_frequency'] == '4'
    assert rows['h1']['organism_counts'] == 'coli--fa1:a1b2=1|dorei--fa1:c3d4=1'
    # Renamed: the same genome hash, so the same genome.
    pool.update_database({'h1': 1, 'h3': 4}, {'h1': 'A', 'h3': 'C'}, 'ecoli_k12--fa1:a1b2', db)
    rows = _rows(db)
    assert rows['h1']['organisms'] == 'dorei--fa1:c3d4|ecoli_k12--fa1:a1b2'
    assert rows['h1']['fingerprint_frequency'] == '2' and rows['h3']['fingerprint_frequency'] == '4'
    assert not [p for p in tmp_path.iterdir() if p.name.endswith('.tmp')]


def test_a_pool_without_counts_is_read_and_estimated(tmp_path, capsys):
    pool = _module('update_fingerprint_database_legacy_t', 'update-fingerprint-database.py')
    db = tmp_path / 'fingerprint-database.tsv'
    db.write_text('pattern_id\tfingerprint_hash\tfingerprint_label\tfingerprint_frequency\t'
                  'fingerprint_label_frequency\torganisms\n'
                  'pattern_1\th1\tA\t3\t3\tcoli--fa1:a1b2|dorei--fa1:c3d4\n'
                  'pattern_2\th2\tB\t1\t1\tcoli--fa1:a1b2\n')
    pool.update_database({'h1': 2}, {'h1': 'A'}, 'coli--fa1:a1b2', db)
    rows = _rows(db)
    # h1: 3 - 2 (estimated: half of 3, rounded) + 2; h2 held by coli only, so dropped.
    assert set(rows) == {'h1'} and rows['h1']['fingerprint_frequency'] == '3'
    assert rows['h1']['organism_counts'] == 'coli--fa1:a1b2=2'
    assert 'estimated' in capsys.readouterr().err


def test_an_operon_pool_replaces_a_genome_seen_again(tmp_path):
    pool = _module('update_operon_fingerprint_database_key_t', 'update-operon-fingerprint-database.py')
    db = tmp_path / 'operon-fingerprint-database-label-ordered.tsv'
    first = {'op1': {'label_ordered': 'h1', 'members': 'A -> B'}, 'op2': {'label_ordered': 'h2', 'members': 'C -> D'}}
    pool.update_pool(first, 'coli--fa1:a1b2', db, 'label_ordered')
    pool.update_pool({'op1': {'label_ordered': 'h1', 'members': 'A -> B'}}, 'dorei--fa1:c3d4', db, 'label_ordered')
    os.chmod(db, 0o640)
    again = {'op1': {'label_ordered': 'h1', 'members': 'A -> B'}, 'op9': {'label_ordered': 'h9', 'members': 'E -> F'}}
    pool.update_pool(again, 'coli_renamed--fa1:a1b2', db, 'label_ordered')
    rows = _rows(db)
    assert set(rows) == {'h1', 'h9'} and rows['h1']['fingerprint_frequency'] == '2'
    assert rows['h9']['pattern_id'] == 'pattern_3'
    assert rows['h1']['organisms'] == 'coli_renamed--fa1:a1b2|dorei--fa1:c3d4'
    assert (db.stat().st_mode & 0o777) == 0o640
    # A genome name without a hash is its own key.
    members = _module('pool_members_t', 'pool_members.py')
    assert members.genome_key('coli--fa1:a1b2') == 'fa1:a1b2' and members.genome_key('coli--a1b2c3d4') == 'a1b2c3d4'
    assert members.genome_key('phocaeicola-dorei-scaffolds') == 'phocaeicola-dorei-scaffolds'
