"""Pfam follows the informativeness rule of the other ranks (assign-canonical-label.py): an
uninformative Pfam hit (a DUF) does not stop the search, so an informative CDD or COG hit names the
gene; with no informative hit at all the fallback pass still takes the first named description."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'labeling' / 'assign-canonical-label.py'
spec = importlib.util.spec_from_file_location('label_pfam_t', SCRIPT)
label = importlib.util.module_from_spec(spec)
spec.loader.exec_module(label)

DUF = {'PFAM_id': 'PF04304', 'PFAM_description': 'Domain of unknown function (DUF412)', 'PFAM_full_seq_evalue': '1e-30'}


def test_a_duf_does_not_stop_the_search():
    row = {**DUF, 'COG_id': 'COG2862', 'COG_description': 'Uncharacterized membrane protein YqhA', 'COG_evalue': '1e-20',
           'INTERPRO_CDD_id': 'cd06261', 'INTERPRO_CDD_description': 'TM_PBP2 transmembrane subunit of ABC transporter',
           'INTERPRO_CDD_evalue': '1e-10'}
    assert label.assign_label(row)[:2] == ('TM_PBP2 transmembrane subunit of ABC transporter', 'CDD')
    assert not label.eval_pfam(DUF).qualifies


def test_with_nothing_informative_the_fallback_is_unchanged():
    row = {**DUF, 'RAST_description': 'hypothetical protein'}
    # RAST comes before PFAM in the order of trust, and "hypothetical protein" names a protein.
    assert label.assign_label(row)[:2] == ('hypothetical protein', 'RAST')
    assert label.assign_label(DUF)[:2] == ('Domain of unknown function (DUF412)', 'PFAM')
    informative = {'PFAM_id': 'PF00005', 'PFAM_description': 'ABC transporter', 'PFAM_full_seq_evalue': '1e-50'}
    assert label.assign_label({**informative, 'RAST_description': 'hypothetical protein'})[:2] == ('ABC transporter', 'PFAM')
