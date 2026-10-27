"""HAMAP's "evalue" column in the merged table holds its profile score, higher being better, so
labeling (assign-canonical-label.py) ranks HAMAP hits highest score first and shows the score as
reported; the other accession tools still rank by lowest e-value."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'labeling' / 'assign-canonical-label.py'
spec = importlib.util.spec_from_file_location('label_hamap_t', SCRIPT)
label = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label)


def test_hamap_takes_the_highest_score():
    row = {'INTERPRO_HAMAP_id': 'MF_01397;MF_01358',
           'INTERPRO_HAMAP_evalue': 'MF_01397: 43.322521; MF_01358: 40.095135',
           'INTERPRO_HAMAP_description': 'MF_01397: NADH-quinone oxidoreductase subunit C/D [nuoC].; '
                                         'MF_01358: NAD(P)H-quinone oxidoreductase subunit H'}
    ev = label.eval_hamap(row)
    assert ev.hit_id == 'MF_01397' and ev.stat_value == '43.322521'
    assert ev.gate_note == 'score=43.322521'
    assert ev.all_stats == 'MF_01397: 43.322521; MF_01358: 40.095135'


def test_an_uninformative_top_score_gives_way():
    row = {'INTERPRO_HAMAP_id': 'MF_00001;MF_00002', 'INTERPRO_HAMAP_evalue': 'MF_00001: 501.0; MF_00002: 9.5',
           'INTERPRO_HAMAP_description': 'MF_00001: UPF0145 protein.; MF_00002: Glucokinase [glk].'}
    ev = label.eval_hamap(row)
    assert ev.hit_id == 'MF_00002'
    assert 'over higher-score-but-uninformative MF_00001, score=501.0' in ev.gate_note


def test_other_tools_rank_by_lowest_evalue():
    row = {'PGAP_id': 'NF1;NF2', 'PGAP_full_seq_evalue': 'NF1: 1e-10; NF2: 1e-50',
           'PGAP_description': 'NF1: glucokinase; NF2: hexokinase'}
    assert label.eval_pgap(row).hit_id == 'NF2'
