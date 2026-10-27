"""Localization, topology and signal-peptide tools (Phobius, TMbed, SignalP 6/4, PSORTb, DeepSig) and
the envelope call are evidence, not scoring inputs: a gene's label, hierarchy tier, C1, C4 and final
score are the same with their columns filled as with them empty (labeling and scoring run end to end
on a small merged table). They stay in the final table as evidence columns."""

import csv
import importlib.util
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'

BASE = [
    {'feature_id': 'fig|1.peg.1', 'organism_name': 'coli', 'gene_id': 'c1_1+300', 'gene_start': '1', 'gene_end': '300',
     'RAST_feature_type': 'CDS', 'RAST_strand': '+', 'aa_seq': 'MKV', 'RAST_description': 'Glucokinase (EC 2.7.1.2)',
     'RAST_EC_numbers': '2.7.1.2', 'KEGG_id': 'K00845', 'KEGG_description': 'glk; glucokinase [EC:2.7.1.2]',
     'KEGG_evalue': '1e-80', 'PGAP_id': 'NF000001.1', 'PGAP_description': 'glucokinase', 'PGAP_full_seq_evalue': '1e-90',
     'OPERON_id': 'operon_1', 'OPERON_member_count': '2', 'OPERON_gene_position_in_operon': '1',
     'OPERON_probability': '0.9'},
    {'feature_id': 'fig|1.peg.2', 'organism_name': 'coli', 'gene_id': 'c1_400+900', 'gene_start': '400', 'gene_end': '900',
     'RAST_feature_type': 'CDS', 'RAST_strand': '+', 'aa_seq': 'MKL', 'RAST_description': 'hypothetical protein',
     'EGGNOG_id': '511145.b0002', 'EGGNOG_description': 'Psort location Cytoplasmic, score', 'EGGNOG_evalue': '1e-40',
     'EGGNOG_EC_numbers': '1.1.1.3', 'UNIPROT_id': 'P00561', 'UNIPROT_description': 'Aspartokinase',
     'UNIPROT_percent_identity': '88.0', 'OPERON_id': 'operon_1', 'OPERON_member_count': '2',
     'OPERON_gene_position_in_operon': '2', 'OPERON_probability': '0.9'},
]
LOCALIZATION = {
    'PHOBIUS_segment_type': 'SIGNAL; TRANSMEM', 'PHOBIUS_description': 'glucose permease EC 9.9.9.9',
    'TMBED_topology': '0-31: signal_peptide; 32-300: outside', 'SIGNALP6_prediction': 'SP',
    'SIGNALP4_is_signal_peptide': 'Y', 'PSORTB_localization': 'CytoplasmicMembrane', 'PSORTB_score': '9.97',
    'PSORTB_is_confident': 'True', 'DEEPSIG_feature_type': 'Signal peptide',
    'ENVELOPE_envelope_type': 'diderm', 'ENVELOPE_inference_basis': 'GTDB-Tk phylum', 'ENVELOPE_evidence_json': '{}',
}
SCORED = {
    'labeled': ('best_consensus_product_descriptor', 'product_descriptor_source', 'product_descriptor_source_id'),
    'hierarchy': ('hierarchy_tier_score', 'hierarchy_tier_name'),
    'tier': ('combined_score', 'confidence_tier'),
    'c1': ('c1_score', 'c1_informative_tools'),
    'ec': ('ec_agreement_status', 'ec_consensus_number', 'ec_all_evidence'),
    'c4': ('c4_score', 'c4_ec_agreement_status'),
    'final': ('preliminary_confidence_c1_c4', 'final_confidence_operon_context', 'confidence_score',
              'confidence_tier', 'needs_review_reason'),
}


def _module(name, path):
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(path.parent))


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = sorted({k for r in rows for k in r})
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    return path


def _read(path):
    with open(path, newline='') as fh:
        return {r['feature_id']: r for r in csv.DictReader(fh, delimiter='\t')}


def _run(monkeypatch, script, **args):
    argv = ['x']
    for k, v in args.items():
        argv += [f'--{k.replace("_", "-")}', str(v)]
    monkeypatch.setattr(sys, 'argv', argv)
    _module(f'pipe_{script.stem.replace("-", "_")}', script).main()


