"""The driver reads margie_sb.genome_info from the config files themselves, as margie_sb.smk does (the
caragols Condex splits keys at dots, so file names like g1.fna do not come through it whole): a genome
with its domain and genetic code goes to RASTtk with GTDB-Tk off, and the run's report and log say so."""

from bioinformatics_tools.caragols import condo
from bioinformatics_tools.workflow_tools.workflow import WorkflowBase
from bioinformatics_tools.workflow_tools.workflow_helpers import genome_calls

CONFIG = """margie_sb:
  genome_info:
    g1.fna:
      domain: Bacteria
      genetic_code: '11'
"""


def _wf(conf, paths=()):
    wf = WorkflowBase.__new__(WorkflowBase)
    wf.conf = conf
    wf.config_paths = list(paths)
    return wf


def test_genome_info_reaches_the_gene_caller_check(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text(CONFIG)
    conf = condo.Condex()
    conf.load(path)
    settings = _wf(conf, [path])._margie_sb_dict()
    assert isinstance(settings, dict) and settings['genome_info']['g1.fna']['domain'] == 'Bacteria'
    calls = genome_calls({'g1': '/in/g1.fna', 'g2': '/in/g2.fna'}, {'run_gtdbtk': False, 'margie_sb': settings})
    assert calls['g1']['gene_caller'] == 'rasttk' and calls['g1']['source'] == 'metadata'
    # A genome the config says nothing about still goes to Prodigal while GTDB-Tk is off.
    assert calls['g2']['gene_caller'] == 'prodigal'


def test_later_files_win_and_no_files_read_as_empty(tmp_path):
    base, mine = tmp_path / 'template.yaml', tmp_path / 'config.yaml'
    base.write_text("margie_sb:\n  genome_info:\n    g1.fna:\n      domain: Archaea\n  threads: 4\n")
    mine.write_text(CONFIG)
    settings = _wf(None, [base, mine])._margie_sb_dict()
    assert settings['genome_info']['g1.fna'] == {'domain': 'Bacteria', 'genetic_code': '11'} and settings['threads'] == 4
    assert _wf(None)._margie_sb_dict() == {}
