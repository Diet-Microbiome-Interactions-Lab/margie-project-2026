"""
Per-protein annotation cache in the job's SQLite database, keyed by the protein's
sequence hash and a tool_key: the tool and the settings that change its answer (its thresholds,
InterPro's analyses). A new version of a tool's container or database leaves the cache as it is,
so genomes annotated once are not run again.

split() writes novel.faa plus the cached rows before a tool runs, MERGE_SH joins
both into the tool's results file, and store() adds the genome's new proteins with the
genome they came from, so a later genome's report names the genomes it matched. A protein
already cached for a tool is not run again; a tool new to it is run and added, and the
protein's other tools stay as they are. When a cached protein is computed anyway (cached by
another genome during the run), its result columns are compared with the cached ones exactly,
and a difference replaces the cached entry.
Only tools whose rows depend on the protein alone are listed in TOOLS.

link_genome() records each genome's proteins and genes by hash (protein_genomes,
genome_proteomes, genome_genes), so a set of proteins names its genome; record_fingerprints()
adds each gene's fingerprint, and each protein's (protein_fingerprints: built from the protein's
own annotations, so one per protein hash, replaced when a later genome's differs).
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from bioinformatics_tools.workflow_tools import db_turn
    from bioinformatics_tools.workflow_tools.genome_identity import protein_hash, read_fasta
    from bioinformatics_tools.workflow_tools.workflow_helpers import db_path as tool_db_path, rc, sif_path
except ImportError:  # imported from margie_sb.smk, with this folder on sys.path
    import db_turn
    from genome_identity import protein_hash, read_fasta
    from workflow_helpers import db_path as tool_db_path, rc, sif_path

LOGGER = logging.getLogger(__name__)

SCHEMA = 2
WORKFLOW = 'margie_sb'
PC_DIR = 'protein-cache'

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS protein_cache (
    aa_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    tool_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    lines TEXT NOT NULL,
    cached_at TEXT NOT NULL,
    genome TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tool, tool_key, filename, aa_hash)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS protein_cache_header (
    tool TEXT NOT NULL,
    tool_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    header TEXT NOT NULL,
    PRIMARY KEY (tool, tool_key, filename)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS protein_genomes (
    aa_hash TEXT NOT NULL,
    genome_hash TEXT NOT NULL,
    PRIMARY KEY (aa_hash, genome_hash)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS protein_genomes_by_genome ON protein_genomes (genome_hash);
CREATE TABLE IF NOT EXISTS genome_proteomes (
    genome_hash TEXT PRIMARY KEY,
    proteins INTEGER NOT NULL,
    protein_set TEXT NOT NULL,
    names TEXT NOT NULL DEFAULT '[]',
    first_linked TEXT NOT NULL,
    last_linked TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS genome_proteomes_by_set ON genome_proteomes (protein_set);
CREATE TABLE IF NOT EXISTS genome_genes (
    genome_hash TEXT NOT NULL,
    gene_hash TEXT NOT NULL,
    aa_hash TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (genome_hash, gene_hash)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS protein_fingerprints (
    aa_hash TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL,
    core_fingerprint TEXT NOT NULL DEFAULT '',
    extra_fingerprint TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS protein_descriptors (
    aa_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    position INTEGER NOT NULL,
    value TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (aa_hash, tool)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS genome_protein_descriptors (
    genome_hash TEXT NOT NULL,
    aa_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    value TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (genome_hash, aa_hash, tool)
) WITHOUT ROWID;
"""

# The protein record (protein_records): one row a protein, read by eye when checking hashes or
# restoring results. The seven tools every run has (C1's sources) come first and make the core
# fingerprint; the other tools follow in this order, tools added later after them, and make the
# additional fingerprint, so a new tool changes only that. Tools whose answer depends on the genome
# as well (PSORTb on its Gram class, DeepSig on its organism class) are kept by genome hash and
# protein hash (genome_protein_descriptors), as they are restored.
CORE_TOOLS = ['COG', 'KEGG', 'EGGNOG', 'UNIPROT', 'PFAM', 'TIGRFAM', 'PGAP']
EXTRA_TOOLS = ['HAMAP', 'NCBIFAM', 'PIRSF', 'CDD', 'DBCAN', 'MEROPS', 'TCDB', 'SIGNALP6', 'PHOBIUS', 'TMBED']
GENOME_TOOLS = ['PSORTB', 'DEEPSIG']
RECORDS_VIEW = """
CREATE VIEW IF NOT EXISTS protein_records AS
SELECT f.aa_hash AS protein_hash,
       (SELECT count(*) FROM protein_genomes g WHERE g.aa_hash = f.aa_hash) AS genomes,
       (SELECT group_concat(genome_hash, ', ') FROM protein_genomes g WHERE g.aa_hash = f.aa_hash) AS genome_hashes,
       f.fingerprint, f.core_fingerprint, f.extra_fingerprint, f.label,
""" + ",\n".join(f"       (SELECT value FROM protein_descriptors d WHERE d.aa_hash = f.aa_hash AND d.tool = '{t}') AS {t.lower()}"
                  for t in CORE_TOOLS) + """,
       (SELECT group_concat(tool || ': ' || value, ' | ') FROM (SELECT tool, value FROM protein_descriptors d
        WHERE d.aa_hash = f.aa_hash AND d.position >= 100 ORDER BY d.position, d.tool)) AS additional
FROM protein_fingerprints AS f;
"""

