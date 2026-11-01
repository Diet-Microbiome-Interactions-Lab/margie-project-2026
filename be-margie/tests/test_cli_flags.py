"""dane_wf's options (workflow_tools/cli_flags.py): --input, --output, --working-directory and --config
read as the key: value words dane_wf takes, so `dane_wf margie sb --input ... --output ...` and
`dane_wf margie sb input: ... output_dir: ...` run the same way."""
import sys
from unittest.mock import patch

import pytest

from bioinformatics_tools.workflow_tools import cli_flags, main
from bioinformatics_tools.workflow_tools.cli_flags import FlagError, to_words


def test_each_option_becomes_its_words_after_the_others():
    assert to_words(['margie', 'sb', '--input', '/g', '--output', '/out', '--config', '/c.yaml',
                     'margie_sb.resume:', 'true']) == [
        'margie', 'sb', 'margie_sb.resume:', 'true', 'input:', '/g', 'output_dir:', '/out', 'config:', '/c.yaml']


def test_an_option_may_carry_its_value_after_an_equals_sign():
    assert to_words(['margie', 'sb', '--input=/g', '--output=/o']) == ['margie', 'sb', 'input:', '/g', 'output_dir:', '/o']


def test_the_short_options_read_as_the_long_ones(tmp_path):
    assert to_words(['margie', 'sb', '-i', 'genomes', '-o', '/out', '-c', '/c.yaml', '-w', str(tmp_path)]) == [
        'margie', 'sb', 'input:', str(tmp_path / 'genomes'), 'output_dir:', '/out', 'config:', '/c.yaml']
    assert to_words(['margie', 'sb', '-i=/g', '-w', str(tmp_path)]) == [
        'margie', 'sb', 'input:', '/g', 'output_dir:', str(tmp_path / 'margie-output')]


def test_a_value_that_starts_with_a_dash_is_a_value():
    assert to_words(['margie', 'sb', '--input', '/g', 'margie_sb.offset:', '-1']) == [
        'margie', 'sb', 'margie_sb.offset:', '-1', 'input:', '/g']


def test_the_key_value_form_is_left_as_it_is():
    words = ['margie', 'sb', 'input:', 'genomes', 'output_dir:', 'out', 'margie_sb.selected_tools:', 'rasttk,cog']
    assert to_words(words, cwd='/somewhere') == words


def test_relative_paths_are_read_from_the_current_folder(tmp_path):
    assert to_words(['margie', 'sb', '--input', 'g.fna', '--output', 'out'], cwd=tmp_path) == [
        'margie', 'sb', 'input:', str(tmp_path / 'g.fna'), 'output_dir:', str(tmp_path / 'out')]


def test_the_working_directory_reads_relative_paths_and_houses_the_results_without_output(tmp_path):
    work = tmp_path / 'project'
    assert to_words(['margie', 'sb', '--input', 'genomes', '--working-directory', str(work), '--config', 'run.yaml'],
                    cwd='/elsewhere') == [
        'margie', 'sb', 'input:', str(work / 'genomes'), 'config:', str(work / 'run.yaml'),
        'output_dir:', str(work / 'margie-output')]


def test_an_output_given_wins_over_the_working_directory(tmp_path):
    words = to_words(['margie', 'sb', '--input', '/g', '--working-directory', str(tmp_path), '--output', '/results'])
    assert words[-2:] == ['output_dir:', '/results'] and 'margie-output' not in ' '.join(words)
    words = to_words(['margie', 'sb', '--input', '/g', '--working-directory', 'w', 'output_dir:', '/r'], cwd=tmp_path)
    assert words.count('output_dir:') == 1


def test_a_home_path_is_expanded(tmp_path):
    with patch.dict('os.environ', {'HOME': str(tmp_path)}):
        assert to_words(['margie', 'sb', '--input', '~/g.fna'])[-1] == str(tmp_path / 'g.fna')


@pytest.mark.parametrize('argv, says', [
    (['margie', 'sb', '--genomes', '/g'], 'unknown option --genomes'),
    (['margie', 'sb', '--input'], '--input needs a value'),
    (['margie', 'sb', '--input', '--output', '/o'], '--input needs a value'),
    (['margie', 'sb', '--input=', '--output', '/o'], '--input needs a value'),
    (['margie', 'sb', '--input', '/a', '--input', '/b'], '--input is given twice'),
    (['margie', 'sb', '--input', '/a', 'input:', '/b'], '--input and input: are both given'),
    (['margie', 'sb', '-i', '-o', '/o'], '--input needs a value'),
    (['margie', 'sb', '-i', '/a', '--input', '/b'], '--input is given twice'),
    (['margie', 'sb', '-x', '/a', '--genome', '/b'], 'unknown option --genome'),
])
def test_an_option_it_cannot_read_stops_it(argv, says):
    with pytest.raises(FlagError, match=says):
        to_words(argv)


def test_dane_wf_reads_the_options_as_the_key_value_form(tmp_path, capsys):
    """The command line itself: dane_wf's settings come out the same for both forms."""
    seen = []

    class Recorder:
        def run(self):
            seen.append(list(sys.argv[1:]))

    with patch.object(main, 'WorkflowBase', Recorder), patch.object(main, 'config_logging_for_app'):
        with patch.object(sys, 'argv', ['dane_wf', 'margie', 'sb', '--input', '/g', '--output', '/o']):
            main.cli()
        with patch.object(sys, 'argv', ['dane_wf', 'margie', 'sb', 'input:', '/g', 'output_dir:', '/o']):
            main.cli()
    assert seen[0] == seen[1] == ['margie', 'sb', 'input:', '/g', 'output_dir:', '/o']


def test_dane_wf_shows_its_options_and_stops_on_one_it_cannot_read(capsys):
    with patch.object(sys, 'argv', ['dane_wf', 'margie', 'sb', '--help']), pytest.raises(SystemExit) as done:
        main.cli()
    assert done.value.code == 0 and '--working-directory' in capsys.readouterr().out
    with patch.object(sys, 'argv', ['dane_wf', 'margie', 'sb', '--genomes', '/g']), pytest.raises(SystemExit) as done:
        main.cli()
    assert done.value.code == 2 and 'unknown option --genomes' in capsys.readouterr().err
    assert cli_flags.USAGE.startswith('dane_wf margie sb --input')


def test_an_input_that_is_not_there_stops_the_run_with_its_path(tmp_path):
    from unittest.mock import MagicMock

    from bioinformatics_tools.workflow_tools.workflow import WorkflowBase
    wf = WorkflowBase.__new__(WorkflowBase)
    values = {'input': str(tmp_path / 'no-genomes'), 'main_database': str(tmp_path / 'm.db')}
    wf.conf = MagicMock()
    wf.conf.get = MagicMock(side_effect=lambda *a: values[a[0]] if len(a) == 1 else values.get(a[0], a[1]))
    wf.failed = MagicMock()
    assert wf.do_margie_sb(mode='dev') == 1
    wf.failed.assert_called_once_with(f'Input not found: {tmp_path / "no-genomes"}')
