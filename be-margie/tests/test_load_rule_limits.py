"""The database loads (load_*_to_db in margie_sb.smk): local rules, so each runs in the run's own SLURM
job without a time limit of its own; one at a time within a run (margie_sb_db_writer, capped at 1 by
workflow.py) and across runs (load_to_db takes the write turn, db_turn.py), retried twice; deletes go
through an organism_name index (load_to_db)."""

import re
import sqlite3
from pathlib import Path

from bioinformatics_tools.workflow_tools import load_to_db

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def _load_rules():
    text = SMK.read_text()
    # The commented template for a new tool at the end is not a rule.
    blocks = re.split(r'\n(?=rule |localrules|checkpoint |# ─+ Template)', text)
    # A load rule calls the loader; load_consolidation_to_db only marks consolidation done.
    return {m.group(1): b for b in blocks if (m := re.match(r'rule (load_\w+_to_db):', b)) and 'LOADER_PYTHON' in b}


def test_each_load_rule_is_local_with_the_slot_and_retries():
    rules = _load_rules()
    assert len(rules) >= 29
    for name, block in rules.items():
        assert 'localrule: True' in block, name
        assert 'runtime=' not in block and 'group:' not in block, name
        assert 'margie_sb_db_writer=1' in block, name
        assert 'retries: LOAD_RETRIES' in block, name


def test_the_loads_have_no_slurm_time_of_their_own():
    assert 'load_minutes' not in SMK.read_text()


def test_steps_that_run_again_on_each_run_are_not_loaded():
    text = SMK.read_text()
    local = re.search(r'^localrules: load_consolidation_to_db.*$', text, re.M).group(0)
    for step in ('consolidation', 'labeling', 'scoring', 'fingerprint'):
        name = f'load_{step}_to_db'
        block = re.search(rf'\nrule {name}:\n(.*?)\n\n\n', text, re.S).group(1)
        assert 'LOADER_PYTHON' not in block and 'margie_sb_db_writer' not in block, name
        assert 'its tables are in the results folder' in block, name
        assert name in local, name


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
