"""The database loads (load_*_to_db in margie_sb.smk): 10-minute SLURM jobs, one at a time within a
run (margie_sb_db_writer, capped at 1 by workflow.py), retried twice."""

import re
from pathlib import Path

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def _load_rules():
    text = SMK.read_text()
    blocks = re.split(r'\n(?=rule |localrules|checkpoint )', text)
    return {m.group(1): b for b in blocks if (m := re.match(r'rule (load_\w+_to_db):', b))}


def test_the_default_load_time_is_ten_minutes():
    assert re.search(r"^LOAD_RUNTIME = int\(rc\('load_db\.runtime', 10, config=config\)\)$", SMK.read_text(), re.M)


def test_each_load_rule_has_the_limit_the_slot_and_retries():
    rules = _load_rules()
    assert len(rules) >= 30
    for name, block in rules.items():
        assert 'runtime=LOAD_RUNTIME' in block, name
        assert 'margie_sb_db_writer=1' in block, name
        assert 'retries: LOAD_RETRIES' in block, name


def test_the_run_caps_database_writers_at_one():
    src = (SMK.parent / 'workflow.py').read_text()
    assert "'margie_sb_db_writer': 1," in src
