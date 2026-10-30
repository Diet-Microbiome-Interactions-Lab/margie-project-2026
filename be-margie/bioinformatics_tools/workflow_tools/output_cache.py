"""
DB-based output cache for MARGIE workflow.

Stores compute rule output files (RASTtk's gene calls, pfam, cog) as BLOBs in an
``output_cache`` table inside the same SQLite database used for annotations.
This lets Snakemake skip expensive re-computation when the same input FASTA
has already been processed, even across fresh timestamped working directories.

Copy the ``.db`` file to another server and it carries the cached outputs
with it — no separate cache directory needed.

A genome's key is its sequence hash (genome_identity.genome_hash), so formatting
differences still hit; older entries keyed by a 16-hex-char file byte hash are
still found (_input_hashes).
"""
import hashlib
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from urllib.parse import unquote

try:
    from bioinformatics_tools.workflow_tools import db_turn
    from bioinformatics_tools.workflow_tools.genome_identity import genome_hash, legacy_file_hash, normalise_protein, read_fasta
    from bioinformatics_tools.workflow_tools.load_to_db import _ensure_run_log as ensure_run_log
except ImportError:  # imported from margie_sb.smk, with this folder on sys.path
    import db_turn
    from genome_identity import genome_hash, legacy_file_hash, normalise_protein, read_fasta
    from load_to_db import _ensure_run_log as ensure_run_log

LOGGER = logging.getLogger(__name__)

CREATE_OUTPUT_CACHE_SQL = """
CREATE TABLE IF NOT EXISTS output_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    filename TEXT NOT NULL,
    content BLOB NOT NULL,
    size_bytes INTEGER NOT NULL,
    cached_at TEXT NOT NULL,
    UNIQUE(input_hash, tool, filename)
);
"""

# When each genome's outputs for a tool were cached, apart from the files: cached_at sits after the
# file's content in output_cache, so reading it there walks the whole stored file. For the cache report.
CREATE_OUTPUT_CACHE_WHEN_SQL = """
CREATE TABLE IF NOT EXISTS output_cache_when (
    input_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    cached_at TEXT NOT NULL,
    PRIMARY KEY (input_hash, tool)
);
"""

# Each cached file's SHA-256, so a store of the same file again writes nothing (store()).
CREATE_OUTPUT_CACHE_DIGESTS_SQL = """
CREATE TABLE IF NOT EXISTS output_cache_digests (
    input_hash TEXT NOT NULL,
    tool TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (input_hash, tool, filename)
) WITHOUT ROWID;
"""

# SQLite's page cache per connection, KiB (256 MiB; the default is 2 MB).
CACHE_KIB = 262144


def _get_connection(db_path: str, timeout: float = 120.0) -> sqlite3.Connection:
    """Create a SQLite connection configured for network filesystems.

    Args:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds (default 120 s, as the database loads wait)

    Returns:
        Configured sqlite3.Connection with increased timeout and busy handler
    """
    conn = sqlite3.connect(db_path, timeout=timeout)

    # Busy timeout (milliseconds): waits as long as `timeout` for the lock
    # This is critical for NFS where lock operations are slow
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    # The index pages a call's lookups share stay in memory.
    conn.execute(f"PRAGMA cache_size=-{CACHE_KIB}")

    return conn


