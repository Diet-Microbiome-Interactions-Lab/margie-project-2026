"""QUAST runs when it is selected: the sequential driver never asks for rule all, which was the only
place QUAST's token was requested, so Stage 1 (and rule rasttk_all) ask for it beside GTDB-Tk's.
It is never cached: it measures the assembly submitted, which differs between assemblies of a strain."""

import re
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'


def test_stage_one_asks_for_quast_when_it_is_selected():
    text = (WF / 'workflow.py').read_text()
    body = re.search(r"def _stage1_targets\(genome: str\).*?return targets", text, re.S).group(0)
    assert 'if run_quast_enabled:' in body and 'quast/quast_db.tkn' in body
    assert "run_quast_enabled = smk_config.get('run_quast', True)" in text


def test_rule_rasttk_all_asks_for_quast_too():
    smk = (WF / 'margie_sb.smk').read_text()
    rule = re.search(r"rule rasttk_all:.*?\nrule ", smk, re.S).group(0)
    assert "QUAST_TOKEN" in rule and "run_quast" in rule


def test_quast_is_never_cached():
    text = (WF / 'workflow.py').read_text()
    cache_map = re.search(r"def _genome_cache_map\(genome: str\).*?return cache_map", text, re.S).group(0)
    tools = re.search(r"simple_tools = \[(.*?)\]", cache_map, re.S).group(1)
    assert "'quast'" not in tools and "cache_map['quast']" not in cache_map
