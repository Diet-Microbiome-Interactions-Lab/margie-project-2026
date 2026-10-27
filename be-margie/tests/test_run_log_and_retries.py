"""run_log keeps one row per genome and tool, however the table was created; with the full GTDB-Tk
classification on, cached identify-step results (no classification) run again; each rule that runs on
the cluster retries once, except the LLM step; KEGG jobs running at once do not share KofamScan's
working folder."""

import re
import sqlite3
from pathlib import Path

from bioinformatics_tools.workflow_tools import load_to_db
from bioinformatics_tools.workflow_tools.workflow import WorkflowBase

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def test_a_run_log_made_without_the_unique_rule_gets_it():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE run_log (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, '
                 'input_hash TEXT NOT NULL, tool TEXT NOT NULL, input_path TEXT, row_count INTEGER, '
                 'rules_completed INTEGER, status TEXT NOT NULL, loaded_at TEXT NOT NULL)')
    for run in ('r1', 'r2'):
        conn.execute("INSERT INTO run_log (run_id, input_hash, tool, status, loaded_at) VALUES (?, 'fa1:x', 'margie_sb', 'success', 't')", (run,))
    load_to_db._ensure_run_log(conn)
    assert conn.execute('SELECT run_id FROM run_log').fetchall() == [('r2',)]
    conn.execute("INSERT OR REPLACE INTO run_log (run_id, input_hash, tool, status, loaded_at) VALUES ('r3', 'fa1:x', 'margie_sb', 'success', 't')")
    assert conn.execute('SELECT run_id FROM run_log').fetchall() == [('r3',)]
    load_to_db._ensure_run_log(conn)   # a second call finds the rule and changes nothing
    assert conn.execute('SELECT count(*) FROM run_log').fetchone()[0] == 1


def test_identify_step_results_are_not_a_classification(tmp_path):
    header = 'organism_name\tGTDBTK_domain\tGTDBTK_classification\n'
    identify = tmp_path / 'identify.tsv'
    identify.write_text(header + 'g1\tBacteria\t\n')
    full = tmp_path / 'full.tsv'
    full.write_text(header + 'g1\tBacteria\td__Bacteria;p__Pseudomonadota\n')
    assert WorkflowBase._names_classification(str(identify)) is True
    assert WorkflowBase._names_classification(str(identify), classified=True) is False
    assert WorkflowBase._names_classification(str(full), classified=True) is True


def test_each_cluster_rule_retries_but_the_llm_step():
    text = SMK.read_text()
    local = set()
    for m in re.finditer(r'^localrules:\s*(.+?)(?=\n\S)', text, re.M | re.S):
        local |= {x.strip() for x in m.group(1).replace('\n', ' ').split(',') if x.strip()}
    missing = []
    for block in re.split(r'^(?=rule \w+:)', text, flags=re.M):
        m = re.match(r'rule (\w+):', block)
        if not m or m.group(1) in local or 'localrule: True' in block:
            continue
        body = block.split('\n\n\n')[0]
        if ('shell:' in body or 'run:' in body) and 'retries:' not in body:
            missing.append(m.group(1))
    assert missing == ['run_llm']


def test_kofamscan_runs_from_a_folder_of_its_genome():
    text = SMK.read_text()
    kegg = text[text.index('rule run_kegg:'):text.index('rule load_kegg_to_db:')]
    assert 'WORK="$OUT/{wildcards.genome}/kofamscan-work"' in kegg and '(cd "$WORK" &&' in kegg
