"""Only ids starting with "operon_" are operons in the fingerprint stage: the non-coding features,
which share the id NOT_APPLICABLE_NON_CODING, get no operon fingerprint (add-operon-fingerprint.py),
stay out of the operon pools (update-operon-fingerprint-database.py) and are not listed as one
operon's members (add-fingerprint-to-final.py)."""

import csv
import importlib.util
import sys
from pathlib import Path

FINGERPRINT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'fingerprint'


def _module(name, file):
    spec = importlib.util.spec_from_file_location(name, FINGERPRINT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tsv(path, header, rows):
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        w.writerow(header)
        w.writerows(rows)
    return path


def _read(path):
    with open(path, newline='') as fh:
        return {r['feature_id']: r for r in csv.DictReader(fh, delimiter='\t')}


GENES = [('peg.1', 'operon_0001', '1'), ('peg.2', 'operon_0001', '2'), ('peg.3', 'NOT_IN_AN_OPERON', '0'),
         ('rna.1', 'NOT_APPLICABLE_NON_CODING', '0'), ('rna.2', 'NOT_APPLICABLE_NON_CODING', '0')]
LABELS = {'peg.1': 'TrpA', 'peg.2': 'TrpB', 'peg.3': 'LacZ', 'rna.1': 'tRNA-Ala', 'rna.2': '16S rRNA'}


def _run(module, monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['x', *argv])
    module.main()


def test_non_coding_features_are_not_an_operon(tmp_path, monkeypatch):
    operon_info = _tsv(tmp_path / 'operon-info.tsv',
                       ['organism_name', 'feature_id', 'operon_id', 'operon_gene_position_in_operon'],
                       [('coli', f, o, p) for f, o, p in GENES])
    hash_label = _tsv(tmp_path / 'hash-label.tsv', ['feature_id', 'fingerprint'],
                      [(f, f'pattern hash: h{f} || label: {LABELS[f]}') for f, _, _ in GENES])
    operon_fp = tmp_path / 'operon-fingerprint.tsv'
    _run(_module('add_operon_fp_t', 'add-operon-fingerprint.py'), monkeypatch,
         '--operon-input', str(operon_info), '--hash-label-input', str(hash_label), '--output', str(operon_fp))
    rows = _read(operon_fp)
    assert rows['peg.1']['operon_fingerprint'] and rows['peg.1']['operon_fingerprint'] == rows['peg.2']['operon_fingerprint']
    assert rows['peg.3']['operon_fingerprint'] == ''
    assert rows['rna.1']['operon_fingerprint'] == '' and rows['rna.2']['operon_fingerprint'] == ''
    assert rows['rna.1']['operon_id'] == 'NOT_APPLICABLE_NON_CODING'

    # The operon pools take the real operon only, even from a table written before this fix.
    pool = _module('update_operon_fp_db_t', 'update-operon-fingerprint-database.py')
    old = _read(operon_fp)
    old['rna.1']['operon_fingerprint'] = old['rna.2']['operon_fingerprint'] = old['peg.1']['operon_fingerprint']
    stale = _tsv(tmp_path / 'old-operon-fingerprint.tsv', list(old['peg.1']), [list(r.values()) for r in old.values()])
    assert list(pool.read_new_genome(operon_fp)) == ['operon_0001']
    assert list(pool.read_new_genome(stale)) == ['operon_0001']

    confidence = _tsv(tmp_path / 'confidence-final.tsv',
                      ['feature_id', 'operon_id', 'operon_gene_position_in_operon',
                       'best_consensus_product_descriptor', 'confidence_score'],
                      [(f, o, p, LABELS[f], '0.8' if f.startswith('peg') else '') for f, o, p in GENES])
    ec = _tsv(tmp_path / 'ec.tsv', ['feature_id', 'ec_all_evidence', 'ec_supporting_tools'], [])
    final = tmp_path / 'final.tsv'
    _run(_module('add_fp_final_t', 'add-fingerprint-to-final.py'), monkeypatch,
         '--confidence-final-input', str(confidence), '--fingerprint-hash-label-input', str(hash_label),
         '--operon-fingerprint-input', str(stale), '--fingerprint-database', str(tmp_path / 'none.tsv'),
         '--operon-fp-label-ordered-database', str(tmp_path / 'none1.tsv'),
         '--operon-fp-label-composition-database', str(tmp_path / 'none2.tsv'),
         '--ec-consensus-input', str(ec), '--output', str(final))
    rows = _read(final)
    members = 'operon_member_genes_with_labels_and_confidence_scores_in_position_order'
    assert rows['peg.1'][members].startswith('Position 1: peg.1 [TrpA]') and 'peg.2' in rows['peg.1'][members]
    assert rows['rna.1'][members] == 'NOT_APPLICABLE_NON_CODING'
    assert rows['peg.3'][members] == 'NOT_IN_AN_OPERON'
