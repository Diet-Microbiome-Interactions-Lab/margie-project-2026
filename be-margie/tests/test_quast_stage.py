"""QUAST runs on its own: it reads only the genomes and no step reads its results, so the run starts
it as a Snakemake of its own beside Stage 1 and 2, a few genomes at a time with few cores each
(Settings: margie_sb.quast.at_once, 3, and margie_sb.quast.threads, 2). Gene calling does not wait
for it in Stage 1's one-job-at-a-time waves. It runs fresh each run: it measures the assembly
submitted, which differs between assemblies of a strain."""

import re
from pathlib import Path
from unittest.mock import patch

from bioinformatics_tools.workflow_tools import workflow_registry as reg
from tests.test_workflow import _fake_launchers, wf  # noqa: F401 (fixture)

WF = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'
W = 'bioinformatics_tools.workflow_tools.workflow'


def _is_quast(cmd):
    return any(t.endswith('/quast/quast_db.tkn') for t in cmd)


def _run(wf, tmp_path, **config):  # noqa: F811
    out = tmp_path / 'run'
    for g in ('g1', 'g2'):
        (out / g / 'rasttk').mkdir(parents=True)
        (out / g / 'rasttk' / 'rasttk_db.tkn').write_text('')
    with patch(f'{W}.cache_sif_files'), patch(f'{W}.locate_local_sif_files'), patch(f'{W}.time.sleep'), \
            _fake_launchers(wf) as rec:
        wf._run_pipeline_batch_sequential('margie_sb', {'output_dir': str(out), 'run_gtdbtk': False, **config},
                                          {'g1': '/g1.fa', 'g2': '/g2.fa'}, cache_map_fn=lambda s: {}, mode='dev')
    return rec


def test_quast_runs_on_its_own_three_genomes_at_a_time(wf, tmp_path):  # noqa: F811
    rec = _run(wf, tmp_path)
    quast = [c for c in rec['stage1'] if _is_quast(c)]
    waves = [c for c in rec['stage1'] if not _is_quast(c)]
    assert len(quast) == 1 and '--jobs=3' in quast[0]
    assert all(t.endswith('/quast/quast_db.tkn') for t in quast[0] if t.endswith('.tkn'))
    assert waves and not any(_is_quast(c) for c in waves)


def test_how_many_at_a_time_comes_from_the_settings(wf, tmp_path):  # noqa: F811
    rec = _run(wf, tmp_path, **{'margie_sb.quast.at_once': 5})
    assert '--jobs=5' in next(c for c in rec['stage1'] if _is_quast(c))


def test_quast_off_starts_nothing(wf, tmp_path):  # noqa: F811
    rec = _run(wf, tmp_path, run_quast=False)
    assert not any(_is_quast(c) for c in rec['stage1'])


def test_the_snakefile_runs_quast_per_genome_with_two_cores():
    smk = (WF / 'margie_sb.smk').read_text()
    rule = re.search(r"rule run_quast:.*?\nrule ", smk, re.S).group(0)
    assert "GENOMES[wildcards.genome]" in rule and "rc('margie_sb.quast.threads', rc('quast.threads', 2" in rule
    rasttk_all = re.search(r"rule rasttk_all:.*?\nrule ", smk, re.S).group(0)
    assert "QUAST_TOKEN" not in rasttk_all
    assert 'rule run_quast_batch' not in smk


def test_settings_offer_its_cores_and_how_many_at_a_time():
    params = {p['param']: p['default'] for p in reg._margie_sb_tool_params()}
    assert params['margie_sb.quast.threads'] == 2 and params['margie_sb.quast.at_once'] == 3


def test_quast_is_never_cached():
    text = (WF / 'workflow.py').read_text()
    cache_map = re.search(r"def _genome_cache_map\(genome: str\).*?return cache_map", text, re.S).group(0)
    tools = re.search(r"simple_tools = \[(.*?)\]", cache_map, re.S).group(1)
    assert "'quast'" not in tools and "cache_map['quast']" not in cache_map
