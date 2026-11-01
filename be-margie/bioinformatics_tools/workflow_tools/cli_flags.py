'''dane_wf's options: --input, --output, --working-directory and --config (-i, -o, -w, -c). Each becomes
the key: value words the rest of dane_wf reads (input:, output_dir:, config:), so both forms run the
same way:

    dane_wf margie sb --input <genome file or folder> --output <folder> --working-directory <folder> --config <file>
    dane_wf margie sb input: <genome file or folder> output_dir: <folder> config: <file>

Paths become absolute. A relative one is read from --working-directory when it is given, else from
the current folder. Without --output, the results go in <working-directory>/margie-output.'''
from pathlib import Path

USAGE = ('dane_wf margie sb --input <genome file or folder> --output <folder> '
         '[--working-directory <folder>] [--config <config file>]')
OPTIONS = '''  -i, --input              a genome file, or a folder of genome files
  -o, --output             the folder the results go in
  -w, --working-directory  the folder relative paths are read from; without --output,
                           the results go in its margie-output folder
  -c, --config             a config file, read over ~/.config/bioinformatics-tools/config.yaml
  -h, --help               shows this'''
EXAMPLE = 'dane_wf margie sb -i genomes/ -o results/ margie_sb.selected_tools: rasttk,cog,kegg,pfam'
HELP = f'''Usage: {USAGE}

{OPTIONS}

Other settings go after them as key: value, for example margie_sb.resume: true:
  {EXAMPLE}'''

# Each option and the word dane_wf reads it as.
WORDS = {'--input': 'input:', '--output': 'output_dir:', '--config': 'config:'}
WORKING = '--working-directory'
SHORT = {'-i': '--input', '-o': '--output', '-w': WORKING, '-c': '--config'}
OUTPUT_IN_WORKING = 'margie-output'


class FlagError(ValueError):
    '''An option dane_wf cannot read.'''


def wants_help(argv: list[str]) -> bool:
    return any(a in ('--help', '-h') for a in argv)


def to_words(argv: list[str], cwd: str | Path | None = None) -> list[str]:
    '''argv (without the program's name) with each option as its key: value words, after the others.'''
    words, given = [], {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        name, eq, value = arg.partition('=')
        name = SHORT.get(name, name)
        if not name.startswith('--'):
            words.append(arg)
            i += 1
            continue
        if name not in WORDS and name != WORKING:
            raise FlagError(f'unknown option {name}: dane_wf takes -i/--input, -o/--output, '
                            '-w/--working-directory and -c/--config')
        if not eq:
            if i + 1 >= len(argv) or argv[i + 1].startswith('--') or argv[i + 1].partition('=')[0] in SHORT:
                raise FlagError(f'{name} needs a value')
            value = argv[i + 1]
            i += 1
        if name in given:
            raise FlagError(f'{name} is given twice')
        if not value.strip():
            raise FlagError(f'{name} needs a value')
        given[name] = value
        i += 1

    for name, word in WORDS.items():
        if name in given and word in words:
            raise FlagError(f'{name} and {word} are both given')

    base = Path(cwd) if cwd is not None else Path.cwd()
    if WORKING in given:
        base = _absolute(given[WORKING], base)
    out = list(words)
    for name, word in WORDS.items():
        if name in given:
            out += [word, str(_absolute(given[name], base))]
    if WORKING in given and '--output' not in given and 'output_dir:' not in words:
        out += ['output_dir:', str(base / OUTPUT_IN_WORKING)]
    return out


def _absolute(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path
