"""Leave-one-out (scoring/c3_score_organism.leave_self_out, shared with the final annotation table)
matches a genome by its fingerprint in members.tsv; when that entry names a genome the reference no
longer holds, it matches by name, and failing that scores against the full reference, saying so."""

import importlib
import sys
from pathlib import Path

import pandas as pd

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def _modules():
    sys.path.insert(0, str(SCORING))
    try:
        return (importlib.import_module('c3_occ'), importlib.import_module('c3_lib'),
                importlib.import_module('c3_score_organism'))
    finally:
        sys.path.remove(str(SCORING))


def _genes(org):
    descs = ['TrpA', 'TrpB', 'TrpC']
    return pd.DataFrame([dict(organism=org, feature_id=f'{org}.peg.{i}', operon_id='operon_1', start=i * 100,
                              clean_descriptor=d, uninformative=False, aa_hash=f'h{org}{i}')
                         for i, d in enumerate(descs)])


def _setup(tmp_path, stale_name):
    O, L, S = _modules()
    genes = pd.concat([_genes('coli'), _genes('dorei')])
    ref = O.new_reference()
    O.update_reference(ref, genes, tmp_path)
    O.finalize_reference(ref)
    path = tmp_path / 'occ_reference.pkl'
    O.save_reference(ref, path)
    coli = genes[genes['organism'] == 'coli']
    # members.tsv maps coli's fingerprint to a genome the reference no longer holds.
    O.record_member(path, L.genome_fingerprint(coli['aa_hash']), stale_name)
    genes_file = tmp_path / 'run' / 'coli' / 'labeling' / 'labeled-genes.tsv'
    return S, ref, path, coli, genes_file


def test_a_stale_fingerprint_entry_falls_back_to_the_name(tmp_path, capsys):
    S, ref, path, coli, genes_file = _setup(tmp_path, 'gone')
    loo, token, how = S.leave_self_out(ref, path, coli, 'coli', genes_file)
    assert (token, how) == ('coli', 'name')
    assert loo['organisms_added'] == {'dorei'}
    assert "names this genome 'gone'" in capsys.readouterr().out


def test_without_a_name_match_the_full_reference_is_used(tmp_path, capsys):
    S, ref, path, coli, genes_file = _setup(tmp_path, 'gone')
    renamed = coli.assign(organism='coli--fa1:a1b2')
    loo, token, how = S.leave_self_out(ref, path, renamed, 'coli--fa1:a1b2', genes_file)
    assert loo is ref and token is None and how is None
    assert 'scoring against the full reference' in capsys.readouterr().out


def test_a_current_fingerprint_entry_is_used(tmp_path):
    S, ref, path, coli, genes_file = _setup(tmp_path, 'coli')
    renamed = coli.assign(organism='coli--fa1:a1b2')
    loo, token, how = S.leave_self_out(ref, path, renamed, 'coli--fa1:a1b2', genes_file)
    assert (token, how) == ('coli', 'fingerprint') and loo['organisms_added'] == {'dorei'}
