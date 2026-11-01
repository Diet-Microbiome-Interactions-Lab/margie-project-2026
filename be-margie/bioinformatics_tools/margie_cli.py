'''The MARGIE command line. `margie` opens a prompt where MARGIE's commands run (dane_wf, the
pipeline; dane and misc, the file and other tools), `cd` changes folder, and any other line goes to
the system shell. `margie <command>` runs one command and returns its exit code.'''
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from bioinformatics_tools.workflow_tools.cli_flags import EXAMPLE, OPTIONS, USAGE

COMMANDS = ('dane_wf', 'dane', 'misc')
BANNER = 'MARGIE command line | help shows how to run MARGIE | exit leaves'
HELP = f'''MARGIE command line

  margie               opens the MARGIE prompt, where the commands below run
  margie <command>     runs one command and returns, for example
                         margie dane_wf margie sb -i genomes/ -o results/
  margie --help        shows this

Running MARGIE on a genome file or a folder of genomes:
  {USAGE}

{OPTIONS}

  Other settings go after them as key: value, for example margie_sb.resume: true:
    {EXAMPLE}
  Settings and databases: ~/.config/bioinformatics-tools/config.yaml

At the prompt:
  dane ...       MARGIE's file tools         misc ...   MARGIE's other tools
  cd <folder>    changes folder              help       shows this
  exit           leaves (or Ctrl-D)          any other line runs in the system shell'''
HISTORY = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state') / 'margie' / 'cli-history'


def program(name: str) -> str | None:
    '''The command installed beside this Python (the same MARGIE), else the one on PATH.'''
    here = Path(sys.executable).parent / name
    return str(here) if here.exists() else shutil.which(name)


def run_line(line: str) -> int | None:
    '''Runs one line of the prompt; returns its exit code, or None to leave.'''
    try:
        words = shlex.split(line)
    except ValueError as err:
        print(f'margie: {err}', file=sys.stderr)
        return 2
    if not words:
        return 0
    head = words[0]
    if head in ('exit', 'quit'):
        return None
    if head in ('help', '--help', '-h'):
        print(HELP)
        return 0
    if head == 'cd':
        try:
            os.chdir(Path(words[1] if len(words) > 1 else '~').expanduser())
        except OSError as err:
            print(f'cd: {err.strerror}: {words[1] if len(words) > 1 else "~"}', file=sys.stderr)
            return 1
        return 0
    if head in COMMANDS:
        found = program(head)
        if not found:
            print(f'margie: {head} is not installed with this MARGIE', file=sys.stderr)
            return 127
        return subprocess.run([found, *words[1:]]).returncode
    return subprocess.run(line, shell=True).returncode


def _history(on: bool) -> None:
    try:
        import readline
        if on:
            HISTORY.parent.mkdir(parents=True, exist_ok=True)
            if HISTORY.exists():
                readline.read_history_file(HISTORY)
        else:
            readline.set_history_length(1000)
            readline.write_history_file(HISTORY)
    except (ImportError, OSError):
        pass


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        sys.exit(run_line(shlex.join(argv)) or 0)
    _history(True)
    print(BANNER)
    try:
        while True:
            try:
                line = input(f'margie {Path.cwd().name or "/"}> ')
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue
            try:
                if run_line(line) is None:
                    break
            except KeyboardInterrupt:
                print()
    finally:
        _history(False)
