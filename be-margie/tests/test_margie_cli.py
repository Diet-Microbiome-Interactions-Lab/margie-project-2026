"""The MARGIE command line (bioinformatics_tools/margie_cli.py): `margie` opens a prompt where
dane_wf, dane and misc run, cd changes folder and other lines go to the system shell; `margie
<command>` runs one command."""
import os
import sys
from unittest.mock import patch

import pytest

from bioinformatics_tools import margie_cli


def test_a_margie_command_runs_the_one_installed_with_this_margie(tmp_path):
    fake = tmp_path / 'dane_wf'
    fake.write_text('#!/bin/sh\necho "ran $*"\nexit 3\n')
    fake.chmod(0o755)
    with patch.object(margie_cli, 'program', return_value=str(fake)):
        assert margie_cli.run_line('dane_wf margie sb --input "/my genomes" --output /out') == 3


def test_cd_changes_the_folder_later_lines_run_in(tmp_path):
    here = os.getcwd()
    try:
        assert margie_cli.run_line(f'cd {tmp_path}') == 0
        assert os.getcwd() == os.path.realpath(tmp_path)
        assert margie_cli.run_line('cd /no/such/folder') == 1
    finally:
        os.chdir(here)


def test_other_lines_go_to_the_shell_and_exit_leaves(tmp_path):
    target = tmp_path / 'made'
    assert margie_cli.run_line(f'touch {target}') == 0 and target.exists()
    assert margie_cli.run_line('exit') is None and margie_cli.run_line('') == 0
    assert margie_cli.run_line('echo "unclosed') == 2


def test_a_missing_command_says_so(capsys):
    with patch.object(margie_cli, 'program', return_value=None):
        assert margie_cli.run_line('dane_wf margie sb') == 127
    assert 'dane_wf is not installed' in capsys.readouterr().err


def test_the_prompt_runs_lines_until_exit_and_one_command_runs_without_it(capsys):
    with patch.object(margie_cli, '_history'), patch('builtins.input', side_effect=['help', 'exit']):
        margie_cli.main([])
    assert capsys.readouterr().out.count('MARGIE command line') == 2
    with patch.object(margie_cli, 'run_line', return_value=4) as run, pytest.raises(SystemExit) as done:
        margie_cli.main(['dane_wf', 'margie', 'sb', '--input', '/my genomes'])
    assert done.value.code == 4 and run.call_args.args[0] == "dane_wf margie sb --input '/my genomes'"


def test_the_commands_come_from_beside_this_python():
    assert margie_cli.program('python3') in (os.path.join(os.path.dirname(sys.executable), 'python3'),
                                              __import__('shutil').which('python3'))
