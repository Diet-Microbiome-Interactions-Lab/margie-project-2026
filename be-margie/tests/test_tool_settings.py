"""Settings lists a database for a tool only when margie_sb.smk reads one (db_path), and a
container only when it runs one (sif_path): SignalP 6, for one, runs from the cluster's modules,
so it had a Container box that nothing read. The registry's database and uses_container say which,
and this checks them against the Snakefile."""

import re
from pathlib import Path

from bioinformatics_tools.workflow_tools import workflow_registry as reg

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def test_a_tool_has_database_and_container_settings_only_when_the_workflow_uses_them():
    smk = SMK.read_text()
    dbs = set(re.findall(r"db_path\(\s*['\"]([\w-]+)['\"]", smk))
    sifs = set(re.findall(r"sif_path\(\s*['\"]([\w.-]+)['\"]", smk))
    params = {p['param'] for p in reg._margie_sb_tool_params()}
    for tool in reg.MARGIE_SB_PHASED_TOOLS:
        key = tool['key']
        assert (f'margie_sb.{key}.db' in params) == (key in dbs), key
        assert (f'margie_sb.{key}.sif' in params) == (tool['sif'] in sifs), key
        assert f'margie_sb.{key}.threads' in params and f'margie_sb.{key}.partition' in params, key
    assert 'margie_sb.signalp6.sif' not in params and 'margie_sb.signalp6.db' not in params
