"""An accession and nothing else (an eggNOG seed ortholog such as "504832.OCAR_7106", "K00845",
"COG1872") names no function (labeling/descriptor_rules.py), for labeling and C1 alike, and the
labeling fallback pass takes a description that names a protein before an accession or a
localisation-only "Psort location ..." text."""

import importlib.util
from pathlib import Path

WT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R = _module('descriptor_rules_acc_t', WT / 'labeling' / 'descriptor_rules.py')
label = _module('label_acc_t', WT / 'labeling' / 'assign-canonical-label.py')
c1 = _module('c1_acc_t', WT / 'scoring' / 'score-c1-tool-coverage.py')


def test_accession_only_strings_are_uninformative():
    for name in ('504832.OCAR_7106', '511145.b0002', 'K00845', 'COG1872', 'PF00005.27', 'TIGR00001',
                 'NF000001.1', 'IPR000001', 'MF_00001', 'WP_000001.1', 'FIG00903396', 'P0A6V8'):
        assert R.is_uninformative(name), name
    for name in ('1.1.1.1', 'recA', 'ABC transporter ATP-binding protein', 'Orfamide synthetase'):
        assert not R.is_uninformative(name), name


def test_c1_does_not_count_a_seed_ortholog():
    row = {'EGGNOG_best_hit_id': '504832.OCAR_7106.1', 'EGGNOG_best_hit_description': '504832.OCAR_7106'}
    assert c1.compute_c1(row)[1] == []


def test_the_fallback_takes_a_named_protein_before_an_accession():
    # eggNOG has a hit without a description (its seed ortholog stands in); RAST says hypothetical.
    row = {'EGGNOG_id': '504832.OCAR_7106', 'EGGNOG_description': '', 'EGGNOG_evalue': '1e-39',
           'RAST_description': 'hypothetical protein'}
    got = label.assign_label(row)
    assert (got[0], got[1]) == ('hypothetical protein', 'RAST')
    psort = {**row, 'EGGNOG_description': 'Psort location Cytoplasmic, score'}
    assert label.assign_label(psort)[:2] == ('hypothetical protein', 'RAST')
    # With nothing else, the accession is the label, as before.
    alone = {k: v for k, v in row.items() if not k.startswith('RAST')}
    assert label.assign_label(alone)[:2] == ('504832.OCAR_7106', 'EGGNOG')
