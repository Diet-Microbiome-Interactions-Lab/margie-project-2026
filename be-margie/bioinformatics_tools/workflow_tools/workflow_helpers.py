"""
Shared utilities for Snakemake workflows.

Provides configuration helpers and standardized path generation.
Import into Snakemake files to access config and generate output paths.
"""
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Repo root (the bioinformatics-tools checkout) for machine-agnostic fallbacks.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Fallback root-path defaults (Profile UI, sif_dir, db_path, do_margie_sb).
WORKFLOW_PATH_DEFAULTS: dict[str, dict[str, str]] = {
    'margie_sb': {
        'sif_path': '',
        # The tools' reference databases (read only, shared by everyone).
        'db_root': '',
        'input_path': '',
        'output_path': '',
    },
    'margie': {
        # No input_path default: margie takes one specific genome file.
        'output_path': '',
    },
}


# Each tool's default threads, memory (MB) and run time (minutes), set from what MARGIE's runs used
# (SLURM accounting, October 2026: CPU efficiency, peak memory, run time). A failed attempt runs once
# more with twice the memory and time (margie_sb.smk, tool_mem and tool_runtime). Settings shows these
# as margie_sb.<tool>.threads|mem_mb|runtime, and a saved value wins.
TOOL_RESOURCES = {
    'quast': (2, 4000, 120),
    'gtdbtk': (16, 32000, 120),  # the identify step; margie_sb.gtdbtk.classify uses GTDBTK_CLASSIFY_RESOURCES
    'rasttk': (2, 4000, 120),
    'prodigal': (1, 4000, 60),
    'cog': (4, 4000, 60),
    'kegg': (8, 8000, 90),
    'eggnog': (16, 64000, 180),
    'uniprot': (4, 4000, 60),
    'pfam': (4, 4000, 120),
    'tigrfam': (4, 4000, 60),
    'merops': (4, 4000, 30),
    'tcdb': (4, 4000, 30),
    'dbcan': (8, 8000, 60),
    'pgap': (4, 4000, 90),
    'geneprop': (1, 2000, 30),
    'interpro': (8, 16000, 300),
    'operon': (2, 2000, 30),
    'phobius': (2, 2000, 60),
    'tmbed': (8, 48000, 1440),
    'signalp6': (8, 6000, 180),
    'envelope': (1, 1000, 30),
    'deepsig': (2, 2000, 60),
    'psortb': (2, 2000, 180),
    'consolidation': (1, 4000, 30),
    'labeling': (1, 4000, 30),
    'scoring_heuristic': (1, 6000, 30),
    'fingerprint': (1, 4000, 30),
    'fingerprint_database': (1, 4000, 15),
}
# GTDB-Tk's full classification (classify_wf with species placement), when margie_sb.gtdbtk.classify is on.
GTDBTK_CLASSIFY_RESOURCES = (64, 460000, 240)
# Partitions other than the cluster default: TMbed's ProtT5 runs for hours on CPU.
TOOL_PARTITIONS = {'tmbed': 'highmem', 'llm': 'gpu'}


# A tool's resource settings, as Settings writes them under margie_sb.<tool>.
_TOOL_RESOURCE_LEAVES = ('threads', 'mem_mb', 'runtime', 'partition')


def rc(key: str, default:str|None = None, config=None):
    """
    Rule Config: Get config value using dot notation for nested keys.

    Supports arbitrary nesting via dot notation:
    key: Config key using dot notation (e.g., 'prodigal.mem_mb')

    Returns:
        The config value OR default OR if not set
    """
    if config is None:
        raise ValueError("config parameter is required")

    # Split key by dots and traverse nested dict
    parts = key.split('.')
    # Settings saves a tool's resources as margie_sb.<tool>.<leaf>; that value wins over <tool>.<leaf>.
    if len(parts) == 2 and parts[1] in _TOOL_RESOURCE_LEAVES:
        saved = config.get('margie_sb', {}) if isinstance(config, dict) else {}
        saved = saved.get(parts[0]) if isinstance(saved, dict) else None
        if isinstance(saved, dict) and saved.get(parts[1]) not in (None, ''):
            return saved[parts[1]]
    value = config

    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default

    return value


def rc_bool(key: str, default: bool = True, config=None) -> bool:
    """Like rc(), for boolean flags such as 'run_quast'.

    Accepts a real bool (YAML --configfile) or a string (`--config key=value`),
    so the string 'false' is not treated as truthy."""
    value = rc(key, default, config=config)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ('false', '0', 'no', 'off', '')
    return bool(value)


