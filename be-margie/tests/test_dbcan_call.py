"""Labeling (assign-canonical-label.py) counts a dbCAN call by its family ID: a call with a family
and no description is a hit, shown by its family ID, not "no hit"."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'labeling' / 'assign-canonical-label.py'
spec = importlib.util.spec_from_file_location('label_dbcan_t', SCRIPT)
label = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label)


def test_a_family_without_a_description_is_a_call():
    row = {'DBCAN_id': 'GH2_10', 'DBCAN_description': '', 'DBCAN_number_of_tools_hit': '3'}
    ev = label.eval_dbcan(row)
    assert (ev.hit_id, ev.description, ev.stat_value) == ('GH2_10', 'GH2_10', '3')
    assert ev.gate_note == '3 sub-tools agree (family ID only; no description)'
    assert label.build_confirmatory_summary([ev], 'beta-galactosidase').startswith('DBCAN=[hit; GH2_10;')


def test_a_described_call_and_no_call():
    described = label.eval_dbcan({'DBCAN_id': 'GH73', 'DBCAN_description': 'lysozyme-like', 'DBCAN_number_of_tools_hit': '2'})
    assert described.description == 'lysozyme-like' and described.informative
    assert label.eval_dbcan({'DBCAN_id': '', 'DBCAN_description': ''}).gate_note == 'no hit'
