"""The descriptor-conflict value (c3_score_organism.descriptor_conflict, reported as
c3_descriptor_conflict) compares descriptors lower-cased, as the operon reference keys them, so a
mixed-case name ("LptM family lipoprotein") matches its consensus partner instead of reading as a
conflict of 1.0, and a mixed-case mate is looked up at all."""

import importlib
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def _modules():
    sys.path.insert(0, str(SCORING))
    try:
        return importlib.import_module('c3_occ'), importlib.import_module('c3_score_organism')
    finally:
        sys.path.remove(str(SCORING))


def test_case_does_not_make_a_conflict():
    _, S = _modules()
    partners = {'outer membrane protein assembly factor bama': Counter({'lptm family lipoprotein': 5}),
                'lptd': Counter({'lpte': 6})}
    assert S.descriptor_conflict('LptM family lipoprotein', ['outer membrane protein assembly factor bama'],
                                 partners) == 0.0
    # A mixed-case mate is found, and its consensus partner differs: a real conflict.
    assert S.descriptor_conflict('LptM family lipoprotein', ['LptD'], partners) == 1.0
    # A mate with the same name says nothing.
    assert S.descriptor_conflict('LptD', ['lptD'], partners) == 0.0


def test_scored_genes_keep_their_consensus_partner():
    O, S = _modules()
    rows = []
    for g in range(4):
        for i, d in enumerate(['outer membrane protein', 'LptM family lipoprotein']):
            rows.append(dict(organism=f'g{g}', feature_id=f'g{g}.{i}', operon_id='operon_1', start=i * 100,
                             clean_descriptor=d, uninformative=False))
    genes = pd.DataFrame(rows)
    ref = O.new_reference()
    O.update_reference(ref, genes, Path('.'))
    O.finalize_reference(ref)
    one = genes[genes['organism'] == 'g0']
    per_gene = S.compute(one, ref, {frozenset(('g0.0', 'g0.1')): 0.9})
    assert per_gene['g0.0']['descriptor_conflict'] == 0.0 and per_gene['g0.1']['descriptor_conflict'] == 0.0