def get_input_stem(config):
    """
    Extract stem (filename without extension) from input file.
    """
    input_file = config.get('input_fasta', 'output')
    return Path(input_file).stem


def config_path(value: str | Path | None) -> str:
    """Expands user-home markers in config-supplied filesystem paths."""
    if value is None:
        return ''
    return str(Path(value).expanduser())


def get_workflow_prefix(config) -> str | Path:
    """
    Get output directory prefix with stem subdirectory and trailing slash.

    Each genome gets isolated in its own subdirectory for clean batch processing.

    Example:
        input_fasta: 'ecoli.fasta'
        output_dir: '/results/batch-run'
        → '/results/batch-run/ecoli/'
    """
    output_dir = config.get('output_dir', '')
    if not output_dir:
        return ''

    stem = get_input_stem(config)
    abs_path = Path(output_dir).resolve()
    return f"{abs_path}/{stem}/"


def get_workflow_prefix_for(genome_stem: str, config) -> str:
    """Returns get_workflow_prefix() for an explicit genome stem, i.e. that
    genome's '{output_dir}/{genome_stem}/' folder in multi-genome runs.
    """
    output_dir = config.get('output_dir', '')
    if not output_dir:
        return ''

    abs_path = Path(output_dir).resolve()
    return f"{abs_path}/{genome_stem}/"


def get_container_outputs_prefix_for(genome_stem: str, config) -> str:
    """Returns the per-genome root for each tool's full container output,
    '{output_dir}/original_container_outputs/{genome_stem}/', kept apart from
    the lean rule outputs Snakemake tracks."""
    output_dir = config.get('output_dir', '')
    if not output_dir:
        return ''

    abs_path = Path(output_dir).resolve() / 'original_container_outputs'
    return f"{abs_path}/{genome_stem}/"


GENOME_EXTENSIONS = ('.fasta', '.fa', '.fna', '.fasta.gz', '.fa.gz', '.fna.gz')


def genome_stem(name: str) -> str:
    """Returns a genome file's key: the basename minus .gz and its recognised extension.

    .fasta and .fna map to the same key.
    """
    lowered = name.lower()
    if lowered.endswith('.gz'):
        name, lowered = name[:-3], lowered[:-3]
    for ext in ('.fasta', '.fna', '.fa'):
        if lowered.endswith(ext):
            return name[: -len(ext)]
    return Path(name).stem


def default_store_root() -> str:
    """Returns the default store root, /scratch/<cluster>/<user>/margie/margie-databases.

    A fallback for runs started outside the app, which always names the stores
    (api/services/user_stores.py); depot base copies are never written."""
    import os
    import socket
    cluster = (socket.getfqdn().split('.') + ['', ''])[1] or 'cluster'
    return f"/scratch/{cluster}/{os.environ.get('USER', 'user')}/margie/margie-databases"


def genome_calls(genomes: dict[str, str], config) -> dict[str, dict[str, str]]:
    """Returns each genome's domain, genetic code and gene caller from config alone.

    `margie_sb.genome_info` in config.yaml maps a genome file name or stem to
    {domain, genetic_code}. RASTtk needs both; a genome missing either is called
    by Prodigal unless GTDB-Tk runs, which determines both. Where the genome table
    leaves one out, the value GTDB-Tk's first step gave (the file `gtdbtk_early`
    names, written by workflow.py while the rest of GTDB-Tk goes on) fills it in.
    Computed at parse time so the Snakefile can split genomes between run_rasttk
    and run_prodigal.
    """
    run_gtdbtk = rc_bool('run_gtdbtk', True, config=config)
    meta = rc('margie_sb.genome_info', None, config=config) or rc('genome_info', None, config=config) or {}
    if not isinstance(meta, dict):
        meta = {}
    early = read_early_calls(rc(GTDBTK_EARLY, '', config=config)) if run_gtdbtk else {}
    by_key = {}
    for key, row in meta.items():
        if isinstance(row, dict):
            by_key.setdefault(str(key), row)
            by_key.setdefault(genome_stem(str(key)), row)
    out = {}
    for genome, fasta in genomes.items():
        # A genome renamed apart for this run (<name>--<hash>, a link) keeps its file's settings.
        original = Path(fasta).resolve().name
        row = (by_key.get(Path(fasta).name) or by_key.get(genome) or by_key.get(original)
               or by_key.get(genome_stem(original)) or {})
        raw = str(row.get('domain') or '').strip().lower()
        domain = 'Bacteria' if raw.startswith('b') else 'Archaea' if raw.startswith('a') else ''
        code = str(row.get('genetic_code') or '').strip()
        code = code if code.isdigit() else ''
        source = 'metadata' if domain or code else ('gtdbtk' if run_gtdbtk else 'none')
        found = early.get(genome, {})
        domain, code = domain or found.get('domain', ''), code or found.get('genetic_code', '')
        caller = 'rasttk' if run_gtdbtk or (domain and code) else 'prodigal'
        out[genome] = {'domain': domain, 'genetic_code': code, 'gene_caller': caller, 'source': source}
    return out


