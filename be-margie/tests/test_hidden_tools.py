"""The tools MARGIE cannot offer freely are hidden: Phobius and SignalP 4 and 6 (academic licences, no
redistribution) and TMbed (its ProtT5 weights are CC-BY-NC-SA). The website's tool lists, Settings'
per-tool list and the licence list leave them out, and each run switches them off, an older saved choice
that names them included. Their rules stay in margie_sb.smk. PSORTb and DeepSig (GPL) stay offered, and
MEROPS and TCDB stay behind their licence terms."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.licensing.catalog import build_terms_payload
from bioinformatics_tools.workflow_tools.workflow_registry import HIDDEN_TOOLS, WORKFLOWS
from tests.test_workflow import wf  # noqa: F401 (fixture)

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'
HIDDEN = {'phobius', 'tmbed', 'signalp6', 'signalp4'}


def test_the_tools_that_cannot_be_offered_freely_are_hidden():
    assert HIDDEN_TOOLS == HIDDEN


def test_the_website_lists_leave_them_out():
    wf_def = WORKFLOWS['margie_sb']
    keys = {t['key'] for t in wf_def.tools}
    assert not keys & HIDDEN
    assert {'psortb', 'deepsig', 'envelope', 'merops', 'tcdb'} <= keys
    params = [p['param'] for p in wf_def.configurable_params]
    assert not any(h in p for p in params for h in HIDDEN)
    assert any('deepsig' in p for p in params)


def test_the_licence_list_leaves_them_out_and_keeps_merops_and_tcdb_gated():
    payload = build_terms_payload()
    assert not {t['id'] for t in payload['tools']} & HIDDEN
    gated = {t['id'] for t in payload['gated_tools']}
    assert not gated & HIDDEN
    assert {'merops', 'tcdb'} <= gated


def test_no_run_waits_for_their_containers():
    from bioinformatics_tools.workflow_tools.workflow_registry import margie_sb_sif_files
    sifs = {s for s, _ in margie_sb_sif_files()}
    assert not sifs & {'phobius.sif', 'tmbed.sif', 'signalp6.sif', 'signalP4.sif'}
    assert {'psortb.sif', 'deepsig.sif', 'envelope.sif'} <= sifs
    assert not {s for s, _ in WORKFLOWS['margie_sb'].sif_files} & {'phobius.sif', 'tmbed.sif'}


def test_install_sets_nothing_up_for_them():
    from bioinformatics_tools.api.services import tool_assets
    tools = {r['tool'] for r in tool_assets.inventory({}, '/home/u')}
    assert not tools & HIDDEN
    assert {'psortb', 'deepsig', 'merops', 'tcdb'} <= tools


def test_the_pipeline_runs_signalp4_only_when_asked():
    text = SMK.read_text()
    assert re.search(r"rc_bool\('run_signalp4', False, config=config\)", text)


def _launch(wf, selected):  # noqa: F811
    wf.conf.get = MagicMock(side_effect=lambda key, default=None: {
        'input': '/genomes/genome1.fa', 'main_database': '/tmp/test-margie.db', 'margie_sb': {'selected_tools': selected},
    }.get(key, default))
    captured = {}

    def fake_run(key_name, smk_config, genome_files, **kwargs):
        captured['config'] = dict(smk_config)

    entitlement = {'usage_type': 'academic', 'licensed_tools': ['signalp4', 'signalp6'], 'source': 'test'}
    with patch('bioinformatics_tools.workflow_tools.workflow.discover_genomes', return_value={'genome1': '/genomes/genome1.fa'}), \
         patch('bioinformatics_tools.workflow_tools.env_keys.ensure_api_keys'), \
         patch('bioinformatics_tools.workflow_tools.license_gate.ensure_cli_license', return_value=entitlement), \
         patch.object(wf, '_run_pipeline_batch_sequential', side_effect=fake_run):
        wf.do_margie_sb(mode='dev')
    return captured.get('config', {})


def test_each_run_switches_them_off(wf):  # noqa: F811
    config = _launch(wf, '')
    assert all(config.get(f'run_{h}') is False for h in HIDDEN)


def test_an_older_choice_naming_them_runs_without_them(wf):  # noqa: F811
    config = _launch(wf, 'phobius,tmbed,signalp4,signalp6,psortb,deepsig')
    assert all(config.get(f'run_{h}') is False for h in HIDDEN)
    assert config.get('run_psortb') is True and config.get('run_deepsig') is True
