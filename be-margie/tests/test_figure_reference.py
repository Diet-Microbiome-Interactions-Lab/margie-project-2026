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
        assert 'L.load_occ_organisms(Path(args.occ_reference))' in text, script
        assert 'L.load_pool_stats(Path(args.occ_reference))' in text, script
        assert 'load_occ_organisms()' not in text and 'load_pool_stats()' not in text, script
