"""The ambiguous-operon review note (score-confidence-final.py) looks at the unclipped context term
C2·C3, so a gene already near 1 with a large C2·C3 is not flagged; the hierarchy tier
(score-hierarchy-tier.py) gives a label that names no function, such as the "hypothetical protein"
labeling's fallback pass picks from PGAP, the lowest tier."""

import importlib.util
from pathlib import Path

from tests.final_scoring_helpers import run_final

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def test_a_large_context_term_is_not_flagged_when_the_score_is_already_high(tmp_path, monkeypatch):
    genes = [
        # Preliminary 0.95: the clipped change is 0.05, the context term 0.5.
        {'feature_id': 'high', 'c1': '0.95', 'c2': '0.9', 'c3': '0.5556', 'ambiguity': '0.6'},
        # A context term of 0.05 in a mostly uncharacterized operon is flagged.
        {'feature_id': 'weak', 'c1': '0.6', 'c2': '0.5', 'c3': '0.1', 'ambiguity': '0.6'},
    ]
    rows = run_final(tmp_path, monkeypatch, genes)
    assert rows['high']['final_confidence_operon_context'] == '1.0000'
    assert rows['high']['does_context_improve_confidence?'] == 'no effect'
    assert 'operon inference ambiguous' not in rows['high']['needs_review_reason']
    assert rows['high']['needs_review'] == 'no'
    assert 'operon inference ambiguous' in rows['weak']['needs_review_reason']


def test_an_uninformative_label_gets_the_lowest_tier():
    spec = importlib.util.spec_from_file_location('score_hierarchy_tier_t', SCORING / 'score-hierarchy-tier.py')
    tier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tier)
    hyp = {'product_descriptor_source': 'PGAP', 'product_descriptor_source_id': 'NF000001.1',
           'best_consensus_product_descriptor': 'hypothetical protein'}
    assert tier.score_hierarchy_tier('PGAP', hyp) == (-1, 'uninformative_label')
    named = {**hyp, 'best_consensus_product_descriptor': 'glucokinase'}
    assert tier.score_hierarchy_tier('PGAP', named) == (4, 'tier1_curated_prokaryote_family')
    accession = {'product_descriptor_source': 'EGGNOG', 'product_descriptor_source_id': '504832.OCAR_7106',
                 'best_consensus_product_descriptor': '504832.OCAR_7106'}
    assert tier.score_hierarchy_tier('EGGNOG', accession)[0] == -1
    low_identity = {'product_descriptor_source_id': 'P0A6V8', 'best_consensus_product_descriptor': 'Glucokinase',
                    'UNIPROT_best_hit_percent_identity': '31.0'}
    assert tier.score_hierarchy_tier('UNIPROT', low_identity)[0] == -1
    assert tier.score_hierarchy_tier('NONE', {'best_consensus_product_descriptor': 'No DB hits'}) == (-1, 'no_qualifying_winner')
    # Without the row, the source alone decides, as before.
    assert tier.score_hierarchy_tier('PGAP') == (4, 'tier1_curated_prokaryote_family')
