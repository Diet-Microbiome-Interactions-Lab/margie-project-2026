"""TMbed reads ProtT5 from its package's models/t5, which the rule binds from db/tmbed/t5. When
config.json there is missing, TMbed downloads the model into the container's read-only /models
and stops with "Read-only file system". The links in db/tmbed/t5 had led to an older database
folder, so the rule now names a missing file or broken link before it starts. These run the
rule's own check with bash."""

import re
import subprocess
from pathlib import Path

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'
FILES = ('config.json', 'pytorch_model.bin', 'spiece.model', 'tokenizer_config.json', 'special_tokens_map.json')


def _check(model_dir: Path):
    rule = re.search(r"rule run_tmbed:.*?\nrule ", SMK.read_text(), re.S).group(0)
    code = re.search(r"\n( *for f in config\.json .*?\n *done)\n", rule, re.S).group(1)
    code = code.replace('{params.model_dir}', str(model_dir)).replace('{{', '{').replace('}}', '}')
    return subprocess.run(['bash', '-c', f'set -euo pipefail\n{code}\necho READY\n'],
                          capture_output=True, text=True, timeout=20)


def _models(tmp_path: Path) -> tuple[Path, Path]:
    snap = tmp_path / 'tmbed' / 'models--Rostlab--prot_t5_xl_half_uniref50-enc' / 'snapshots' / 'abc'
    snap.mkdir(parents=True)
    t5 = tmp_path / 'tmbed' / 't5'
    t5.mkdir()
    for f in FILES:
        (snap / f).write_text('x\n')
        (t5 / f).symlink_to(snap / f)
    return tmp_path / 'tmbed', snap


def test_the_model_files_in_place_let_tmbed_start(tmp_path):
    model_dir, _ = _models(tmp_path)
    done = _check(model_dir)
    assert done.returncode == 0 and 'READY' in done.stdout


def test_a_link_to_a_moved_folder_is_named_before_tmbed_starts(tmp_path):
    model_dir, _ = _models(tmp_path)
    (model_dir / 't5' / 'config.json').unlink()
    (model_dir / 't5' / 'config.json').symlink_to(tmp_path / 'db' / 'tmbed' / 'config.json')
    done = _check(model_dir)
    assert done.returncode == 1 and 'READY' not in done.stdout
    assert f'{model_dir}/t5/config.json is missing or a broken link' in done.stderr
