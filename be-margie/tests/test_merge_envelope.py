"""Consolidation (merge-all-columns.py) gives every gene the genome's envelope call from the envelope
stage (envelope/envelope_summary.tsv), with or without DeepSig, PSORTb or SignalP; a row of one of
those that carries its own ENVELOPE_* values takes its place."""

import csv
import subprocess
import sys
from pathlib import Path

MERGE = (Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'consolidation'
         / 'merge-all-columns.py')

RAST = ('organism\tdomain\tfeature_id\tgene_id\tRAST_strand\tgene_start\tgene_end\tna_length\taa_length\t'
        'na_seq\taa_seq\tRAST_description\n'
        'coli\tBacteria\tfig|1.peg.1\tc_1+6\t+\t1\t6\t6\t2\tATGAAA\tMK\tone\n'
        'coli\tBacteria\tfig|1.peg.2\tc_20+6\t+\t20\t25\t6\t2\tATGCCC\tMP\ttwo\n')
SUMMARY = ('organism\tdomain\tenvelope_type\tinference_basis\tevidence_json\n'
           'coli\tBacteria\tdiderm-gram-negative-like\tscore_majority\t{"hits": 16}\n')


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _merge(root):
    out = root / 'merged.tsv'
    subprocess.run([sys.executable, str(MERGE), '--input-root', str(root), '--organism-name', 'coli',
                    '--domain', 'Bacteria', '--output', str(out)], check=True, capture_output=True)
    return {r['feature_id']: r for r in csv.DictReader(out.open(), delimiter='\t')}


def test_every_gene_carries_the_envelope_summary(tmp_path):
    _write(tmp_path / 'rasttk' / 'rast.tsv', RAST)
    _write(tmp_path / 'cog' / 'cog_results.tsv', 'feature_id\tCOG_id\nfig|1.peg.1\tCOG0001\n')
    _write(tmp_path / 'envelope' / 'envelope_summary.tsv', SUMMARY)
    rows = _merge(tmp_path)
    assert {r['ENVELOPE_envelope_type'] for r in rows.values()} == {'diderm-gram-negative-like'}
    assert {r['ENVELOPE_inference_basis'] for r in rows.values()} == {'score_majority'}
    assert rows['fig|1.peg.2']['ENVELOPE_evidence_json'] == '{"hits": 16}'


def test_no_summary_leaves_the_envelope_empty(tmp_path):
    _write(tmp_path / 'rasttk' / 'rast.tsv', RAST)
    rows = _merge(tmp_path)
    assert {r['ENVELOPE_envelope_type'] for r in rows.values()} == {''}


def test_a_localisation_row_takes_the_summary_place(tmp_path):
    _write(tmp_path / 'rasttk' / 'rast.tsv', RAST)
    _write(tmp_path / 'envelope' / 'envelope_summary.tsv', SUMMARY)
    _write(tmp_path / 'psortb' / 'psortb_results.tsv',
           'feature_id\tPSORTB_localization\tENVELOPE_envelope_type\tENVELOPE_inference_basis\tENVELOPE_evidence_json\n'
           'fig|1.peg.1\tCytoplasmic\tmonoderm-gram-positive-like\tpsortb\t{}\n')
    rows = _merge(tmp_path)
    assert rows['fig|1.peg.1']['ENVELOPE_envelope_type'] == 'monoderm-gram-positive-like'
    assert rows['fig|1.peg.2']['ENVELOPE_envelope_type'] == 'diderm-gram-negative-like'
