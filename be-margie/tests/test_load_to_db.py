"""load_to_db adds the columns a TSV has and its table lacks. SQLite's column names ignore case,
and a signalp6 table made by an older SignalP output had SIGNALP6_prediction, so the newer
signalp6_prediction was taken for a missing column and adding it failed with "duplicate column
name". Columns are now compared as SQLite compares them."""

import sqlite3

from bioinformatics_tools.workflow_tools.load_to_db import load_csv_to_db


def test_a_column_in_another_case_is_the_same_column(tmp_path):
    db = tmp_path / 'margie.db'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE signalp6 (id INTEGER PRIMARY KEY AUTOINCREMENT, organism_name TEXT, '
                     'feature_id TEXT, SIGNALP6_prediction TEXT, SIGNALP6_prob_sp REAL)')
        conn.execute("INSERT INTO signalp6 (organism_name, feature_id, SIGNALP6_prediction, SIGNALP6_prob_sp) "
                     "VALUES ('old', 'fig|1.peg.1', 'OTHER', 0.01)")
    tsv = tmp_path / 'signalp6_results.tsv'
    tsv.write_text('organism_name\tfeature_id\tsignalp6_prediction\tsignalp6_prob_sp_sec_spi\r\n'
                   'g\tfig|2.peg.24\tSP\t0.999\r\n')

    assert load_csv_to_db(str(tsv), str(db), 'signalp6', delimiter='\t') == 1
    with sqlite3.connect(db) as conn:
        cols = [r[1] for r in conn.execute('PRAGMA table_info(signalp6)')]
        rows = conn.execute('SELECT organism_name, SIGNALP6_prediction, signalp6_prob_sp_sec_spi FROM signalp6 '
                            'ORDER BY id').fetchall()
    assert cols.count('SIGNALP6_prediction') == 1 and 'signalp6_prediction' not in cols
    assert 'signalp6_prob_sp_sec_spi' in cols
    assert rows == [('old', 'OTHER', None), ('g', 'SP', 0.999)]
