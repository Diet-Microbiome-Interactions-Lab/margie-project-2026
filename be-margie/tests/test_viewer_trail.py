"""The genome map's evidence trail counts the way C1 does: the databases C1 counted come from its own
reasoning in the final table (workflow_tools/viz/gen_genome_viewer.py)."""

import importlib.util
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'viz' / 'gen_genome_viewer.py'
spec = importlib.util.spec_from_file_location('gen_genome_viewer_t', VIEWER)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def test_the_shared_slot_lights_its_three_databases():
    reasoning = '2/7 independent databases gave an informative hit (of RAST/COG/PFAM/KEGG/EGGNOG/UNIPROT/TIGRFAM_CLUSTER): PFAM;TIGRFAM_CLUSTER'
    assert viewer.c1_counted(reasoning) == ['Pfam', 'PGAP', 'TIGRFAM', 'NCBIfam']


def test_nothing_counted_or_no_reasoning():
    assert viewer.c1_counted('0/7 independent databases gave an informative hit (of RAST/COG): ') == []
    assert viewer.c1_counted('') == []


def test_fingerprints_are_found_in_a_tidied_run_folder(tmp_path):
    g = tmp_path / 'g1'
    (g / 'per-tool-phased-output' / 'fingerprint').mkdir(parents=True)
    (g / 'per-tool-phased-output' / 'fingerprint' / 'labeled-genes-fingerprint-full.tsv').write_text(
        'feature_id\tfingerprint\nf1\tpattern hash: ab12 || label: X || fingerprint: PFAM_id: PF1\n')
    fps = viewer.load_fingerprints(str(g / 'FINAL_ANNOTATION_WITH_CONFIDENCE.tsv'))
    assert 'f1' in fps and fps['f1']['l'] == 'X'
