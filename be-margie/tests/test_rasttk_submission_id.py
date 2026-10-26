"""RASTtk's step checks that its gene table and GFF come from one BV-BRC submission (margie_sb.smk,
run_rasttk). Each file's id is its first match: a gene table whose first line carries the id many
times (Mesorhizobium opportunistum's did) is the same submission, not another one."""

import re
import subprocess
from pathlib import Path

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'


def _check(tmp_path, tsv: str, gff: str) -> subprocess.CompletedProcess:
    text = SMK.read_text()
    start = text.index('        TSV_ID=$(')
    end = text.index('        echo "rasttk complete', start)
    script = text[start:end].replace('{{', '{').replace('}}', '}')
    (tmp_path / 'rast.tsv').write_text(tsv)
    (tmp_path / 'rast.gff').write_text(gff)
    script = (script.replace('{output.results}', str(tmp_path / 'rast.tsv')).replace('{output.gff}', str(tmp_path / 'rast.gff'))
              .replace('{wildcards.genome}', 'g'))
    assert not re.search(r'\{[a-z_.]+\}', script)
    return subprocess.run(['bash', '-c', 'set -euo pipefail\n' + script], capture_output=True, text=True)


def test_one_submission_passes_however_often_a_line_names_it(tmp_path):
    many = '\t'.join(['fig|6666666.1512905.peg.1'] + [f'fig|6666666.1512905.peg.{i}' for i in range(2, 30)])
    got = _check(tmp_path, f'contig_id\tfeature_id\nc1\t{many}\n', '##gff-version 3\nc1\tx\tCDS\t1\t9\t.\t+\t0\tID=fig|6666666.1512905.peg.1\n')
    assert got.returncode == 0, got.stderr


def test_two_submissions_stop_the_step(tmp_path):
    got = _check(tmp_path, 'c1\tfig|6666666.111.peg.1\n', 'c1\tx\tCDS\t1\t9\t.\t+\t0\tID=fig|6666666.222.peg.1\n')
    assert got.returncode == 1 and 'different BV-BRC submissions' in got.stderr
