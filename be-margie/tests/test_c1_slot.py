"""C1 (scoring/score-c1-tool-coverage.py): seven independent sources counted when their name is informative.
The shared TIGRFAM/PGAP/NCBIfam slot counts only when one of them, looked at in that order, gives an
informative name, as the script describes; a "hypothetical protein" from all three counts for nothing."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'scoring' / 'score-c1-tool-coverage.py'
spec = importlib.util.spec_from_file_location('c1_t', SCRIPT)
c1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c1)

# Bacteroides thetaiotaomicron's YbjQ (UPF0145) gene, as the run labelled it.
YBJQ = {
    'RAST_description': 'UPF0145 protein YbjQ',
    'COG_best_hit_description': 'Uncharacterized pentameric protein YbjQ, UPF0145 family',
    'PFAM_best_hit_description': 'Putative heavy-metal-binding',
    'EGGNOG_best_hit_description': 'Belongs to the UPF0145 family',
    'UNIPROT_best_hit_description': 'UPF0145 protein BT_3410',
    'PGAP_best_hit_description': 'hypothetical protein',
    'NCBIFAM_best_hit_description': 'hypothetical protein',
}
ANY_HIT = {'tigrfam_cluster_status': 'single_source'}


def test_family_names_of_unknown_function_and_hypothetical_hits_do_not_count():
    score, tools = c1.compute_c1(YBJQ, ANY_HIT)
    assert tools == ['PFAM'] and abs(score - 1 / 7) < 1e-9


def test_the_shared_slot_counts_the_first_informative_member():
    row = {**YBJQ, 'PGAP_best_hit_description': 'heavy-metal-binding protein YbjQ',
           'NCBIFAM_best_hit_description': 'YbjQ family heavy metal-binding protein'}
    score, tools = c1.compute_c1(row, ANY_HIT)
    assert tools == ['PFAM', 'TIGRFAM_CLUSTER(PGAP)'] and abs(score - 2 / 7) < 1e-9
    row['TIGRFAM_best_hit_description'] = 'heavy metal-binding domain protein'
    assert c1.compute_c1(row, ANY_HIT)[1][-1] == 'TIGRFAM_CLUSTER(TIGRFAM)'
