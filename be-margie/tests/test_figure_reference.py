"""The report figures compare a genome with the operon reference scoring used: margie_sb.smk passes
that reference to every figure script, which no longer falls back silently to a default name
(a working copy is named <user>-occ_reference-vN.pkl, so the default was never found and the
figures compared with this run's genomes only, captioned "0 genes | 0 operons")."""

import re
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'
FIGURES = WF / 'scoring' / 'analysis' / 'report_figures'
SCRIPTS = ('make_organism_report.py', 'make_complete_operon_diagrams.py', 'make_global_report.py')


def test_every_figure_rule_passes_the_scoring_reference():
    smk = (WF / 'margie_sb.smk').read_text()
    for script in SCRIPTS:
        call = re.search(rf'{re.escape(script)}(.*?)\|\|', smk, re.S)
        assert call and '--occ-reference "{params.occ_reference}"' in call.group(1), script
    assert smk.count('occ_reference=C3_REFERENCE_PKL') == 3


def test_every_figure_script_reads_the_reference_it_is_given():
    for script in SCRIPTS:
        text = (FIGURES / script).read_text()
        assert '"--occ-reference"' in text, script
        assert 'L.comparison_pool(args.occ_reference, args.operon_db' in text, script
        assert 'L.load_pool_stats(Path(args.occ_reference))' in text, script
        assert 'load_occ_organisms()' not in text and 'load_pool_stats()' not in text, script


def _lib():
    import importlib
    import sys
    sys.path.insert(0, str(FIGURES))
    return importlib.import_module('reportfig_lib')


def _operon_db(tmp_path):
    db = tmp_path / 'operon-fingerprint-database-label-ordered.tsv'
    db.write_text('pattern_id\tfingerprint_hash\tmembers_in_order\tfingerprint_frequency\t'
                  'fingerprint_label_frequency\torganisms\n'
                  'p1\th1\tA -> B\t3\t3\tg1|g2|g3\r\n'
                  'p2\th2\tC -> D\t2\t2\tg2|g4\n')
    return db


def test_the_pool_is_the_reference_less_the_genome(tmp_path):
    import pickle
    L = _lib()
    ref = tmp_path / 'u-occ_reference-v1.pkl'
    ref.write_bytes(pickle.dumps({'organisms_added': {'g1', 'g2', 'g3'}}))
    pool, missing = L.comparison_pool(str(ref), _operon_db(tmp_path), leave_out='g1')
    assert (pool, missing) == ({'g2', 'g3'}, None)


def test_a_missing_reference_is_named_and_the_fingerprint_genomes_are_the_pool(tmp_path):
    L = _lib()
    pool, missing = L.comparison_pool(str(tmp_path / 'gone.pkl'), _operon_db(tmp_path), leave_out='g4')
    assert pool == {'g1', 'g2', 'g3'}
    assert missing.endswith('gone.pkl')
    text = L.provenance_text(len(pool), None, leave_one_out=True, missing=missing)
    assert 'operon reference not found' in text and '3 genomes of the operon fingerprint database' in text
    assert L.comparison_pool('', _operon_db(tmp_path))[1] == '(not given)'
