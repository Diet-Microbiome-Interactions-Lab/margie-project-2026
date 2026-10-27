"""The uninformative rules (labeling/descriptor_rules.py) look past a leading source tag, so
"JCVI: DUF167 family protein" is a DUF; labeling keeps the full text as the reported descriptor."""

import importlib.util
from pathlib import Path

LABELING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'labeling'


def _module(name, file):
    spec = importlib.util.spec_from_file_location(name, LABELING / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R = _module('descriptor_rules_tags_t', 'descriptor_rules.py')
label = _module('label_tags_t', 'assign-canonical-label.py')


def test_rules_look_past_source_tags():
    for name in ('JCVI: DUF167 family protein', 'NCBI Protein Cluster (PRK): DUF2002 family protein',
                 'JCVI: PRK: hypothetical protein', 'NCBIFAM: UPF0149 family protein', 'NCBIFAM:'):
        assert R.is_uninformative(name), name
    assert not R.is_uninformative('JCVI: glucokinase')
    assert R.strip_source_tags('JCVI: PRK: DUF167 family protein') == 'DUF167 family protein'


def test_labeling_skips_a_tagged_duf_and_reports_names_in_full():
    row = {'PGAP_id': 'NF000001.1', 'PGAP_description': 'JCVI: DUF167 family protein', 'PGAP_full_seq_evalue': '1e-30',
           'TIGRFAM_id': 'TIGR00001', 'TIGRFAM_description': 'JCVI: ribosomal protein L35',
           'TIGRFAM_full_seq_evalue': '1e-20'}
    got = label.assign_label(row)
    assert (got[0], got[1]) == ('JCVI: ribosomal protein L35', 'TIGRFAM')