def _retry_operation(func, max_retries: int = 3, initial_delay: float = 0.5):
    """Retry operations that fail with transient disk I/O or lock errors.

    Args:
        func: Callable to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (doubles each time)

    Returns:
        Result of func() if successful

    Raises:
        sqlite3.OperationalError: If all retries fail
    """
    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            last_error = e
            error_str = str(e).lower()

            # Retry on transient errors
            if any(err in error_str for err in ["disk i/o error", "database is locked", "unable to open"]):
                if attempt < max_retries - 1:
                    LOGGER.warning(
                        "Database operation failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, max_retries, e, delay
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    LOGGER.error("Database operation failed after %d attempts: %s", max_retries, e)
            else:
                # Not a transient error, re-raise immediately
                raise

    raise last_error


def _compute_file_hash(file_path: str) -> str:
    """Returns the first 16 hex chars of the SHA-256 of *file_path* (the key before genome_hash)."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def _input_hashes(input_file: str) -> tuple[str, str]:
    """Returns (key new entries are written under, older key still looked up)."""
    return genome_hash(input_file), legacy_file_hash(input_file)[:16]


def _ensure_table(conn: sqlite3.Connection) -> None:
    # A read first: CREATE ... IF NOT EXISTS takes the write lock even when the table is there,
    # and on a busy database that wait is what failed.
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('output_cache', 'output_cache_when', 'output_cache_digests')")}
    if 'output_cache' not in have:
        conn.execute(CREATE_OUTPUT_CACHE_SQL)
    if 'output_cache_when' not in have:
        conn.execute(CREATE_OUTPUT_CACHE_WHEN_SQL)
    if 'output_cache_digests' not in have:
        conn.execute(CREATE_OUTPUT_CACHE_DIGESTS_SQL)


def _digests(conn: sqlite3.Connection, input_hash: str, tool: str) -> dict[str, tuple[str, int]]:
    """The cached files of a genome and tool with a digest, {filename: (sha256, bytes)}. A blob's
    length comes from its row's header, without reading the blob."""
    try:
        sums = dict(conn.execute("SELECT filename, sha256 FROM output_cache_digests WHERE input_hash = ? AND tool = ?",
                                 (input_hash, tool)))
    except sqlite3.OperationalError:  # no digests yet
        return {}
    if not sums:
        return {}
    sizes = dict(conn.execute("SELECT filename, length(content) FROM output_cache WHERE input_hash = ? AND tool = ?",
                              (input_hash, tool)))
    return {f: (s, sizes[f]) for f, s in sums.items() if f in sizes}


# ───────────────────────── single-tool helpers ───────────────────────── #

def _extract_pattern_suffix(filename: str) -> str:
    """Extract the pattern suffix for matching across different stems.

    Files follow two patterns:
    1. With stem: "{stem}-{rest}" → pattern = "-{rest}"
    2. Without stem: "{filename}" → pattern = "{filename}"

    Examples:
        'genome-a-prodigal.gff' → '-prodigal.gff'
        'genome-b-prodigal_db.tkn' → '-prodigal_db.tkn'
        'pfam.tsv' → 'pfam.tsv'
        'cog_classify.tsv' → 'cog_classify.tsv'
    """
    # If filename contains a dash, assume it's {stem}-{rest}
    # Pattern is everything from first dash onwards
    if '-' in filename:
        return '-' + filename.split('-', 1)[1]
    # Otherwise, it's a fixed filename without stem
    return filename


def restore(db_path: str, input_file: str, tool_name: str,
            output_paths: list[str], optional: list[str] = (), genes: dict[str, str] | None = None) -> bool:
    """Restore cached outputs for *tool_name* from the DB using pattern matching.

    Matches files by pattern suffix rather than exact filename, allowing cache hits
    across different input filenames with identical content.

    Examples:
        Cached: genome-a-prodigal.gff (pattern: -prodigal.gff)
        Expected: genome-b-prodigal.gff (pattern: -prodigal.gff) → MATCH!

        Cached: pfam.tsv (pattern: pfam.tsv)
        Expected: pfam.tsv (pattern: pfam.tsv) → MATCH!

    Returns True if **all** expected files were found in the cache and
    written to disk, False on any miss. Files in *optional* are written too when
    they are cached, and a miss on them is not a miss.
    """
    if not Path(db_path).exists():
        return False

    current, legacy = _input_hashes(input_file)

    conn = _get_connection(db_path)
    try:
        _ensure_table(conn)
        # Prefers the sequence-hash entry; falls back to the older byte-hash one.
        rows = []
        for input_hash in (current, legacy):
            rows = conn.execute(
                "SELECT filename, content FROM output_cache "
                "WHERE input_hash = ? AND tool = ?",
                (input_hash, tool_name),
            ).fetchall()
            if rows:
                break
    finally:
        conn.close()

    if not rows:
        LOGGER.info("Cache miss for %s: no cached files found for this input", tool_name)
        return False

    # Build pattern -> blob mapping from cached files
    cached_patterns = {}
    for fname, blob in rows:
        pattern = _extract_pattern_suffix(fname)
        cached_patterns[pattern] = blob

    # Match expected files by pattern
    matched = {}
    for path in output_paths:
        expected_fname = Path(path).name
        expected_pattern = _extract_pattern_suffix(expected_fname)

        if expected_pattern in cached_patterns:
            matched[path] = cached_patterns[expected_pattern]
        else:
            LOGGER.info("Cache miss for %s: no match for pattern '%s' (file: %s)",
                       tool_name, expected_pattern, expected_fname)
            LOGGER.debug("Available patterns: %s", list(cached_patterns.keys()))
            return False
    for path in optional:
        pattern = _extract_pattern_suffix(Path(path).name)
        if pattern in cached_patterns:
            matched[path] = cached_patterns[pattern]

    # Tables stored with genes by hash come back under this run's gene ids, when each gene is here.
    ids_by_hash = {h: fid for fid, h in (genes or {}).items()}
    for path, blob in list(matched.items()):
        back = _from_gene_hashes(blob, ids_by_hash)
        if back is None:
            LOGGER.info("Cache miss for %s: its genes are not this run's gene calls", tool_name)
            return False
        matched[path] = back

    # Write all matched BLOBs to expected paths
    for path, blob in matched.items():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(blob)
        LOGGER.info("Restored from cache: %s", path)

    return True


# ---- Genes by hash: cached tables name a gene by what it is, not by its number ----

# RASTtk's gene ids, and the token a cached table names a gene by instead.
_GENE_ID_RE = re.compile(rb"fig\|6666666\.\d+\.(?:peg|rna)\.\d+")
_GENE_TOKEN = b"margie-gene:"
# Gene hashes are 64 hexadecimal digits; tables cached with the older 24-digit form match no gene
# of a run, so they are computed again.
_GENE_TOKEN_RE = re.compile(rb"margie-gene:([0-9a-f]{64}|[0-9a-f]{24})")


def gene_hashes(gff: str, faa: str) -> dict[str, str]:
    """{gene id: gene hash} for a genome's RASTtk gene calls. A gene's hash is of its contig, start,
    end, strand and protein (an RNA's feature type), so a gene keeps it whatever number a gene
    caller gives it. {} when the files are missing or two genes share a hash."""
    try:
        proteins = {fid: normalise_protein(seq) for fid, _, seq in read_fasta(faa) if fid}
        lines = Path(gff).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    out: dict[str, str] = {}
    for line in lines:
        cols = line.split("\t")
        if line.startswith("#") or len(cols) < 9:
            continue
        m = re.search(r"(?:^|;)ID=([^;]+)", cols[8])
        if not m:
            continue
        fid = unquote(m.group(1))
        what = proteins.get(fid) or cols[2]
        out[fid] = hashlib.sha256(f"{cols[0]}\t{cols[3]}\t{cols[4]}\t{cols[6]}\t{what}".encode()).hexdigest()
    return out if len(set(out.values())) == len(out) else {}


def _to_gene_hashes(blob: bytes, genes: dict[str, str]) -> bytes:
    """The table with each gene id written as its gene hash; unchanged when a gene id in it is not
    among `genes`, or when a RASTtk id remains in another form."""
    found = {m.decode() for m in _GENE_ID_RE.findall(blob)}
    if not found or any(fid not in genes for fid in found):
        return blob
    out = _GENE_ID_RE.sub(lambda m: _GENE_TOKEN + genes[m.group(0).decode()].encode(), blob)
    return blob if _RAST_GENOME_ID_RE.search(out) else out


def _from_gene_hashes(blob: bytes, ids_by_hash: dict[str, str]) -> bytes | None:
    """The table with each gene hash written as this run's gene id; None when a gene in it is not
    among this run's gene calls. A table stored with gene ids comes back as it is."""
    if _GENE_TOKEN not in blob:
        return blob
    if any(h.decode() not in ids_by_hash for h in set(_GENE_TOKEN_RE.findall(blob))):
        return None
    return _GENE_TOKEN_RE.sub(lambda m: ids_by_hash[m.group(1).decode()].encode(), blob)


# ---- RASTtk genome-id realignment ----

# RASTtk ids features by submission (6666666.<job>), so resubmits get new namespaces.
_RAST_GENOME_ID_RE = re.compile(rb"6666666\.(\d+)")


def current_rast_genome_id(rasttk_file: str) -> str | None:
    """Returns the ``6666666.<job>`` id this run's RASTtk produced.

    Read from rast.gff / rast.tsv; None (file missing or no id) means leave everything alone.
    """
    try:
        blob = Path(rasttk_file).read_bytes()
    except OSError:
        return None
    ids = {m.group(1) for m in _RAST_GENOME_ID_RE.finditer(blob)}
    if len(ids) != 1:
        if ids:
            LOGGER.warning("rasttk output %s carries %d genome ids (%s) — cannot pin one",
                           rasttk_file, len(ids), sorted(i.decode() for i in ids))
        return None
    return ids.pop().decode()


def rast_genome_ids(paths: list[str]) -> set[str]:
    """The RASTtk genome ids (6666666.<job>) the files name."""
    ids: set[str] = set()
    for path in paths:
        try:
            ids |= {m.group(1).decode() for m in _RAST_GENOME_ID_RE.finditer(Path(path).read_bytes())}
        except OSError:
            continue
    return ids


def _proteins_by_number(faa: bytes) -> dict[str, str]:
    """{feature number ('peg.12'): protein} from a RASTtk .faa."""
    out: dict[str, str] = {}
    name, seq = None, []
    for line in faa.decode(errors="replace").splitlines():
        if line.startswith(">"):
            if name:
                out[name] = "".join(seq)
            m = re.match(r">\S*?6666666\.\d+\.(\S+)", line)
            name, seq = (m.group(1) if m else None), []
        elif name:
            seq.append(line.strip())
    if name:
        out[name] = "".join(seq)
    return out


def gene_calls_match(db_path: str, input_file: str, current_faa: str, made_with: str) -> bool | None:
    """Whether the genome's cached gene calls under RASTtk job `made_with` (6666666.<job>) are this run's: the same
    protein under each feature number. Cached tables name genes by number, so they move onto this
    run's id only then. None when the cache holds no gene calls under that id to compare with."""
    try:
        current = _proteins_by_number(Path(current_faa).read_bytes())
    except OSError:
        return None
    pattern = _extract_pattern_suffix("rast.faa")
    conn = _get_connection(db_path)
    try:
        _ensure_table(conn)
        for input_hash in _input_hashes(input_file):
            for fname, blob in conn.execute(
                    "SELECT filename, content FROM output_cache WHERE input_hash = ? AND tool = 'rasttk'", (input_hash,)):
                if _extract_pattern_suffix(fname) != pattern:
                    continue
                if {m.group(1).decode() for m in _RAST_GENOME_ID_RE.finditer(blob)} != {made_with}:
                    return None
                return bool(current) and _proteins_by_number(blob) == current
    finally:
        conn.close()
    return None


def realign_rast_genome_id(paths: list[str], current_id: str) -> dict[str, str]:
    """Rewrites cache-restored files onto this run's RASTtk genome id.

    A cache hit means identical sequence, so RASTtk output differs only in the
    6666666.<job> prefix that downstream tables join on. When rasttk itself
    misses but its dependents hit, the prefix is rewritten so the joins still
    match. Files with more than one genome id are left alone with a warning.

    Returns ``{path: "<old>->      <new>"}`` for the files actually rewritten.
    """
    changed: dict[str, str] = {}
    want = current_id.encode()
    for path in paths:
        p = Path(path)
        try:
            blob = p.read_bytes()
        except OSError:
            continue
        ids = {m.group(1) for m in _RAST_GENOME_ID_RE.finditer(blob)}
        if not ids or ids == {want}:
            continue
        if len(ids) > 1:
            LOGGER.warning(
                "Not realigning %s: it carries %d RAST genome ids (%s). A cached "
                "per-genome output should carry exactly one.",
                path, len(ids), sorted(i.decode() for i in ids))
            continue
        old = ids.pop()
        try:
            p.write_bytes(blob.replace(b"6666666." + old, b"6666666." + want))
        except OSError as exc:
            LOGGER.warning("Could not realign %s: %s", path, exc)
            continue
        changed[path] = f"{old.decode()} -> {current_id}"
    return changed


def cached_tools(db_path: str, input_file: str) -> set:
    """Returns the tool names with cached outputs for *input_file* (by content hash).

    Read-only and never raises (empty set on any problem). Used by the batch
    scheduler to process the most complete genomes first."""
    try:
        if not Path(db_path).expanduser().exists():
            return set()
        current, legacy = _input_hashes(input_file)
        conn = _get_connection(str(Path(db_path).expanduser()))
        try:
            _ensure_table(conn)
            rows = conn.execute(
                "SELECT DISTINCT tool FROM output_cache WHERE input_hash IN (?, ?)",
                (current, legacy),
            ).fetchall()
        finally:
            conn.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def cached_when(db_path: str, input_file: str) -> dict[str, str]:
    """Returns {tool: when its outputs for *input_file* were cached (UTC, ISO)}, the newest per tool.

    Reads output_cache_when only, never the stored files, so it stays quick on a large database;
    outputs cached before that table existed have no date. Never raises (empty on any problem).
    For the run's cache report."""
    try:
        if not db_path or not Path(db_path).expanduser().exists():
            return {}
        current, legacy = _input_hashes(input_file)
        conn = _get_connection(str(Path(db_path).expanduser()))
        try:
            _ensure_table(conn)
            rows = conn.execute(
                "SELECT tool, MAX(cached_at) FROM output_cache_when WHERE input_hash IN (?, ?) GROUP BY tool",
                (current, legacy),
            ).fetchall()
        finally:
            conn.close()
        return {tool: when for tool, when in rows if when}
    except Exception:
        return {}


def store(db_path: str, input_file: str, tool_name: str,
          output_paths: list[str], genes: dict[str, str] | None = None) -> None:
    """Read each output file and INSERT OR REPLACE into output_cache.

    Missing files are skipped (handles partial workflow success). With `genes` ({gene id: gene
    hash}), each table names its genes by hash, so it comes back under any gene caller numbering.
    The files are read and compared with the cached ones (by SHA-256 and length) before the
    database's write turn is taken, and only those that differ are written: a genome stored again
    (a resumed or repeated run) writes nothing.
    """
    input_hash = genome_hash(input_file)
    now = datetime.now(timezone.utc).isoformat()

    # Ensure parent directory exists before creating database
    db_path_obj = Path(db_path).expanduser()
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)

    files = []
    for path in output_paths:
        p = Path(path)
        if not p.exists():
            LOGGER.debug("Skipping cache store for missing file: %s", path)
            continue
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb > 1:
            LOGGER.info("  Reading %s (%.1f MB)...", p.name, size_mb)
        blob = p.read_bytes()
        if genes:
            blob = _to_gene_hashes(blob, genes)
        files.append((p.name, blob, hashlib.sha256(blob).hexdigest()))

    conn = _get_connection(str(db_path_obj))
    try:
        held = _digests(conn, input_hash, tool_name)
        changed = [(name, blob, sha) for name, blob, sha in files if held.get(name) != (sha, len(blob))]
        if files and not changed:
            LOGGER.info("  %s: cached as it is already", tool_name)
            return
        with db_turn.turn(str(db_path_obj), wait=db_turn.CONTROLLER_WAIT):
            _ensure_table(conn)
            for name, blob, sha in changed:
                conn.execute(
                    "INSERT OR REPLACE INTO output_cache "
                    "(input_hash, tool, filename, content, size_bytes, cached_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (input_hash, tool_name, name, blob, len(blob), now),
                )
                conn.execute("INSERT OR REPLACE INTO output_cache_digests (input_hash, tool, filename, sha256) VALUES (?, ?, ?, ?)",
                             (input_hash, tool_name, name, sha))
                if len(blob) > 1024 * 1024:
                    LOGGER.info("  ✓ Stored %s", name)
            conn.execute("INSERT OR REPLACE INTO output_cache_when (input_hash, tool, cached_at) VALUES (?, ?, ?)",
                         (input_hash, tool_name, now))
            conn.commit()
    finally:
        conn.close()


