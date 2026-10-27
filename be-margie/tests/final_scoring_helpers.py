"""Builds the small input tables score-confidence-final.py joins and runs it (shared by the scoring tests)."""

import csv
import importlib.util
import sys
from pathlib import Path

SCORING = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring'


def _tsv(path, rows):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    return path


def run_final(tmp_path, monkeypatch, genes, *extra):
    """genes: [{feature_id, c1, c2, c3, ambiguity, members}] -> {feature_id: output row}."""
    files = {
        'c1': _tsv(tmp_path / 'c1.tsv', [{'feature_id': g['feature_id'], 'c1_score': g['c1']} for g in genes]),
        'c2': _tsv(tmp_path / 'c2.tsv', [{'feature_id': g['feature_id'], 'c2_score_from_operon_probability': g['c2']}
                                         for g in genes]),
        'c3': _tsv(tmp_path / 'c3.tsv', [{'feature_id': g['feature_id'], 'c3_score': g['c3'], 'c3_score_hybrid': g['c3'],
                                          'c3_operon_ambiguity': g.get('ambiguity', '0')} for g in genes]),
        'c4': _tsv(tmp_path / 'c4.tsv', [{'feature_id': g['feature_id'], 'c4_score': '1.0',
                                          'c4_ec_agreement_status': 'no_evidence'} for g in genes]),
        'operon': _tsv(tmp_path / 'operon.tsv', [{'feature_id': g['feature_id'], 'operon_id': 'operon_1',
                                                  'operon_member_count': g.get('members', '3')} for g in genes]),
        'merged': _tsv(tmp_path / 'merged.tsv', [{'feature_id': g['feature_id'], 'RAST_feature_type': 'CDS'}
                                                 for g in genes]),
    }
    out = tmp_path / 'final.tsv'
    spec = importlib.util.spec_from_file_location('score_confidence_final_t', SCORING / 'score-confidence-final.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    argv = ['x', '--output', str(out), *extra]
    for k in ('c1', 'c2', 'c3', 'c4', 'operon', 'merged'):
        argv += [f'--{k}-input', str(files[k])]
    monkeypatch.setattr(sys, 'argv', argv)
    module.main()
    with open(out, newline='') as fh:
        return {r['feature_id']: r for r in csv.DictReader(fh, delimiter='\t')}