# ---- GTDB-Tk's first step ----
# The config key naming the file of domains and genetic codes GTDB-Tk's first step gave.
GTDBTK_EARLY = 'gtdbtk_early'
# GTDB-Tk's single-copy marker sets (CONFIG.BAC_MARKER_COUNT, CONFIG.AR_MARKER_COUNT).
_MARKERS = {'bac120': 120, 'ar53': 53}


def identify_calls(folder: str | Path, newer_than: float = 0.0) -> dict[str, dict[str, str]]:
    """Each genome's domain and genetic code from GTDB-Tk's identify step under `folder`, as soon
    as it has written them, while classify_wf goes on: the translation table it chose
    (gtdbtk.translation_table_summary.tsv, written last) and the domain whose single-copy markers
    it found the larger share of, ties to Bacteria, as GTDB-Tk's genome_domain decides it.
    Empty until the three files are there (and newer than `newer_than`)."""
    found = sorted(Path(folder).glob('**/identify/gtdbtk.translation_table_summary.tsv'),
                   key=lambda f: f.stat().st_mtime)
    if not found or found[-1].stat().st_mtime < newer_than:
        return {}
    here = found[-1].parent
    tables = {}
    for line in found[-1].read_text().splitlines():
        parts = line.split('\t')
        if len(parts) >= 2 and parts[1].strip().isdigit():
            tables[parts[0]] = parts[1].strip()
    shares: dict[str, dict[str, float]] = {}
    for name, total in _MARKERS.items():
        summary = here / f'gtdbtk.{name}.markers_summary.tsv'
        if not summary.exists():
            return {}
        for line in summary.read_text().splitlines()[1:]:
            parts = line.split('\t')
            if len(parts) != 9 or not parts[1].isdigit() or not parts[3].isdigit():
                continue
            # Unique hits and multiple identical hits count as single copy (get_single_copy_hits).
            shares.setdefault(parts[0], {})[name] = 100.0 * (int(parts[1]) + int(parts[3])) / total
    calls = {}
    for genome, table in tables.items():
        share = shares.get(genome, {})
        if 'bac120' in share and 'ar53' in share:
            calls[genome] = {'domain': 'Bacteria' if share['bac120'] >= share['ar53'] else 'Archaea',
                             'genetic_code': table}
    return calls


def write_early_calls(path: str | Path, calls: dict[str, dict[str, str]]) -> None:
    """Writes the domains and genetic codes GTDB-Tk's first step gave, one genome a line."""
    lines = ['genome\tdomain\tgenetic_code'] + [f"{g}\t{c['domain']}\t{c['genetic_code']}" for g, c in sorted(calls.items())]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text('\n'.join(lines) + '\n')


def read_early_calls(path: str | Path | None) -> dict[str, dict[str, str]]:
    """Reads write_early_calls' file; empty when there is none."""
    try:
        lines = Path(path).read_text().splitlines()[1:] if path else []
    except OSError:
        return {}
    calls = {}
    for line in lines:
        parts = line.split('\t')
        if len(parts) == 3 and parts[1] in ('Bacteria', 'Archaea') and parts[2].isdigit():
            calls[parts[0]] = {'domain': parts[1], 'genetic_code': parts[2]}
    return calls


def gene_call_files(prefix: str, caller: str) -> dict[str, str]:
    """A genome's gene-call files under its results prefix, as margie_sb.smk writes them: RASTtk's
    in rasttk/ (rast.*), Prodigal's in prodigal/ (prodigal.*). Keys: table, faa, gff, computed
    (the compute token) and loaded (the database token)."""
    folder, stem = ('prodigal', 'prodigal') if caller == 'prodigal' else ('rasttk', 'rast')
    return {'table': f"{prefix}{folder}/{stem}.tsv", 'faa': f"{prefix}{folder}/{stem}.faa",
            'gff': f"{prefix}{folder}/{stem}.gff", 'computed': f"{prefix}{folder}/{folder}_compute.tkn",
            'loaded': f"{prefix}{folder}/{folder}_db.tkn"}