def _pipeline(root, monkeypatch, rows):
    g = root / 'run' / 'coli'
    merged = _write(g / 'consolidation' / 'merged.tsv', rows)
    out = {k: g / d / f'{k}.tsv' for k, d in (('labeled', 'labeling'), ('ec', 'labeling'), ('operon', 'labeling'),
                                              ('hierarchy', 'scoring'), ('tier', 'scoring'), ('c1', 'scoring'),
                                              ('c2', 'scoring'), ('c3', 'scoring'), ('c4', 'scoring'),
                                              ('final', 'scoring'))}
    results = _write(g / 'operon' / 'operon_results.tsv', [
        {'feature_id': 'fig|1.peg.1', 'OPERON_downstream_gene_id': 'fig|1.peg.2',
         'OPERON_downstream_pairwise_probability': '0.9'},
        {'feature_id': 'fig|1.peg.2', 'OPERON_upstream_gene_id': 'fig|1.peg.1',
         'OPERON_upstream_pairwise_probability': '0.9'}])
    occ = _module('pipe_c3_occ', WT / 'scoring' / 'c3_occ.py')
    reference = occ.save_reference(occ.new_reference(), root / 'occ.pkl')
    L, S = WT / 'labeling', WT / 'scoring'
    _run(monkeypatch, L / 'assign-canonical-label.py', input=merged, output=out['labeled'])
    _run(monkeypatch, L / 'add-ec-consensus.py', labeled_input=out['labeled'], merged_input=merged, output=out['ec'])
    _run(monkeypatch, L / 'add-operon-info.py', labeled_input=out['labeled'], merged_input=merged, output=out['operon'])
    _run(monkeypatch, S / 'score-hierarchy-tier.py', labeled_input=out['labeled'], output=out['hierarchy'])
    _run(monkeypatch, S / 'score-confidence-tier.py', hierarchy_tier_input=out['hierarchy'],
         ec_consensus_input=out['ec'], output=out['tier'])
    _run(monkeypatch, S / 'score-c1-tool-coverage.py', labeled_input=out['labeled'], output=out['c1'])
    _run(monkeypatch, S / 'score-c2-operon-probability.py', operon_input=out['operon'], operon_results=results,
         output=out['c2'])
    _run(monkeypatch, S / 'c3_score_organism.py', operon_info=out['operon'], genes_file=out['labeled'],
         operon_results=results, reference=reference, output=out['c3'])
    _run(monkeypatch, S / 'score-c4-ec-agreement.py', ec_consensus_input=out['ec'], confidence_tier_input=out['tier'],
         output=out['c4'])
    _run(monkeypatch, S / 'score-confidence-final.py', c1_input=out['c1'], c2_input=out['c2'], c3_input=out['c3'],
         c4_input=out['c4'], operon_input=out['operon'], merged_input=merged, output=out['final'])
    return {k: _read(p) for k, p in out.items()}


def test_localization_columns_do_not_change_any_score(tmp_path, monkeypatch):
    empty = _pipeline(tmp_path / 'empty', monkeypatch, [{**r, **{k: '' for k in LOCALIZATION}} for r in BASE])
    filled = _pipeline(tmp_path / 'filled', monkeypatch, [{**r, **LOCALIZATION} for r in BASE])
    for table, cols in SCORED.items():
        for fid in ('fig|1.peg.1', 'fig|1.peg.2'):
            for col in cols:
                assert filled[table][fid][col] == empty[table][fid][col], (table, fid, col)
    assert empty['labeled']['fig|1.peg.1']['product_descriptor_source'] == 'PGAP'
    assert '9.9.9.9' not in filled['ec']['fig|1.peg.1']['ec_all_evidence']
    # They stay as evidence columns in the final table.
    assert filled['final']['fig|1.peg.1']['PSORTB_localization'] == 'CytoplasmicMembrane'
    assert filled['final']['fig|1.peg.1']['SIGNALP6_prediction'] == 'SP'


def test_no_scoring_rule_reads_a_localization_column():
    R = _module('pipe_rules', WT / 'labeling' / 'descriptor_rules.py')
    ec = _module('pipe_ec', WT / 'labeling' / 'add-ec-consensus.py')
    assert not [c for c in ec.EC_SOURCE_COLUMN.values() if c.startswith(R.LOCALIZATION_PREFIXES)]
    assert 'TCDB' in ec.EC_SOURCE_COLUMN
    fingerprint = _module('pipe_gene_fp', WT / 'fingerprint' / 'add-gene-fingerprint.py')
    slots = fingerprint.build_fingerprint_values({})
    assert not [s for s in slots.split(' | ') if s.startswith(R.LOCALIZATION_PREFIXES)]