# InterPro's member databases, as margie_sb.smk names them.
INTERPRO_ALL_ANALYSES = {
    "AntiFam": "antifam", "CDD": "cdd", "Coils": "coils", "FunFam": "funfam",
    "Gene3D": "gene3d", "Hamap": "hamap", "MobiDBLite": "mobidb", "NCBIfam": "ncbifam",
    "PANTHER": "panther", "Pfam": "pfam", "PIRSF": "pirsf", "PIRSR": "pirsr",
    "PRINTS": "prints", "ProSitePatterns": "prosite_patterns", "ProSiteProfiles": "prosite_profiles",
    "SFLD": "sfld", "SMART": "smart", "SUPERFAMILY": "superfamily",
}
INTERPRO_DEFAULT_ANALYSES = ["Hamap", "NCBIfam", "CDD", "PIRSF"]

# Tools whose rows depend only on the protein; the first file marks it cached.
_SIMPLE = ['cog', 'kegg', 'eggnog', 'uniprot', 'pfam', 'merops', 'tcdb', 'dbcan', 'pgap', 'tmbed', 'signalp6']
TOOLS = _SIMPLE + ['tigrfam', 'phobius', 'interpro']

# Rule params that change a tool's answer, with margie_sb.smk's defaults.
TOOL_PARAMS = {
    'cog': [('cog.evalue', '1e-2')],
    'merops': [('merops.evalue', '1e-5')],
    'tcdb': [('tcdb.evalue', '1e-5'), ('tcdb.pct_id', '30')],
    'uniprot': [('uniprot.evalue', '1e-5'), ('uniprot.pct_id', '30')],
}
# Tools run from cluster modules rather than a container.
MODULE_TOOLS = {'signalp6': 'biocontainers/default + signalp6/6.0-fast --organism other --mode fast'}
NO_DATABASE = {'phobius', 'signalp6'}


def interpro_analyses(cfg: dict) -> list[str]:
    return list(rc('interpro.analyses', INTERPRO_DEFAULT_ANALYSES, config=cfg))


def tool_files(tool: str, cfg: dict) -> list[tuple[str, str]]:
    """Returns (file name, kind) for each results file of the tool, marker file first.

    kind is tsv, tsv? (may be missing or empty) or domtbl (HMMER --domtblout)."""
    if tool in _SIMPLE:
        return [(f'{tool}_results.tsv', 'tsv')]
    if tool == 'tigrfam':
        return [('tigrfam_results.tsv', 'tsv'), ('tigrfam_domtbl.out', 'domtbl')]
    if tool == 'phobius':
        return [('phobius_results.tsv', 'tsv'), ('phobius_top1.tsv', 'tsv')]
    if tool == 'interpro':
        return [('interpro_results.tsv', 'tsv')] + [
            (f'interpro_{INTERPRO_ALL_ANALYSES[a]}_results.tsv', 'tsv?')
            for a in interpro_analyses(cfg) if a in INTERPRO_ALL_ANALYSES]
    raise KeyError(tool)


def _stat(path: str) -> list:
    try:
        st = os.stat(path)
        return [os.path.basename(path.rstrip('/')), st.st_size if not os.path.isdir(path) else 0, int(st.st_mtime)]
    except OSError:
        return [path, None, None]


def _params(tool: str, cfg: dict) -> dict:
    params = {k: str(rc(k, d, config=cfg)) for k, d in TOOL_PARAMS.get(tool, [])}
    if tool == 'interpro':
        analyses = interpro_analyses(cfg)
        params['analyses'] = analyses
        params['applications'] = str(rc('interpro.applications', ','.join(analyses), config=cfg))
    return params


def tool_key(tool: str, cfg: dict) -> str:
    """Hashes what the tool's answer depends on besides the protein that MARGIE keeps to: the
    tool and the settings that change results. Container and database versions stay out."""
    parts: dict = {'schema': SCHEMA, 'tool': tool, 'params': _params(tool, cfg)}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


_carried: set = set()


def _carry_over(conn, tool: str, cfg: dict, key: str) -> None:
    """Moves the tool's entries made under earlier keys (schema 1 named the container and database
    files) under this key, the newest entry of each protein first; an older duplicate goes. Runs
    once per tool and process, and finds nothing to do once the cache is moved."""
    if (tool, key) in _carried:
        return
    _carried.add((tool, key))
    # A tool whose answer depends on its settings keeps entries made under other settings apart:
    # an earlier key there can name another E-value, identity or set of InterProScan analyses.
    if TOOL_PARAMS.get(tool) or tool == 'interpro':
        return
    # The tool's keys, one seek each along the primary key (tool, tool_key, ...): a GROUP BY read
    # every entry of the tool, its current key's too, which took minutes a tool on a large cache.
    keys, after = [], ''
    while row := conn.execute('SELECT tool_key FROM protein_cache WHERE tool = ? AND tool_key > ? ORDER BY tool_key LIMIT 1',
                              (tool, after)).fetchone():
        after = row[0]
        keys.append(after)
    older = [k for k in keys if k != key]
    if not older:
        return
    # Newest first.
    newest = {k: conn.execute('SELECT max(cached_at) FROM protein_cache WHERE tool = ? AND tool_key = ?', (tool, k)).fetchone()[0] or ''
              for k in older}
    older.sort(key=lambda k: newest[k], reverse=True)
    moved = 0
    with conn:
        for old in older:
            moved += conn.execute('UPDATE OR IGNORE protein_cache SET tool_key = ? WHERE tool = ? AND tool_key = ?', (key, tool, old)).rowcount
            conn.execute('UPDATE OR IGNORE protein_cache_header SET tool_key = ? WHERE tool = ? AND tool_key = ?', (key, tool, old))
            conn.execute('DELETE FROM protein_cache WHERE tool = ? AND tool_key = ?', (tool, old))
            conn.execute('DELETE FROM protein_cache_header WHERE tool = ? AND tool_key = ?', (tool, old))
    LOGGER.info('protein cache: %d %s entries from %d earlier key(s) moved to the settings key', moved, tool, len(older))


