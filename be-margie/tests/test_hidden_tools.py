"""SignalP 4 is hidden: the website's tool lists, Settings' per-tool list and the licence list
leave it out, and each run switches it off, an older saved choice that names it included. Its
rule stays in margie_sb.smk, off unless run_signalp4 is set."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.licensing.catalog import build_terms_payload
from bioinformatics_tools.workflow_tools.workflow_registry import HIDDEN_TOOLS, WORKFLOWS
from tests.test_workflow import wf  # noqa: F401 (fixture)

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def test_signalp4_is_hidden():
    assert HIDDEN_TOOLS == {'signalp4'}


def test_the_website_lists_leave_it_out():
    wf_def = WORKFLOWS['margie_sb']
    assert 'signalp4' not in {t['key'] for t in wf_def.tools}
    assert 'signalp6' in {t['key'] for t in wf_def.tools}
    params = [p['param'] for p in wf_def.configurable_params]
    assert not any('signalp4' in p for p in params) and any('signalp6' in p for p in params)


def test_the_licence_list_leaves_it_out():
    payload = build_terms_payload()
    assert 'signalp4' not in {t['id'] for t in payload['tools']}
    assert 'signalp4' not in {t['id'] for t in payload['gated_tools']}
    assert 'signalp6' in {t['id'] for t in payload['gated_tools']}


def test_the_pipeline_runs_it_only_when_asked():
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


def test_each_run_switches_it_off(wf):  # noqa: F811
    assert _launch(wf, '').get('run_signalp4') is False


def test_an_older_choice_naming_it_runs_without_it(wf):  # noqa: F811
    config = _launch(wf, 'signalp4,signalp6,psortb')
    assert config.get('run_signalp4') is False
    assert config.get('run_signalp6') is True and config.get('run_psortb') is True
