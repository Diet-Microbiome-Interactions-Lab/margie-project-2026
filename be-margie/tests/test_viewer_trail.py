"""The genome map's evidence trail counts the way C1 does: the databases C1 counted come from its own
reasoning in the final table (workflow_tools/viz/gen_genome_viewer.py)."""

import importlib.util
from pathlib import Path

from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

VIEWER = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'viz' / 'gen_genome_viewer.py'
spec = importlib.util.spec_from_file_location('gen_genome_viewer_t', VIEWER)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


def test_the_shared_slot_lights_its_three_databases():
    reasoning = '2/7 independent databases gave an informative hit (of RAST/COG/PFAM/KEGG/EGGNOG/UNIPROT/TIGRFAM_CLUSTER): PFAM;TIGRFAM_CLUSTER'
    assert viewer.c1_counted(reasoning) == ['Pfam', 'PGAP', 'TIGRFAM', 'NCBIfam']


def test_the_member_that_counted_is_lit_alone():
    assert viewer.c1_counted("2/7 ...: PFAM;TIGRFAM_CLUSTER(PGAP)") == ["Pfam", "PGAP"]


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


def test_a_map_names_the_script_version_that_drew_it():
    v = viewer.viewer_version()
    assert len(v) == 12
    # The stamp goes right after the doctype, where Results reads the first few hundred bytes.
    assert viewer.TEMPLATE.startswith('<!doctype html>')


def test_the_server_says_which_version_is_deployed(authed_client):  # noqa: F811
    r = authed_client.get('/v1/ssh/genome-viewer/version')
    assert r.status_code == 200 and r.json()['version'] == viewer.viewer_version()


# C4's reasoning, as the final table writes it.
CONFLICT = ('EC_reporting_tools_count = 2. EC_conflict_fraction = 1.0000 = conflicting tool-pairs / all EC-reporting tool-pairs. '
            'C4 is the fraction of confidence retained after EC-conflict penalty. 1/1 EC tool-pairs conflict among 2 tools '
            '(R=1.0000): EGGNOG: 3.1.3.5,3.1.3.6,3.1.4.16; KEGG: 3.1.31.1 — penalty=(min(m,5)/5)·R=(2/5)·1.0000=0.4000 '
            '→ c4_score=0.6000 (discounts C1 by 40.0%); categorical status=conflicting')


def test_the_map_lists_each_tools_ec_numbers():
    assert viewer.ec_by_tool(CONFLICT) == [['eggNOG', '3.1.3.5, 3.1.3.6, 3.1.4.16'], ['KEGG', '3.1.31.1']]
    assert viewer.ec_pairs(CONFLICT) == [1, 1]
    one = 'EC_reporting_tools_count = 1. ... only one tool reported an EC (KEGG: 1.3.98.3) — nothing independent to conflict with'
    assert viewer.ec_by_tool(one) == [['KEGG', '1.3.98.3']] and viewer.ec_pairs(one) is None
    assert viewer.ec_by_tool('EC_reporting_tools_count = 3. ...: EGGNOG: 1.1.1.1; KEGG: 1.3.1.-; RAST: 1.3.1.84 — ...') == [
        ['eggNOG', '1.1.1.1'], ['KEGG', '1.3.1.-'], ['RAST', '1.3.1.84']]
    assert viewer.ec_by_tool('no EC number assigned by any tool — no conflict measurable') == []


def test_the_map_waits_for_fingerprints_when_they_are_made():
    smk = (VIEWER.parents[1] / 'margie_sb.smk').read_text()
    rule = smk.split('rule run_genome_viewer_one_genome:')[1].split('\nrule ')[0]
    assert "fingerprint_tkn=([FINGERPRINT_COMPUTE_TOKEN] if rc_bool('run_fingerprint', False, config=config) else [])" in rule


def test_a_drawn_map_carries_fingerprints_and_ec_numbers(tmp_path):
    import base64, gzip, json, re, sys
    from unittest.mock import patch
    g = tmp_path / 'g1'
    (g / 'fingerprint').mkdir(parents=True)
    (g / 'fingerprint' / 'labeled-genes-fingerprint-full.tsv').write_text(
        'feature_id\tfingerprint\nfig|1.1.peg.1\tpattern hash: ab12 || label: X || fingerprint: KEGG_id: K1 | PFAM_id: PF1\n')
    head = ['organism_name', 'gene_id', 'RAST_feature_id', 'RAST_start', 'RAST_end', 'RAST_strand', 'CONFIDENCE_TIER',
            'C4_score_EC_conflict', 'C4_score_reasoning', 'best_consensus_product_descriptor']
    row = ['G', 'c1_10+300', 'fig|1.1.peg.1', '10', '309', '+', 'medium', '0.6', CONFLICT, 'a nuclease']
    (g / 'scoring').mkdir()
    final = g / 'scoring' / 'FINAL_ANNOTATION_WITH_CONFIDENCE.tsv'
    final.write_text('\t'.join(head) + '\n' + '\t'.join(row) + '\n')
    out = tmp_path / 'map.html'
    with patch.object(sys, 'argv', ['gen_genome_viewer.py', str(final), str(out)]):
        viewer.main()
    html = out.read_text()
    d = json.loads(re.search(r'const D = (\{.*?\});\n', html).group(1))
    gene = d['genes'][0]
    assert d['fpMade'] is True and gene['fp'] == 1 and gene['ecp'] == [1, 1]
    assert gene['ec'][0] == ['eggNOG', '3.1.3.5, 3.1.3.6, 3.1.4.16']
    packed = re.search(r'id="xtra">([^<]+)<', html).group(1)
    extras = json.loads(gzip.decompress(base64.b64decode(packed)))
    x = dict(zip(extras['fields'], extras['rows'][0]))
    assert x['fingerprint_hash'] == 'ab12' and x['fingerprint_label'] == 'X' and 'PFAM_id: PF1' in x['fingerprint_line']


def test_the_linear_view_is_drawn_to_scale_unless_asked_for_gene_order():
    t = viewer.TEMPLATE
    assert '<select id="linScale"><option value="scale">to scale</option><option value="order">in gene order</option></select>' in t
    assert 'let two=false, scaled=true;' in t
    # Regions lie under the genes they span, and labels are measured to fit their gene.
    assert 'if(scaled) for(const k of ks){ const i=list[k], g=D.genes[i]; if(!g.rg) continue;' in t
    assert 'function fit(texts,px,size,keep)' in t


def test_the_page_can_leave_out_the_maps_title():
    assert 'head=0' in viewer.TEMPLATE and '.nohead .left>h1' in viewer.TEMPLATE
