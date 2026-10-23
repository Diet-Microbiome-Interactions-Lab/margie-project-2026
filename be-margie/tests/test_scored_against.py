"""Scoring records what a genome was compared with (scoring/scored-against.json), and each update of
the operon reference records its size (<reference>.summary.json), so Results can say when a genome
was scored against fewer genomes than the reference holds now."""

import importlib.util
import json
import sys
from pathlib import Path

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def _module(name: str, file: str):
    sys.path.insert(0, str(SCORING))
    try:
        spec = importlib.util.spec_from_file_location(name, SCORING / file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCORING))


def test_scoring_writes_what_it_compared_with(tmp_path):
    scorer = _module('c3_score_organism_t', 'c3_score_organism.py')
    out = tmp_path / scorer.SCORED_AGAINST
    scorer.write_scored_against(out, tmp_path / 'occ_reference.pkl', compared=28, left_out_self=True)
    record = json.loads(out.read_text())
    assert record['genomes'] == 28 and record['left_out_self'] is True
    assert record['reference'].endswith('occ_reference.pkl') and record['scored_at']


def test_the_reference_update_writes_its_size():
    text = (SCORING / 'update-occ-reference-depot.py').read_text()
    # Written under the reference lock, after the update, with the count Results compares against.
    assert '.summary.json' in text and '"genomes": after' in text
