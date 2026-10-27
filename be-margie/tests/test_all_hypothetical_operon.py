"""An operon of uninformative proteins only gets no context boost: C3 is 0 ("no informative member:
context not assessable"), so final = C1·C4 for its genes. Singletons keep C3 0.5 and no context term;
an operon with informative genes but no assessable or supported pair scores 0, with a reason for each."""

import importlib
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


def _genes(rows):
    return pd.DataFrame([dict(organism='g', feature_id=f, operon_id=o, start=i * 100,
                              clean_descriptor=d or 'hypothetical protein', uninformative=not d)
                         for i, (f, o, d) in enumerate(rows)])


def test_no_informative_member_scores_zero():
    O, S = _modules()
    ref = O.finalize_reference(O.new_reference())
    genes = _genes([('h1', 'operon_1', ''), ('h2', 'operon_1', ''),
                    ('a', 'operon_2', 'TrpA'), ('b', 'operon_2', 'TrpB'),
                    ('c', 'operon_3', 'LacZ'), ('d', 'operon_3', 'LacY'),
                    ('s', '', 'GalK')])
    links = {frozenset(('h1', 'h2')): 0.9, frozenset(('a', 'b')): 0.9}
    per_gene = S.compute(genes, ref, links)
    hyp = per_gene['h1']
    assert hyp['c3'] == 0.0 and hyp['c3_hybrid'] == 0.0 and hyp['gene_class'] == 'all_hypothetical_operon'
    assert S._breakdown_and_formula(hyp, 'operon_1') == ('no informative member: context not assessable',
                                                         'no informative member = 0.0000')
    # Informative, linked, not supported in the reference: 0.
    assert per_gene['a']['c3'] == 0.0
    assert S._breakdown_and_formula(per_gene['a'], 'operon_2')[0] == \
        'operon member, no informative adjacency supported in the reference genomes'
    # Informative but without a UniOP link between them: nothing to assess, 0.
    assert per_gene['c']['c3'] == 0.0
    assert S._breakdown_and_formula(per_gene['c'], 'operon_3')[0] == \
        'operon member, no UniOP-linked adjacent pair of informative genes to assess'
    assert per_gene['s']['c3'] == 0.5 and per_gene['s']['gene_class'] == 'singleton'


def test_their_final_score_is_their_own_evidence(tmp_path, monkeypatch):
    rows = run_final(tmp_path, monkeypatch, [
        {'feature_id': 'hyp', 'c1': '0.1429', 'c2': '0.9', 'c3': '0.0000', 'members': '2'},
        {'feature_id': 'single', 'c1': '0.4286', 'c2': '0.5', 'c3': '0.5000', 'members': '1'},
    ])
    assert rows['hyp']['final_confidence_operon_context'] == rows['hyp']['preliminary_confidence_c1_c4'] == '0.1429'
    assert rows['single']['final_confidence_operon_context'] == '0.4286'