# ──────────────────────── multi-tool wrappers ──────────────────────── #

def restore_all(db_path: str, input_file: str,
                build_filepaths_map: dict[str, list[str]], genes: dict[str, str] | None = None) -> dict[str, bool]:
    """Restore cached outputs for every tool in *build_filepaths_map*.

    Returns ``{tool_name: hit_bool}`` so the caller can log which tools
    were restored.

    Every restored file is stamped with one common mtime, so no restored input
    is newer than a restored output and Snakemake's mtime trigger does not rerun
    cached rules; all remain newer than the Stage-1 rasttk output.
    """
    results: dict[str, bool] = {}
    restored_paths: list[str] = []
    for tool_name, output_paths in build_filepaths_map.items():
        hit = restore(db_path, input_file, tool_name, output_paths, genes=genes)
        results[tool_name] = hit
        if hit:
            restored_paths.extend(output_paths)
            LOGGER.info("Cache HIT for %s (genome=%s) — skipping recomputation",
                        tool_name, Path(input_file).stem)
        else:
            LOGGER.info("Cache miss for %s — will compute", tool_name)

    if restored_paths:
        stamp = time.time()
        for path in restored_paths:
            try:
                os.utime(path, (stamp, stamp))
            except OSError:
                pass
    return results


def store_all(db_path: str, input_file: str,
              build_filepaths_map: dict[str, list[str]], genes: dict[str, str] | None = None) -> None:
    """Store outputs for every tool in *build_filepaths_map* into the DB, each tool's writes in a
    write turn of their own (store())."""
    total_tools = len(build_filepaths_map)
    LOGGER.info("Storing outputs to cache for %d tools...", total_tools)
    for idx, (tool_name, output_paths) in enumerate(build_filepaths_map.items(), 1):
        LOGGER.info("Caching %s (%d/%d)...", tool_name, idx, total_tools)
        store(db_path, input_file, tool_name, output_paths, genes=genes)
        LOGGER.info("✓ Cached outputs for %s", tool_name)