def enabled(cfg: dict) -> bool:
    v = rc(f'{WORKFLOW}.protein_cache', True, config=cfg)
    return str(v).strip().lower() not in ('false', '0', 'no', 'off')




def pc_dir(prefix: str, tool: str) -> str:
    return f'{prefix}{tool}/{PC_DIR}'


def clear(prefix: str, tool: str) -> None:
    """Removes a split so the tool's rule reads rast.faa again."""
    shutil.rmtree(pc_dir(prefix, tool), ignore_errors=True)


# ---- database ----

def _connect(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db, timeout=120)
    conn.execute('PRAGMA busy_timeout=120000')
    # The index pages a call's lookups share stay in memory (SQLite keeps 2 MB by default); each
    # page read again is a trip to the cluster's storage.
    conn.execute(f'PRAGMA cache_size=-{CACHE_KIB}')
    conn.executescript(CREATE_SQL)
    have = {r[1] for r in conn.execute('PRAGMA table_info(protein_fingerprints)')}
    for col in ('core_fingerprint', 'extra_fingerprint'):
        if col not in have:
            conn.execute(f"ALTER TABLE protein_fingerprints ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
    conn.executescript(RECORDS_VIEW)
    # Caches made before the genome column: it is added, empty for the rows already there.
    if 'genome' not in {r[1] for r in conn.execute('PRAGMA table_info(protein_cache)')}:
        try:
            conn.execute("ALTER TABLE protein_cache ADD COLUMN genome TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError as exc:
            if 'duplicate column' not in str(exc):
                raise
    return conn


# Proteins written to the cache in one transaction by store(), and the pause after each, in which a
# writer waiting for the database's turn (a load, another of the run's caches) gets it.
STORE_CHUNK = 500
STORE_PAUSE = 0.3
# Proteins read in one query outside the write turn: a short read, so a writer's commit, which waits
# for the readers, waits little.
READ_CHUNK = 100
# SQLite's page cache per connection, KiB (256 MiB).
CACHE_KIB = 262144


def _chunks(items: list, n: int = 500):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _cached_hashes(conn, tool: str, key: str, filename: str, hashes: list[str]) -> set[str]:
    found: set[str] = set()
    for chunk in _chunks(hashes):
        found.update(r[0] for r in conn.execute(
            'SELECT aa_hash FROM protein_cache WHERE tool = ? AND tool_key = ? AND filename = ? '
            f'AND aa_hash IN ({",".join("?" * len(chunk))})', (tool, key, filename, *chunk)))
    return found


# ---- rows: remapped to this genome's feature ids and name ----

_DOMTBL_ID = re.compile(r'^(\S+\s+\S+\s+\S+\s+)(\S+)')


def _columns(header: str) -> tuple[int | None, int | None]:
    cols = header.rstrip('\n').split('\t')
    return (cols.index('feature_id') if 'feature_id' in cols else None,
            cols.index('organism_name') if 'organism_name' in cols else None)


def _row_id(line: str, kind: str, fid_col: int | None) -> str | None:
    if kind == 'domtbl':
        if line.startswith('#'):
            return None
        m = _DOMTBL_ID.match(line)
        return m.group(2) if m else None
    if fid_col is None:
        return None
    cols = line.split('\t')
    return cols[fid_col] if fid_col < len(cols) else None


def _remap(line: str, kind: str, cols: tuple[int | None, int | None], fid: str, genome: str) -> str:
    if kind == 'domtbl':
        return _DOMTBL_ID.sub(lambda m: m.group(1) + fid, line, count=1)
    fid_col, org_col = cols
    parts = line.split('\t')
    if fid_col is not None and fid_col < len(parts):
        parts[fid_col] = fid
    if org_col is not None and org_col < len(parts):
        parts[org_col] = genome
    return '\t'.join(parts)


def _read_rows(path: Path, kind: str) -> tuple[str | None, dict[str, list[str]]]:
    """Returns (header, {feature id: lines}) for one results file."""
    if not path.exists() or path.stat().st_size == 0:
        return None, {}
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    rows: dict[str, list[str]] = {}
    if kind == 'domtbl':
        head = []
        for line in lines:
            if line.startswith('#'):
                if not rows:
                    head.append(line)
                continue
            fid = _row_id(line, kind, None)
            if fid:
                rows.setdefault(fid, []).append(line)
        return '\n'.join(head[:3]), rows
    header, data = lines[0], lines[1:]
    fid_col, _ = _columns(header)
    if fid_col is None:
        return header, {}
    for line in data:
        fid = _row_id(line, kind, fid_col)
        if fid:
            rows.setdefault(fid, []).append(line)
    return header, rows


# ---- before the annotation stage ----

def _proteins(faa: str) -> list[tuple[str, str, str, str]]:
    """Returns (feature id, hash, header, sequence) for each protein of the genome."""
    return [(fid, protein_hash(seq), header, seq) for fid, header, seq in read_fasta(faa) if fid and seq]


def _source(genome: str, lines: str, org_col: int | None) -> str:
    """The genome a cached protein came from: recorded with it, else the organism its rows name."""
    if genome:
        return genome
    first = (lines or '').split('\n', 1)[0]
    parts = first.split('\t') if first else []
    return parts[org_col] if org_col is not None and org_col < len(parts) else ''


def split(db: str, faa: str, prefix: str, genome: str, tools: list[str], cfg: dict,
          sources: dict[str, dict[str, int]] | None = None) -> dict[str, tuple[int, int]]:
    """Writes novel.faa and the cached proteins' rows per tool; returns {tool: (cached, to run)}.
    `sources`, when given, receives {tool: {genome the cached proteins came from: proteins}}."""
    proteins = _proteins(faa)
    hashes = sorted({h for _, h, _, _ in proteins})
    now = {}
    conn = _connect(db)
    try:
        for tool in tools:
            key = tool_key(tool, cfg)
            _carry_over(conn, tool, cfg, key)
            files = tool_files(tool, cfg)
            cached = _cached_hashes(conn, tool, key, files[0][0], hashes)
            out = Path(pc_dir(prefix, tool))
            if out.exists():
                shutil.rmtree(out)  # working files from an earlier attempt
            (out / 'cached').mkdir(parents=True)
            with open(out / 'novel.faa', 'w') as fh:
                for fid, h, header, seq in proteins:
                    if h not in cached:
                        fh.write(f'>{header}\n')
                        for i in range(0, len(seq), 60):
                            fh.write(seq[i:i + 60] + '\n')
            want = sorted(cached)
            for n, (filename, kind) in enumerate(files):
                row = conn.execute('SELECT header FROM protein_cache_header WHERE tool = ? AND tool_key = ? AND filename = ?',
                                   (tool, key, filename)).fetchone()
                header = row[0] if row else None
                stored: dict[str, str] = {}
                came: dict[str, str] = {}
                for chunk in _chunks(want):
                    for h, lines, src in conn.execute(
                            'SELECT aa_hash, lines, genome FROM protein_cache WHERE tool = ? AND tool_key = ? AND filename = ? '
                            f'AND aa_hash IN ({",".join("?" * len(chunk))})', (tool, key, filename, *chunk)):
                        stored[h] = lines
                        came[h] = src
                cols = _columns(header) if header and kind != 'domtbl' else (None, None)
                if n == 0 and sources is not None:
                    tally: dict[str, int] = {}
                    for _, h, _, _ in proteins:
                        if h in cached:
                            src = _source(came.get(h, ''), stored.get(h, ''), cols[1])
                            if src:
                                tally[src] = tally.get(src, 0) + 1
                    sources[tool] = dict(sorted(tally.items(), key=lambda kv: -kv[1]))
                if header is None and not any(stored.values()):
                    continue
                with open(out / 'cached' / filename, 'w') as fh:
                    if header:
                        fh.write(header + '\n')
                    for fid, h, _, _ in proteins:
                        for line in (stored.get(h) or '').splitlines():
                            fh.write(_remap(line, kind, cols, fid, genome) + '\n')
            (out / 'plan.json').write_text(json.dumps({
                'tool': tool, 'tool_key': key, 'cached': sum(1 for p in proteins if p[1] in cached),
                'novel': sum(1 for p in proteins if p[1] not in cached),
                **({'sources': sources[tool]} if sources is not None and tool in sources else {})}) + '\n')
            now[tool] = (sum(1 for p in proteins if p[1] in cached), sum(1 for p in proteins if p[1] not in cached))
    finally:
        conn.close()
    return now


# ---- after a tool's results are in ----

# Columns that name the run rather than the answer: the gene, the genome, the run's files and
# the tool, command, database and model it recorded.
_PROVENANCE = re.compile(r'^(feature_id|organism_name|input_path|output_path)$|_(tool|command|database|model)_used$', re.I)


def _answer(header: str | None, lines: list[str], kind: str) -> list:
    """A protein's rows as their results only, in a fixed order: what two runs are compared by."""
    if kind == 'domtbl':
        return sorted(_DOMTBL_ID.sub(lambda m: m.group(1) + '-', line, count=1) for line in lines)
    cols = (header or '').split('\t')
    keep = [i for i, c in enumerate(cols) if not _PROVENANCE.search(c)]
    return sorted(tuple((cols[i], parts[i] if i < len(parts) else '') for i in keep)
                  for parts in (line.split('\t') for line in lines))


def _computed_here(prefix: str, tool: str, proteins: list) -> set[str]:
    """Hashes of the proteins this genome's run of the tool computed: those in its novel.faa when
    the protein cache split the run, else every protein."""
    novel = Path(pc_dir(prefix, tool)) / 'novel.faa'
    if not novel.is_file():
        return {h for _, h, _, _ in proteins}
    ids = {fid for fid, _, _ in read_fasta(str(novel))}
    return {h for fid, h, _, _ in proteins if fid in ids}


def _by_name(lines: str, old: list[str], new: list[str]) -> str:
    """Rows written under the columns `old`, rewritten under `new` by column name (a column `new`
    adds is empty)."""
    at = {c: i for i, c in enumerate(old)}
    out = []
    for line in lines.splitlines():
        parts = line.split('\t')
        out.append('\t'.join(parts[at[c]] if c in at and at[c] < len(parts) else '' for c in new))
    return '\n'.join(out)


def _reheader(conn, tool: str, key: str, filename: str, old: str, new: str) -> int:
    """Rewrites a tool file's cached rows from the header `old` to `new` by column name; returns the count."""
    old_cols, new_cols = old.split('\t'), new.split('\t')
    rows = conn.execute('SELECT aa_hash, lines FROM protein_cache WHERE tool = ? AND tool_key = ? AND filename = ?',
                        (tool, key, filename)).fetchall()
    conn.executemany('UPDATE protein_cache SET lines = ? WHERE tool = ? AND tool_key = ? AND filename = ? AND aa_hash = ?',
                     [(_by_name(lines, old_cols, new_cols), tool, key, filename, h) for h, lines in rows])
    return len(rows)


def store(db: str, faa: str, prefix: str, tool: str, cfg: dict, genome: str = '', ran: bool = True) -> int:
    """Adds the genome's uncached proteins from the tool's final results, each with the genome it
    came from; returns the count. A tool restored from the MARGIE database (`ran` False) adds none:
    its results came from an earlier run, and adding a genome's proteins one by one to the cache
    takes minutes per tool on a large database. Only the writes take the database's write turn (db_turn)."""
    if not ran:
        return 0
    key = tool_key(tool, cfg)
    files = tool_files(tool, cfg)
    folder = Path(f'{prefix}{tool}')
    if not (folder / files[0][0]).exists():
        return 0
    proteins = _proteins(faa)
    first: dict[str, str] = {}
    for fid, h, _, _ in proteins:
        first.setdefault(h, fid)
    conn = _connect(db)
    try:
        _carry_over(conn, tool, cfg, key)
        cached = _cached_hashes(conn, tool, key, files[0][0], sorted(first))
        new = sorted(set(first) - cached)
        again = sorted(cached & _computed_here(prefix, tool, proteins))
        if not new and not again:
            return 0
        tables = {}
        for filename, kind in files:
            header, rows = _read_rows(folder / filename, kind)
            if header is None and kind == 'tsv':
                LOGGER.warning('protein cache: %s has no header; not caching %s', folder / filename, tool)
                return 0
            tables[filename] = (header, rows)
        # Skips caching when the results' ids are not this genome's proteins.
        ids = {fid for fid, _, _, _ in proteins}
        rows = tables[files[0][0]][1]
        strangers = sum(1 for fid in rows if fid not in ids)
        if rows and strangers > 0.01 * len(rows):
            LOGGER.warning('protein cache: %d of %d feature ids in %s are not proteins of %s; not caching %s',
                           strangers, len(rows), folder / files[0][0], faa, tool)
            return 0
        # Computed again: replaced where any result column differs from the cached one.
        changed: list[str] = []
        for chunk in _chunks(again):
            held: dict[tuple[str, str], str] = {}
            for h, filename, lines in conn.execute(
                    'SELECT aa_hash, filename, lines FROM protein_cache WHERE tool = ? AND tool_key = ? '
                    f'AND aa_hash IN ({",".join("?" * len(chunk))})', (tool, key, *chunk)):
                held[(h, filename)] = lines
            heads = {f: (r[0] if (r := conn.execute('SELECT header FROM protein_cache_header WHERE tool = ? AND tool_key = ? '
                                                     'AND filename = ?', (tool, key, f)).fetchone()) else None) for f, _ in files}
            for h in chunk:
                if any(_answer(heads[f], (held.get((h, f)) or '').splitlines(), kind)
                       != _answer(tables[f][0], tables[f][1].get(first[h], []), kind) for f, kind in files):
                    changed.append(h)
        stamp = datetime.now(timezone.utc).isoformat()
        with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
            for filename, (header, _) in tables.items():
                if not header:
                    continue
                # A tool whose columns changed (a new container): the cached rows move to the new
                # header by column name, and the header is replaced.
                row = conn.execute('SELECT header FROM protein_cache_header WHERE tool = ? AND tool_key = ? AND filename = ?',
                                   (tool, key, filename)).fetchone()
                if row and row[0] != header:
                    moved = _reheader(conn, tool, key, filename, row[0], header)
                    LOGGER.info('protein cache: %s %s has new columns; %d cached entries moved to them', tool, filename, moved)
                conn.execute('INSERT OR REPLACE INTO protein_cache_header VALUES (?, ?, ?, ?)',
                             (tool, key, filename, header))
        # The rows go in short transactions, each in the write turn, so loads and the run's other
        # writes go between them; a store cut short keeps the chunks it wrote.
        for chunk in _chunks(new, STORE_CHUNK):
            with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
                for filename, (_, rows) in tables.items():
                    conn.executemany('INSERT OR IGNORE INTO protein_cache (aa_hash, tool, tool_key, filename, lines, cached_at, genome) '
                                     'VALUES (?, ?, ?, ?, ?, ?, ?)',
                                     [(h, tool, key, filename, '\n'.join(rows.get(first[h], [])), stamp, genome) for h in chunk])
            time.sleep(STORE_PAUSE)
        for chunk in _chunks(changed, STORE_CHUNK):
            with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
                for filename, (_, rows) in tables.items():
                    conn.executemany('UPDATE protein_cache SET lines = ?, cached_at = ?, genome = ? '
                                     'WHERE tool = ? AND tool_key = ? AND filename = ? AND aa_hash = ?',
                                     [('\n'.join(rows.get(first[h], [])), stamp, genome, tool, key, filename, h) for h in chunk])
            time.sleep(STORE_PAUSE)
        if changed:
            LOGGER.info('protein cache: %d %s entries replaced, their results differing from the cached ones', len(changed), tool)
        return len(new) + len(changed)
    finally:
        conn.close()


# ---- inside the rule: merging tool rows with cached rows ----

# POSIX sh, run inside the tool's container: merge.sh PRODUCED DEST PC_DIR FILENAME KIND
MERGE_SH = r'''#!/bin/sh
# Written by protein_cache.py. The tool's own rows (it ran on the proteins
# not in the cache), then the cached proteins' rows.
produced="$1"; dest="$2"; cached="$3/cached/$4"; kind="$5"
if [ -s "$produced" ]; then
  [ "$produced" = "$dest" ] || cp "$produced" "$dest" || exit 1
  if [ -s "$cached" ]; then
    if [ "$kind" = domtbl ]; then grep -v '^#' "$cached" >> "$dest" || true
    elif [ "$(head -n 1 "$dest")" = "$(head -n 1 "$cached")" ]; then tail -n +2 "$cached" >> "$dest" || exit 1
    else
      # The tool's columns changed since the rows were cached: each cached row is laid out under
      # the new header by column name (a new column is empty).
      command -v awk >/dev/null || { echo "protein cache: cached rows of $4 have other columns and awk is missing" >&2; exit 1; }
      head -n 1 "$dest" > "$dest.header" || exit 1
      awk -F '\t' -v OFS='\t' 'NR == FNR { for (i = 1; i <= NF; i++) want[i] = $i; n = NF; next }
        FNR == 1 { for (i = 1; i <= NF; i++) at[$i] = i; next }
        { row = ""; for (i = 1; i <= n; i++) { v = (want[i] in at) ? $(at[want[i]]) : ""; row = (i == 1) ? v : row OFS v }; print row }' \
        "$dest.header" "$cached" >> "$dest" || exit 1
      rm -f "$dest.header"
    fi
  fi
elif [ -s "$cached" ]; then
  cp "$cached" "$dest" || exit 1
elif [ -e "$produced" ] || [ "$kind" = "tsv?" ]; then
  : > "$dest"
elif [ -e "$3/novel.faa" ] && [ ! -s "$3/novel.faa" ]; then
  : > "$dest"   # every protein was cached, and none has a row here
else
  echo "protein cache: $produced was not written" >&2; exit 1
fi
'''


def install_merge_script(folder: str) -> str:
    """Writes MERGE_SH into the run's output folder, where every container can read it."""
    path = Path(folder) / '.protein-cache' / 'merge.sh'
    try:
        if not path.exists() or path.read_text() != MERGE_SH:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp')
            tmp.write_text(MERGE_SH)
            tmp.replace(path)
    except OSError as exc:
        LOGGER.warning('protein cache: could not write %s: %s', path, exc)
    return str(path)


# ---- which genome each protein and gene belongs to ----

def link_genome(db: str, faa: str, genome_hash: str, name: str = '', genes: dict[str, str] | None = None) -> int:
    """Records the genome's proteins by hash (protein_genomes), its protein set (a hash of its sorted
    protein hashes, in genome_proteomes) and, with `genes` ({feature id: gene hash}), its genes
    (genome_genes); returns the number of distinct proteins. What is linked already is read first,
    outside the database's write turn, and only what is new or different is written, so a genome
    linked before (a resumed or repeated run) writes nothing; last_linked is when its links last
    changed."""
    proteins = _proteins(faa)
    hashes = sorted({h for _, h, _, _ in proteins})
    if not genome_hash or not hashes:
        return 0
    protein_set = hashlib.sha256('\n'.join(hashes).encode()).hexdigest()
    stamp = datetime.now(timezone.utc).isoformat()
    conn = _connect(db)
    try:
        linked = {r[0] for r in conn.execute('SELECT aa_hash FROM protein_genomes WHERE genome_hash = ?', (genome_hash,))}
        new_proteins = [(h, genome_hash) for h in hashes if h not in linked]
        row = conn.execute('SELECT proteins, protein_set, names FROM genome_proteomes WHERE genome_hash = ?', (genome_hash,)).fetchone()
        names = json.loads(row[2]) if row else []
        if name and name not in names:
            names.append(name)
        proteome = (len(hashes), protein_set, json.dumps(names))
        new_genes: list[tuple[str, str, str]] = []
        if genes:
            by_fid = {fid: h for fid, h, _, _ in proteins}
            held = dict(conn.execute('SELECT gene_hash, aa_hash FROM genome_genes WHERE genome_hash = ?', (genome_hash,)))
            new_genes = [(genome_hash, g, by_fid.get(fid, '')) for fid, g in genes.items() if held.get(g) != by_fid.get(fid, '')]
        if not new_proteins and not new_genes and row and tuple(row) == proteome:
            return len(hashes)
        with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
            conn.executemany('INSERT OR IGNORE INTO protein_genomes (aa_hash, genome_hash) VALUES (?, ?)', new_proteins)
            if row:
                conn.execute('UPDATE genome_proteomes SET proteins = ?, protein_set = ?, names = ?, last_linked = ? WHERE genome_hash = ?',
                             (*proteome, stamp, genome_hash))
            else:
                conn.execute('INSERT INTO genome_proteomes VALUES (?, ?, ?, ?, ?, ?)', (genome_hash, *proteome, stamp, stamp))
            conn.executemany('INSERT INTO genome_genes (genome_hash, gene_hash, aa_hash) VALUES (?, ?, ?) '
                             'ON CONFLICT (genome_hash, gene_hash) DO UPDATE SET aa_hash = excluded.aa_hash', new_genes)
    finally:
        conn.close()
    return len(hashes)


def record_fingerprints(db: str, genome_hash: str, hash_label_tsv: str, genes: dict[str, str]) -> int:
    """Adds each gene's fingerprint (its pattern hash, from the fingerprint step's hash-label table)
    to genome_genes, and each protein's, with its label, to protein_fingerprints; returns how many
    genes got one. As link_genome, it reads first and writes only what differs."""
    path = Path(hash_label_tsv)
    if not genome_hash or not genes or not path.is_file():
        return 0
    found: list[tuple[str, str, str]] = []
    labels: dict[str, str] = {}
    with open(path, newline='', encoding='utf-8', errors='replace') as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            text = row.get('fingerprint') or ''
            m = re.search(r'pattern hash:\s*([0-9a-f]+)', text)
            gene = genes.get(row.get('feature_id') or '')
            if m and gene:
                found.append((m.group(1), genome_hash, gene))
                label = re.search(r'label:\s*(.*?)\s*(?:\|\||$)', text)
                labels[m.group(1)] = label.group(1) if label else ''
    if not found:
        return 0
    stamp = datetime.now(timezone.utc).isoformat()
    conn = _connect(db)
    try:
        held = {g: [aa, fp] for g, aa, fp in conn.execute(
            'SELECT gene_hash, aa_hash, fingerprint FROM genome_genes WHERE genome_hash = ?', (genome_hash,))}
        genes_set = []
        for fp, _, gene in found:
            if gene in held and held[gene][1] != fp:
                genes_set.append((fp, genome_hash, gene))
                held[gene][1] = fp
        # A protein's fingerprint: kept while a later genome gives the same, replaced when it differs.
        pairs = sorted({(aa, fp) for aa, fp in held.values() if aa and fp})
        kept: dict[str, str] = {}
        for chunk in _chunks(sorted({aa for aa, _ in pairs}), READ_CHUNK):
            kept.update(conn.execute(f'SELECT aa_hash, fingerprint FROM protein_fingerprints WHERE aa_hash IN ({",".join("?" * len(chunk))})', chunk))
        prints = []
        for aa, fp in pairs:
            if kept.get(aa) != fp:
                prints.append((aa, fp, labels.get(fp, ''), stamp))
                kept[aa] = fp
        if genes_set or prints:
            with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
                conn.executemany('UPDATE genome_genes SET fingerprint = ? WHERE genome_hash = ? AND gene_hash = ?', genes_set)
                conn.executemany('INSERT INTO protein_fingerprints (aa_hash, fingerprint, label, recorded_at) VALUES (?, ?, ?, ?) '
                                 'ON CONFLICT (aa_hash) DO UPDATE SET fingerprint = excluded.fingerprint, label = excluded.label, '
                                 'recorded_at = excluded.recorded_at WHERE protein_fingerprints.fingerprint != excluded.fingerprint',
                                 prints)
    finally:
        conn.close()
    return len(found)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _rows_by_feature(path: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if path.is_file():
        with open(path, newline='', encoding='utf-8', errors='replace') as fh:
            for row in csv.DictReader(fh, delimiter='\t'):
                out.setdefault(row.get('feature_id') or '', []).append(row)
    return out


def _localization(prefix: str) -> dict[str, dict[str, str]]:
    """{feature id: {tool: value}} from the localization tools' results in the genome's folder;
    PSORTb's and DeepSig's say the Gram or organism class they were run for."""
    out: dict[str, dict[str, str]] = {}
    put = lambda fid, slot, value: value and out.setdefault(fid, {}).__setitem__(slot, value)  # noqa: E731
    for fid, rows in _rows_by_feature(Path(f'{prefix}signalp6/signalp6_results.tsv')).items():
        r = rows[0]
        # process_signalp6.py writes lower-case signalp6_ columns.
        site = (r.get('signalp6_cs_position') or r.get('SIGNALP6_cleavage_site') or '').strip()
        call = (r.get('signalp6_prediction') or r.get('SIGNALP6_prediction') or '').strip()
        put(fid, 'SIGNALP6', call + (f'; cleavage {site}' if call and site else ''))
    for fid, rows in _rows_by_feature(Path(f'{prefix}phobius/phobius_results.tsv')).items():
        tm = sum(1 for r in rows if 'TRANSMEM' in (r.get('phobius_segment_type') or '').upper())
        sp = (rows[0].get('phobius_has_signal_peptide') or '').strip().lower() in ('true', 'yes', '1', 'y')
        put(fid, 'PHOBIUS', f'{tm} TM segment{"" if tm == 1 else "s"}; signal peptide: {"yes" if sp else "no"}')
    for fid, rows in _rows_by_feature(Path(f'{prefix}tmbed/tmbed_results.tsv')).items():
        # The whole protein's topology string, rather than its first segment's.
        put(fid, 'TMBED', (rows[0].get('TMBED_topology_string') or rows[0].get('TMBED_topology') or '').strip())
    for fid, rows in _rows_by_feature(Path(f'{prefix}psortb/psortb_results.tsv')).items():
        r = rows[0]
        envelope = (r.get('PSORTB_gram_class') or r.get('ENVELOPE_envelope_type') or '').strip()
        where = (r.get('PSORTB_localization') or '').strip()
        put(fid, 'PSORTB', f'{where} ({envelope})' if where and envelope else where)
    for fid, rows in _rows_by_feature(Path(f'{prefix}deepsig/deepsig_results.tsv')).items():
        kind = (rows[0].get('DEEPSIG_organism_class') or '').strip()
        found = ', '.join(dict.fromkeys(t for r in rows if (t := (r.get('DEEPSIG_feature_type') or '').strip())))
        put(fid, 'DEEPSIG', f'{found} ({kind})' if found and kind else found)
    return out


def _position(tool: str) -> int:
    """Where a tool sits in the record: core tools first, then the additional tools in their order,
    then any other tool."""
    base = tool.split(' (')[0]
    if base in CORE_TOOLS:
        return CORE_TOOLS.index(base)
    return 100 + (EXTRA_TOOLS.index(base) if base in EXTRA_TOOLS else len(EXTRA_TOOLS))


def _prints(have: dict[str, str]) -> tuple[str, str]:
    """A protein's core and additional fingerprints from its descriptors ({tool: value})."""
    core = _sha256(' | '.join(f'{t}: {have.get(t, "")}' for t in CORE_TOOLS))
    extra_tools = sorted((t for t in have if _position(t) >= 100), key=lambda t: (_position(t), t))
    extra = _sha256(' | '.join(f'{t}: {have[t]}' for t in extra_tools)) if extra_tools else ''
    return core, extra


def record_proteins(db: str, labeled_tsv: str, prefix: str, genome_hash: str = '') -> int:
    """Adds each protein's descriptors to its record (protein_descriptors, read through
    protein_records): each tool's ids and descriptions from the labeled genes, and the localization
    tools' answers. A tool the record lacks is added, the same answer stays, a different one replaces
    it; the core and additional fingerprints follow. PSORTb's and DeepSig's answers go under the
    genome hash and protein hash (genome_protein_descriptors). Returns the number of proteins.

    The records are read first, outside the database's write turn; the turn is taken only for the
    proteins with something new or different, whose fingerprints are then made from their records as
    they stand in it (another genome can share a protein). A genome recorded before writes nothing."""
    path = Path(labeled_tsv)
    if not path.is_file():
        return 0
    local = _localization(prefix)
    found: dict[tuple[str, str], str] = {}
    per_genome: dict[tuple[str, str], str] = {}
    with open(path, newline='', encoding='utf-8', errors='replace') as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            seq = (row.get('aa_seq') or '').strip()
            if not seq:
                continue
            h = protein_hash(seq)
            for tool in CORE_TOOLS + EXTRA_TOOLS:
                ids = (row.get(f'{tool}_all_ids') or '').strip()
                desc = (row.get(f'{tool}_all_descriptions') or '').strip()
                if ids:
                    found[(h, tool)] = f'{ids} — {desc}' if desc else ids
            for tool, value in local.get(row.get('feature_id') or '', {}).items():
                (per_genome if tool in GENOME_TOOLS else found)[(h, tool)] = value
    if not found and not per_genome:
        return 0
    proteins = sorted({h for h, _ in found})
    ours: dict[str, dict[str, str]] = {}
    for (h, tool), value in found.items():
        ours.setdefault(h, {})[tool] = value
    stamp = datetime.now(timezone.utc).isoformat()
    in_ = lambda chunk: ",".join("?" * len(chunk))  # noqa: E731
    conn = _connect(db)
    try:
        genome_rows = []
        if genome_hash and per_genome:
            kept = {(h, tool): value for h, tool, value in conn.execute(
                'SELECT aa_hash, tool, value FROM genome_protein_descriptors WHERE genome_hash = ?', (genome_hash,))}
            genome_rows = [(genome_hash, h, tool, value, stamp) for (h, tool), value in per_genome.items() if kept.get((h, tool)) != value]
        held: dict[str, dict[str, str]] = {}
        prints_held: dict[str, tuple[str, str]] = {}
        for chunk in _chunks(proteins, READ_CHUNK):
            for h, tool, value in conn.execute(f'SELECT aa_hash, tool, value FROM protein_descriptors WHERE aa_hash IN ({in_(chunk)})', chunk):
                held.setdefault(h, {})[tool] = value
            for h, core, extra in conn.execute(
                    f'SELECT aa_hash, core_fingerprint, extra_fingerprint FROM protein_fingerprints WHERE aa_hash IN ({in_(chunk)})', chunk):
                prints_held[h] = (core, extra)
        # A protein is touched when one of its descriptors is new or different, or its fingerprints
        # are not those of its record with ours in it.
        touched = [h for h in proteins
                   if any(held.get(h, {}).get(t) != v for t, v in ours[h].items())
                   or prints_held.get(h) != _prints({**held.get(h, {}), **ours[h]})]
        if genome_rows:
            with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
                conn.executemany('INSERT INTO genome_protein_descriptors (genome_hash, aa_hash, tool, value, recorded_at) '
                                 'VALUES (?, ?, ?, ?, ?) ON CONFLICT (genome_hash, aa_hash, tool) DO UPDATE SET '
                                 'value = excluded.value, recorded_at = excluded.recorded_at '
                                 'WHERE genome_protein_descriptors.value != excluded.value', genome_rows)
        for chunk in _chunks(touched, STORE_CHUNK):
            with db_turn.turn(db, wait=db_turn.CONTROLLER_WAIT), conn:
                conn.executemany('INSERT INTO protein_descriptors (aa_hash, tool, position, value, recorded_at) VALUES (?, ?, ?, ?, ?) '
                                 'ON CONFLICT (aa_hash, tool) DO UPDATE SET value = excluded.value, recorded_at = excluded.recorded_at '
                                 'WHERE protein_descriptors.value != excluded.value',
                                 [(h, tool, _position(tool), value, stamp) for h in chunk for tool, value in ours[h].items()])
                now: dict[str, dict[str, str]] = {}
                for h, tool, value in conn.execute(f'SELECT aa_hash, tool, value FROM protein_descriptors WHERE aa_hash IN ({in_(chunk)})', chunk):
                    now.setdefault(h, {})[tool] = value
                conn.executemany("INSERT INTO protein_fingerprints (aa_hash, fingerprint, label, recorded_at, core_fingerprint, extra_fingerprint) "
                                 "VALUES (?, '', '', ?, ?, ?) ON CONFLICT (aa_hash) DO UPDATE SET "
                                 "core_fingerprint = excluded.core_fingerprint, extra_fingerprint = excluded.extra_fingerprint",
                                 [(h, stamp, *_prints(now.get(h, {}))) for h in chunk])
            time.sleep(STORE_PAUSE)
    finally:
        conn.close()
    return len(proteins)
