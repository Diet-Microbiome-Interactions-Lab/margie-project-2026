"""The operon reference stores each genome's counts as they were added (c3_occ.py, ref["contrib"]),
so leave-one-out subtracts exactly what went in, even when the genome's files or the informative gate
have changed since; a genome added again has its counts replaced, so they follow its current
annotation. A reference without stored counts loads and works as before, recomputing them."""

import importlib
import sys
from pathlib import Path

import pandas as pd

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'
COUNT_KEYS = ('present', 'adj_org', 'coop_org', 'adj_inst', 'coop_inst', 'deg_adj', 'deg_op',
              'M_adj', 'M_op', 'n_qualifying_operons', 'organisms_added')


def _c3_occ():
    sys.path.insert(0, str(SCORING))
    try:
        return importlib.import_module('c3_occ')
    finally:
        sys.path.remove(str(SCORING))


def _genes(org, operons):
    """operons: {operon_id: [descriptor, ...]}; an empty descriptor is a hypothetical gene."""
    rows, pos = [], 0
    for oid, descs in operons.items():
        for d in descs:
            pos += 1
            rows.append(dict(organism=org, feature_id=f'{org}.peg.{pos}', operon_id=oid, start=pos * 100,
                             clean_descriptor=d or 'hypothetical protein', uninformative=not d))
    return pd.DataFrame(rows)


A = _genes('A', {'operon_1': ['TrpA', 'TrpB', 'TrpC'], 'operon_2': ['LacZ', 'LacY', '']})
B = _genes('B', {'operon_1': ['TrpA', 'TrpB'], 'operon_2': ['LacZ', 'LacY', 'LacA']})
C = _genes('C', {'operon_1': ['TrpB', 'TrpC', 'TrpD']})


def _counts(ref):
    return {k: (dict(ref[k]) if isinstance(ref[k], dict) else ref[k]) for k in COUNT_KEYS}


def _built(O, *frames, tmp_path):
    ref = O.new_reference()
    O.update_reference(ref, pd.concat(frames), tmp_path)
    return ref


def test_leave_one_out_subtracts_what_was_added(tmp_path, capsys):
    O = _c3_occ()
    ref = _built(O, A, B, C, tmp_path=tmp_path)
    assert set(ref['contrib']) == {'A', 'B', 'C'}
    # The genome's files changed after it was added (another gate, a new annotation).
    changed = _genes('A', {'operon_1': ['TrpA', 'TrpE'], 'operon_2': ['GalK', 'GalT']})
    loo = O.subtract_organism(ref, changed, tmp_path, 'A')
    assert _counts(loo) == _counts(_built(O, B, C, tmp_path=tmp_path))
    assert 'stored contribution' in capsys.readouterr().out


def test_a_genome_added_again_has_its_counts_replaced(tmp_path):
    O = _c3_occ()
    ref = _built(O, A, B, tmp_path=tmp_path)
    reannotated = _genes('A', {'operon_1': ['TrpA', 'TrpB', 'TrpD'], 'operon_2': ['GalK', 'GalT']})
    assert O.replace_organism(ref, reannotated, tmp_path, 'A') == 'stored'
    assert _counts(ref) == _counts(_built(O, reannotated, B, tmp_path=tmp_path))
    # Under another name it is replaced under the name the reference knows it by.
    renamed = reannotated.assign(organism='A--fa1:a1b2')
    assert O.replace_organism(ref, renamed, tmp_path, 'A--fa1:a1b2', token='A') == 'stored'
    assert _counts(ref) == _counts(_built(O, reannotated, B, tmp_path=tmp_path))
    # Then its leave-one-out is exact.
    loo = O.subtract_organism(ref, renamed, tmp_path, 'A--fa1:a1b2', token='A')
    assert _counts(loo) == _counts(_built(O, B, tmp_path=tmp_path))


def test_a_reference_without_stored_counts_recomputes_them(tmp_path, capsys):
    O = _c3_occ()
    ref = _built(O, A, B, tmp_path=tmp_path)
    del ref['contrib']
    path = tmp_path / 'old.pkl'
    O.save_reference(ref, path)
    old = O.load_reference(path)
    assert 'contrib' not in old
    loo = O.subtract_organism(old, A, tmp_path, 'A')
    assert _counts(loo) == _counts(_built(O, B, tmp_path=tmp_path))
    assert 'recomputed' in capsys.readouterr().out
    # Adding to it stores the new genome's counts, and replacing an old one stores its counts from now on.
    O.update_reference(old, C, tmp_path)
    assert set(old['contrib']) == {'C'}
    assert O.replace_organism(old, A, tmp_path, 'A') == 'recomputed'
    assert set(old['contrib']) == {'A', 'C'}
    assert _counts(old) == _counts(_built(O, A, B, C, tmp_path=tmp_path))


def test_the_stored_counts_add_up_to_the_reference(tmp_path):
    O = _c3_occ()
    ref = _built(O, A, B, C, tmp_path=tmp_path)
    assert sum(c['n_op'] for c in ref['contrib'].values()) == ref['n_qualifying_operons']
    assert sum(sum(c['adj'].values()) for c in ref['contrib'].values()) == ref['M_adj']
    assert sum(sum(c['coop'].values()) for c in ref['contrib'].values()) == ref['M_op']


def test_the_reference_update_replaces_a_genome_it_holds():
    text = (SCORING / 'update-occ-reference-depot.py').read_text()
    assert 'c3_occ.replace_organism(ref, genes, run_root, organism, token=token)' in text
    assert 'if same_genome is None:' not in text
