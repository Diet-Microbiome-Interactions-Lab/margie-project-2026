"""The operon reference and its sidecars (scoring/c3_occ.py) are written to a temporary file in the
same folder and moved into place with os.replace, so a reader sees the old file or the new one and
needs no lock; a write that fails leaves the old file as it was."""

import importlib
import os
import pickle
import sys
from pathlib import Path

import pytest

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def _c3_occ():
    sys.path.insert(0, str(SCORING))
    try:
        return importlib.import_module('c3_occ')
    finally:
        sys.path.remove(str(SCORING))


class _Unpicklable:
    def __reduce__(self):
        raise RuntimeError('cannot pickle')


def test_a_failed_save_leaves_the_old_reference(tmp_path):
    O = _c3_occ()
    path = tmp_path / 'occ_reference.pkl'
    ref = O.new_reference()
    O.save_reference(ref, path)
    before = path.read_bytes()
    with pytest.raises(RuntimeError):
        O.save_reference({**ref, 'bad': _Unpicklable()}, path)
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ['occ_reference.pkl']
    assert O.load_reference(path)['version'] == O.REF_VERSION


def test_writes_go_through_os_replace_and_keep_the_mode(tmp_path, monkeypatch):
    O = _c3_occ()
    path = tmp_path / 'occ_reference.pkl'
    O.save_reference(O.new_reference(), path)
    os.chmod(path, 0o640)
    moved = []
    real_replace = os.replace

    def _replace(src, dst):
        moved.append((Path(src).parent, Path(dst).name))
        return real_replace(src, dst)

    monkeypatch.setattr(O.os, 'replace', _replace)
    O.save_reference(O.new_reference(), path)
    O.record_member(path, 'fp1', 'coli')
    O.record_pool_stats(path, 'fp1', 'coli', {'total_genes': 3})
    O.write_text_atomic(Path(str(path) + '.summary.json'), '{"genomes": 1}\n')
    assert moved == [(tmp_path, 'occ_reference.pkl'), (tmp_path, 'occ_reference.pkl.members.tsv'),
                     (tmp_path, 'occ_reference.pkl.genome_stats.tsv'),
                     (tmp_path, 'occ_reference.pkl.summary.json')]
    assert (path.stat().st_mode & 0o777) == 0o640
    assert O.load_members(path) == {'fp1': 'coli'}
    assert O.load_pool_stats(path)['coli']['total_genes'] == 3
    assert not list(tmp_path.glob('.*.tmp'))
    assert pickle.loads(path.read_bytes())['organisms_added'] == set()


def test_the_reference_update_writes_its_summary_atomically():
    text = (SCORING / 'update-occ-reference-depot.py').read_text()
    assert 'c3_occ.write_text_atomic(Path(str(reference_path) + ".summary.json")' in text
