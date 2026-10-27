"""Settings saves a tool's threads, memory, run time and partition as margie_sb.<tool>.<leaf>, and
margie_sb.smk's rules read <tool>.<leaf>: rc() reads the saved key first for those four leaves, and
each tool's compute rule asks for its partition. Also checks the Phase 8 cap reaches Snakemake,
the final tables leave Phobius out unless it runs, and the C3 reasons use the leave-one-out reference."""

import re
from pathlib import Path

from bioinformatics_tools.workflow_tools import workflow_registry as reg
from bioinformatics_tools.workflow_tools.workflow_helpers import rc

WT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'
SMK = WT / 'margie_sb.smk'


def test_a_saved_tool_resource_wins_over_the_unprefixed_key():
    config = {'cog': {'threads': 2, 'evalue': '1e-2'}, 'margie_sb': {'cog': {'threads': 12, 'mem_mb': 9000}}}
    assert rc('cog.threads', 8, config=config) == 12
    assert rc('cog.mem_mb', 4000, config=config) == 9000
    # Other keys keep their own value: a search setting, and a missing saved leaf.
    assert rc('cog.evalue', '1e-5', config=config) == '1e-2'
    assert rc('cog.runtime', 90, config=config) == 90
    assert rc('pfam.threads', 8, config={'margie_sb': {'pfam': {'threads': ''}}}) == 8


def test_run_level_keys_are_not_replaced_by_saved_defaults():
    config = {'output_dir': '/run/out', 'margie_sb': {'output_dir': '/saved/out'}}
    assert rc('output_dir', None, config=config) == '/run/out'


def test_each_tool_compute_rule_asks_for_its_partition():
    smk = SMK.read_text()
    asked = dict(re.findall(r"tool_partition\('([\w]+)', (\d+)\)", smk))
    for tool in reg.MARGIE_SB_PHASED_TOOLS:
        key = tool['key']
        if tool.get('hidden') or key in {'gtdbtk', 'llm', 'evidence', 'ani', 'aai', 'closest', 'mauve', 'synteny'}:
            continue
        assert key in asked, key
        assert int(asked[key]) == tool['phase'], key


def test_the_phase8_cap_is_passed_to_snakemake():
    assert "'margie_sb_phase8_slot': max_parallel_phase8" in (WT / 'workflow.py').read_text()


def test_the_final_tables_do_not_wait_for_phobius():
    smk = SMK.read_text()
    rule = smk[smk.index('rule run_operon_fingerprint:'):smk.index('rule update_operon_fingerprint_database:')]
    assert 'phobius' not in rule.lower()
    assert 'phobius' not in (WT / 'fingerprint' / 'make-final-annotated.py').read_text().lower()


def test_c3_reasons_use_the_leave_one_out_reference():
    text = (WT / 'scoring' / 'make-final-annotation-with-confidence.py').read_text()
    assert 'C3S.leave_self_out(' in text
