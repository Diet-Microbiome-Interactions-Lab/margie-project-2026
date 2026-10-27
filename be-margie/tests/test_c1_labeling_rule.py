"""C1 (scoring/score-c1-tool-coverage.py) counts a hit by labeling's rule (labeling/descriptor_rules.py):
a UniProt hit below the 40% identity floor and an accession standing in for a missing description
(e.g. "K00845") count for nothing. C1 reads labeled-genes.tsv only; --cluster-agreement-input is
accepted and not read."""

import csv
import importlib.util
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c1 = _module('c1_rule_t', WT / 'scoring' / 'score-c1-tool-coverage.py')
label = _module('label_rule_t', WT / 'labeling' / 'assign-canonical-label.py')

ROW = {
    'RAST_description': 'Glucokinase (EC 2.7.1.2)',
    'KEGG_best_hit_id': 'K00845', 'KEGG_best_hit_description': 'K00845',
    'UNIPROT_best_hit_id': 'P0A6V8', 'UNIPROT_best_hit_description': 'Glucokinase',
    'UNIPROT_best_hit_percent_identity': '35.2',
    'PGAP_best_hit_id': 'NF000001.1', 'PGAP_best_hit_description': 'NF000001.1',
    'NCBIFAM_best_hit_id': 'NF000002.1', 'NCBIFAM_best_hit_description': 'glucokinase',
}


def test_hits_labeling_rejects_do_not_count():
    score, tools = c1.compute_c1(ROW)
    assert tools == ['RAST', 'TIGRFAM_CLUSTER(NCBIFAM)'] and abs(score - 2 / 7) < 1e-9
    passing = {**ROW, 'UNIPROT_best_hit_percent_identity': '40.0', 'KEGG_best_hit_description': 'glucokinase'}
    assert c1.compute_c1(passing)[1] == ['RAST', 'KEGG', 'UNIPROT', 'TIGRFAM_CLUSTER(NCBIFAM)']
    # No identity reported: the gate is skipped, as labeling skips it.
    assert 'UNIPROT' in c1.compute_c1({**ROW, 'UNIPROT_best_hit_percent_identity': ''})[1]


def test_c1_and_labeling_use_one_rule():
    assert c1.R is label.R or c1.R.__file__ == label.R.__file__
    assert c1.is_uninformative is c1.R.is_uninformative
    merged = {'UNIPROT_id': 'P0A6V8', 'UNIPROT_description': 'Glucokinase', 'UNIPROT_percent_identity': '35.2',
              'KEGG_id': 'K00845', 'KEGG_description': '', 'KEGG_evalue': '1e-50'}
    uni, kegg = label.eval_uniprot(merged), label.eval_kegg(merged)
    assert not uni.qualifies and not kegg.qualifies
    assert not c1.R.hit_is_informative('UNIPROT', uni.hit_id, uni.description, uni.stat_value)
    assert not c1.R.hit_is_informative('KEGG', kegg.hit_id, kegg.description, kegg.stat_value)


def test_c1_does_not_read_the_cluster_table(tmp_path, monkeypatch):
    labeled = tmp_path / 'labeled-genes.tsv'
    with open(labeled, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['feature_id', *ROW], delimiter='\t')
        w.writeheader()
        w.writerow({'feature_id': 'peg.1', **ROW})
    out = tmp_path / 'c1.tsv'
    monkeypatch.setattr(sys, 'argv', ['x', '--labeled-input', str(labeled), '--cluster-agreement-input',
                                      str(tmp_path / 'absent.tsv'), '--output', str(out)])
    c1.main()
    with open(out, newline='') as fh:
        row = next(csv.DictReader(fh, delimiter='\t'))
    assert row['c1_informative_tools'] == 'RAST;TIGRFAM_CLUSTER(NCBIFAM)' and row['c1_formula'] == '2/7 = 0.2857'
    assert 'cluster_by_gene' not in (WT / 'scoring' / 'score-c1-tool-coverage.py').read_text()