# run_log is load_to_db's table: one definition, one row per genome and tool.


def log_workflow_run(db_path: str, run_id: str, input_file: str, workflow_name: str,
                     rules_completed: int = 0, status: str = 'success') -> None:
    """Insert a run_log row for this workflow execution.

    The caller supplies the run_id (generated at the start of the pipeline) so
    the same UUID covers the full run, including failure cases.

    row_count is always 0 here — it is only meaningful for annotation loaders
    (load_to_db.py). rules_completed holds the number of snakemake rules that
    finished in this run.

    This function is non-fatal: any errors are logged as warnings but do not
    crash the workflow. The workflow run itself has already succeeded/failed.
    """
    try:
        if not Path(db_path).exists():
            LOGGER.warning("Cannot write run_log: db not found at %s", db_path)
            return

        input_hash = genome_hash(input_file)
        now = datetime.now(timezone.utc).isoformat()

        def _log_run():
            """Inner function for retry wrapper."""
            conn = _get_connection(db_path)
            try:
                ensure_run_log(conn)
                # The loader's run_log keeps one row per (input_hash, tool): a genome's newest run replaces it.
                conn.execute(
                    "INSERT OR REPLACE INTO run_log "
                    "(run_id, input_hash, tool, input_path, row_count, rules_completed, status, loaded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, input_hash, workflow_name, input_file, 0, rules_completed, status, now),
                )
                conn.commit()
            finally:
                conn.close()

        # Retry on transient I/O errors (NFS, lock contention, etc.); the genome's hash is read
        # before the database's write turn is taken.
        with db_turn.turn(db_path, wait=db_turn.CONTROLLER_WAIT):
            _retry_operation(_log_run, max_retries=3, initial_delay=0.5)

        LOGGER.info("Logged workflow run: %s run_id=%s status=%s rules_completed=%d (hash %s...)",
                    workflow_name, run_id, status, rules_completed, input_hash[:12])

    except Exception as e:
        # Non-fatal: log the error but don't crash the workflow
        LOGGER.warning(
            "Failed to log workflow run to database (non-fatal): %s. "
            "Workflow execution was %s, but logging failed.",
            e, status
        )