def discover_genomes(input_path: str, recursive: bool = False) -> dict[str, str]:
    """Resolves an input path to a {stem: filepath} map.

    A file gives one entry; a directory is scanned for recognised genome files,
    sorted by name. Non-recursive by default, so nested reference genomes (e.g.
    synteny-input/<genome>/...) stay out; recursive=True includes them."""
    path = Path(config_path(input_path))
    if path.is_dir():
        entries = path.rglob('*') if recursive else path.iterdir()
        genomes = {}
        for entry in sorted(entries):
            if entry.is_file() and entry.name.lower().endswith(GENOME_EXTENSIONS):
                stem = genome_stem(entry.name)
                previous = genomes.get(stem)
                if previous is not None:
                    # Same stem is the same genome only if the content hashes match.
                    from bioinformatics_tools.workflow_tools.load_to_db import compute_fasta_hash
                    if compute_fasta_hash(previous) == compute_fasta_hash(str(entry)):
                        LOGGER.info(
                            "Genome '%s' present as both %s and %s with identical "
                            "content -- same genome, using %s",
                            stem, Path(previous).name, entry.name, Path(previous).name)
                        continue
                    raise ValueError(
                        f"Two DIFFERENT genomes map to the same name '{stem}': "
                        f"{previous} and {entry}. Their contents differ, so one "
                        f"would overwrite the other's outputs. Rename one so each "
                        f"genome has a distinct name.")
                genomes[stem] = str(entry)
        return genomes
    return {genome_stem(path.name): str(path)}


def fixed_path(relative_path: str, config=None) -> str:
    """Prepend workflow prefix to a relative path. E.g., 'prodigal/file.faa' → 'results/prodigal/file.faa'"""
    if config is None:
        raise ValueError("config parameter is required")

    prefix = get_workflow_prefix(config)
    return f"{prefix}{relative_path}"


def build_filepath(config_string: str, suffix: str, default: str = None, config=None) -> str:
    """
    Build filepath with config lookup and auto-generation.

    Priority: 1) Config value, 2) Default path, 3) Auto-generate {tool}/{stem}-{tool}.{suffix}

    Examples:
        build_filepath('pfam.output', suffix='tsv') → 'results/pfam/ecoli-pfam.tsv'
        build_filepath('cog.output', suffix='txt', default='cog/results.txt') → 'results/cog/results.txt'
        # With config pfam.output='custom.tsv' → 'results/pfam/custom.tsv'
    """
    if config is None:
        raise ValueError("config parameter is required")

    prefix = get_workflow_prefix(config)

    parts = config_string.split('.')
    if len(parts) < 1:
        raise ValueError(f"config_string must have at least one part, got: {config_string}")
    tool = parts[0]

    # Check config first
    config_filename = rc(config_string, None, config=config)
    if config_filename:
        return f"{prefix}{tool}/{config_filename}"

    # Use default if provided
    if default:
        return f"{prefix}{default}"

    # Auto-generate with stem
    stem = get_input_stem(config)
    return f"{prefix}{tool}/{stem}-{tool}.{suffix}"


def db_token(tool, config=None):
    """Generate database token path: {tool}/{tool}_db.tkn"""
    return fixed_path(f'{tool}/{tool}_db.tkn', config=config)


def sif_dir(config=None, workflow_id: str | None = None) -> str:
    """Returns the configured SIF directory as an absolute user path.

    Reads '<workflow_id>.sif_path' when workflow_id is given, else 'sif_path'.
    """
    if config is None:
        raise ValueError("config parameter is required")

    key = f'{workflow_id}.sif_path' if workflow_id else 'sif_path'
    fallback = WORKFLOW_PATH_DEFAULTS.get(workflow_id, {}).get('sif_path', '~/.cache/bioinformatics-tools')
    return config_path(rc(key, fallback, config=config))


def sif_path(filename: str, config=None, workflow_id: str | None = None) -> str:
    """Resolves a container filename relative to the configured SIF directory."""
    if config is None:
        raise ValueError("config parameter is required")

    return str(Path(sif_dir(config=config, workflow_id=workflow_id)) / filename)


def db_path(tool: str, config=None, default_root: str | None = None,
            workflow_id: str | None = None) -> str:
    """Resolves a tool database path from db.<tool> or <workflow_id>.db_root/<tool>."""
    if config is None:
        raise ValueError("config parameter is required")

    explicit = rc(f'db.{tool}', None, config=config)
    if explicit:
        return config_path(explicit)

    if default_root is None:
        default_root = WORKFLOW_PATH_DEFAULTS.get(workflow_id, {}).get('db_root', '')

    db_root_key = f'{workflow_id}.db_root' if workflow_id else 'db_root'
    db_root = rc(db_root_key, default_root, config=config)
    return str(Path(config_path(db_root)) / tool)
