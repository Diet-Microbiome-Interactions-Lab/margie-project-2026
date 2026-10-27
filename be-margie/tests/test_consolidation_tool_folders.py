"""Consolidation (consolidation/_shared.discover_tool_tables) merges the known tool folders only:
genome_info/ (which gave five empty GENOME_INFO_* columns) and later folders such as llm/ or
mauve/ are not read."""

import importlib
import sys
from pathlib import Path

CONSOLIDATION = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'consolidation'


def _shared():
    sys.path.insert(0, str(CONSOLIDATION))
    try:
        return importlib.import_module('_shared')
    finally:
        sys.path.remove(str(CONSOLIDATION))


def _tsv(path, text='feature_id\tx\nfig|1.peg.1\t1\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_only_tool_folders_are_merged(tmp_path):
    S = _shared()
    _tsv(tmp_path / 'rasttk' / 'rast.tsv')
    _tsv(tmp_path / 'cog' / 'cog_results.tsv')
    _tsv(tmp_path / 'interpro' / 'interpro_hamap_results.tsv')
    _tsv(tmp_path / 'genome_info' / 'genome_info.tsv', 'organism\tcontigs\tn50\tgc\tsize\ncoli\t1\t2\t3\t4\n')
    _tsv(tmp_path / 'llm' / 'llm_results.tsv')
    _tsv(tmp_path / 'mauve' / 'conserved_blocks.tsv')
    _tsv(tmp_path / 'evidence' / 'prepared.tsv')
    names = [name for name, _ in S.discover_tool_tables(tmp_path, set())]
    assert names == ['cog', 'interpro_hamap', 'rasttk']
    assert {'cog', 'eggnog', 'dbcan', 'geneprop', 'interpro', 'operon', 'psortb', 'rasttk', 'prodigal'} <= S.TOOL_FOLDERS
    assert not {'genome_info', 'llm', 'mauve', 'envelope', 'labeling'} & S.TOOL_FOLDERS
    # An excluded tool stays out.
    assert [n for n, _ in S.discover_tool_tables(tmp_path, {'cog'})] == ['interpro_hamap', 'rasttk']
