"""C3 reports two counts per operon (scoring/c3_score_organism.py): the evaluated pairs (adjacent
informative genes with a UniOP link) and, of these, the OCC-supported ones its geometric mean uses;
the final annotation table labels them so. In c3-only context mode the formula says context = C3."""

import importlib
import importlib.util
import sys
from pathlib import Path

import pandas as pd

from tests.final_scoring_helpers import run_final

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def _modules():
    sys.path.insert(0, str(SCORING))
    try:
        return importlib.import_module('c3_occ'), importlib.import_module('c3_score_organism')
    finally:
        sys.path.remove(str(SCORING))


def _genes(org, descs):
    return pd.DataFrame([dict(organism=org, feature_id=f'{org}.{i}', operon_id='operon_1', start=i * 100,
                              clean_descriptor=d or 'hypothetical protein', uninformative=not d)
                         for i, d in enumerate(descs)])


def test_evaluated_and_supported_pairs_are_two_numbers():
    O, S = _modules()
    ref = O.new_reference()
    O.update_reference(ref, pd.concat([_genes(f'r{k}', ['TrpA', 'TrpB']) for k in range(3)]), Path('.'))
    O.finalize_reference(ref)
    # TrpA-TrpB is supported, TrpB-hypothetical excluded, hypothetical-LacZ excluded, LacZ-GalK novel.
    genes = _genes('g', ['TrpA', 'TrpB', '', 'LacZ', 'GalK'])
    links = {frozenset((f'g.{i}', f'g.{i + 1}')): 0.9 for i in range(4)}
    info = S.compute(genes, ref, links)['g.0']
    assert (info['n_evaluated'], info['n_supported'], info['n_pairs_used'], info['n_neutral']) == (2, 1, 1, 3)
    reason, formula = S._breakdown_and_formula(info, 'operon_1')
    assert reason.startswith('operon context: 1/2 OCC-supported adjacencies, 3 neutral')
    assert formula.startswith('geomean(rho_adj) over 1 OCC-supported adjacencies')

    sys.path.insert(0, str(SCORING))
    try:
        spec = importlib.util.spec_from_file_location('mfawc_pairs_t', SCORING / 'make-final-annotation-with-confidence.py')
        final = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(final)
    finally:
        sys.path.remove(str(SCORING))
    text = final._c3_reasoning_expanded(reason, 'operon_1', '5', '', 3)
    assert 'adjacent pairs of informative genes with a UniOP link (evaluated) = 2' in text
    assert 'of these, pairs with OCC support' in text and 'C3 is their geometric mean) = 1' in text
    assert 'usable UniOP probability' not in text


def test_the_c3_only_formula_says_what_is_computed(tmp_path, monkeypatch):
    gene = {'feature_id': 'peg.1', 'c1': '0.4', 'c2': '0.8', 'c3': '0.5'}
    gated = run_final(tmp_path, monkeypatch, [gene])['peg.1']['confidence_score_formula']
    assert 'context=C2·C3=(0.800·0.500)=+0.4000' in gated
    c3_only = run_final(tmp_path, monkeypatch, [gene], '--context-mode', 'c3-only')['peg.1']
    assert 'context=C3=(0.500)=+0.5000' in c3_only['confidence_score_formula']
    assert 'C2·C3' not in c3_only['confidence_score_formula']
    assert c3_only['final_confidence_operon_context'] == '0.9000'
