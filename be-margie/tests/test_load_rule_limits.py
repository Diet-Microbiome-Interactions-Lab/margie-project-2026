"""The database loads (load_*_to_db in margie_sb.smk): SLURM time from load_minutes (10 minutes, plus
input and database size, doubled on each retry), one at a time within a run (margie_sb_db_writer,
capped at 1 by workflow.py), retried twice; deletes go through an organism_name index (load_to_db)."""

import math
import os
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from bioinformatics_tools.workflow_tools import load_to_db

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def _load_rules():
    text = SMK.read_text()
    blocks = re.split(r'\n(?=rule |localrules|checkpoint )', text)
    # A load rule calls the loader; load_consolidation_to_db only marks consolidation done.
    return {m.group(1): b for b in blocks if (m := re.match(r'rule (load_\w+_to_db):', b)) and 'LOADER_PYTHON' in b}


def _load_minutes(db_path):
    """margie_sb.smk's load_minutes, with its defaults and db_path as main_database."""
    src = SMK.read_text()
    start = src.index('def load_minutes')
    end = src.index('\n\n', src.index('return math.ceil', start))
    scope = {'math': math, 'os': os, 'MAIN_DATABASE': str(db_path), 'LOAD_RUNTIME': 10,
             'LOAD_INPUT_MB_PER_MINUTE': 50.0, 'LOAD_DB_GB_PER_MINUTE': 10.0}
    exec(src[start:end], scope)
    return scope['load_minutes']


def test_the_default_load_time_is_ten_minutes_and_scales():
    text = SMK.read_text()
    assert re.search(r"^LOAD_RUNTIME = int\(rc\('load_db\.runtime', 10, config=config\)\)$", text, re.M)
    assert "rc('load_db.input_mb_per_minute', 50, config=config)" in text
    assert "rc('load_db.db_gb_per_minute', 10, config=config)" in text


def test_the_time_grows_with_input_database_and_attempt(tmp_path):
    db = tmp_path / 'main.db'
    with open(db, 'wb') as fh:
        fh.truncate(20 * 10**9)                          # 20 GB, sparse
    minutes = _load_minutes(db)
    assert minutes(None, SimpleNamespace(size_mb=0), 1) == 12
    assert minutes(None, SimpleNamespace(size_mb=100), 1) == 14
    assert minutes(None, SimpleNamespace(size_mb=100), 2) == 28
    assert minutes(None, SimpleNamespace(size_mb=100), 3) == 56


def test_without_a_database_the_time_is_the_base(tmp_path):
    minutes = _load_minutes(tmp_path / 'none.db')
    assert minutes(None, SimpleNamespace(size_mb=0), 1) == 10


def test_each_load_rule_has_the_limit_the_slot_and_retries():
    rules = _load_rules()
    assert len(rules) >= 30
    for name, block in rules.items():
        assert 'runtime=load_minutes' in block, name
        assert 'margie_sb_db_writer=1' in block, name
        assert 'retries: LOAD_RETRIES' in block, name


def test_the_run_caps_database_writers_at_one():
    src = (SMK.parent / 'workflow.py').read_text()
    assert "'margie_sb_db_writer': 1," in src


def _tsv(path, organism, n):
    path.write_text('gene\torganism_name\n' + ''.join(f'g{i}\t{organism}\n' for i in range(n)))
    return str(path)


def test_a_genome_delete_goes_through_the_organism_index(tmp_path):
    db = str(tmp_path / 'main.db')
    load_to_db.load_csv_to_db(_tsv(tmp_path / 'a.tsv', 'A', 5), db, 'scoring_x', delimiter='\t')
    load_to_db.load_csv_to_db(_tsv(tmp_path / 'b.tsv', 'B', 3), db, 'scoring_x', delimiter='\t')
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' "
                            "AND name='scoring_x__organism_name'").fetchone()
        plan = ' '.join(r[-1] for r in conn.execute(
            "EXPLAIN QUERY PLAN DELETE FROM scoring_x WHERE organism_name IN ('A')"))
        assert 'scoring_x__organism_name' in plan
    finally:
        conn.close()
    assert load_to_db._delete_stale_organism_rows(db, 'scoring_x', 'A') == 5
    conn = sqlite3.connect(db)
    try:
        assert conn.execute('SELECT organism_name, count(*) FROM scoring_x GROUP BY 1').fetchall() == [('B', 3)]
    finally:
        conn.close()


def test_an_older_table_gets_its_index_at_its_first_delete(tmp_path, capsys):
    db = str(tmp_path / 'main.db')
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE kegg (id INTEGER PRIMARY KEY, gene TEXT, organism_name TEXT)')
    conn.executemany('INSERT INTO kegg (gene, organism_name) VALUES (?, ?)', [('g1', 'A'), ('g2', 'B')])
    conn.commit()
    conn.close()
    assert load_to_db._delete_stale_organism_rows(db, 'kegg', 'A') == 1
    assert 'Indexing kegg by organism_name' in capsys.readouterr().out
    conn = sqlite3.connect(db)
    try:
        load_to_db._ensure_run_log(conn)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    finally:
        conn.close()
    assert {'kegg__organism_name', 'run_log__fasta_hash'} <= names
