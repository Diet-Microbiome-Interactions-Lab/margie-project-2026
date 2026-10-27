"""Genome membership for the fingerprint pools (update-fingerprint-database.py,
update-operon-fingerprint-database.py). Not run directly.

A genome is known by its content: a run names it <name>--fa1:xxxx (older runs
<name>--xxxxxxxx), the start of its genome hash, and genome_key() strips the
name to that hash, so a renamed genome is the same genome. Each pattern row keeps
every genome's own count (organism_counts), so a genome seen again has its
previous entries replaced. write_atomic() writes a pool through a temporary file
and os.replace.
"""
from __future__ import annotations

import os
import re
import secrets
import stat
import sys
from pathlib import Path

# As in workflow.py and the website: <name>--fa1:<4 hex> or, from older runs, <name>--<8 hex>.
NAMED_WITH_HASH = re.compile(r'--(fa1:[0-9a-f]{4}|[0-9a-f]{8})$')
COUNTS_COLUMN = "organism_counts"


def genome_key(organism: str) -> str:
    """Returns the genome hash ending the name ("fa1:a1b2"), else the name itself."""
    m = NAMED_WITH_HASH.search(organism or "")
    return m.group(1) if m else (organism or "")


def parse_counts(text: str) -> dict[str, int]:
    """Parses "coli--fa1:a1b2=2|dorei--fa1:c3d4=1" into {organism: count}."""
    out: dict[str, int] = {}
    for part in (text or "").split("|"):
        name, sep, n = part.rpartition("=")
        if sep and name:
            try:
                out[name] = int(n)
            except ValueError:
                continue
    return out


def format_counts(counts: dict[str, int]) -> str:
    """Formats {organism: count} as "name=count" pairs joined by "|", sorted by name."""
    return "|".join(f"{o}={counts[o]}" for o in sorted(counts))


def remove_genome(patterns: dict[str, dict], organism: str, count_field: str, log_prefix: str) -> set[str]:
    """Removes, in place, the entries of every pool member that is the same genome as organism.

    Each pattern row is {count_field: int, "organisms": set, "counts": {organism: int}}. A member
    without a recorded count (a pool written before counts were kept) is estimated as its share of
    the row's count the recorded members do not account for, and says so. Rows left with no count
    stay for the caller to prune. Returns the names removed.
    """
    key = genome_key(organism)
    previous = {o for p in patterns.values() for o in p["organisms"] if genome_key(o) == key}
    estimated = 0
    for p in patterns.values():
        here = previous & p["organisms"]
        if not here:
            continue
        unknown = [o for o in p["organisms"] if o not in p["counts"]]
        rest = p[count_field] - sum(p["counts"].values())
        for o in here:
            if o in p["counts"]:
                n = p["counts"].pop(o)
            else:
                n = max(1, round(rest / len(unknown))) if unknown else 1
                estimated += 1
            p[count_field] = max(0, p[count_field] - n)
            p["organisms"].discard(o)
    if previous:
        others = sorted(previous - {organism})
        print(f"{log_prefix} {organism}: replacing its previous entries"
              + (f" (as {', '.join(others)}, the same genome hash {key})" if others else ""))
    if estimated:
        print(f"{log_prefix} WARNING: {estimated} entries of {', '.join(sorted(previous))} had no recorded "
              f"count (written before counts were kept); their counts were estimated", file=sys.stderr)
    return previous


def next_pattern_number(patterns: dict[str, dict]) -> int:
    """Returns one more than the highest "pattern_N" id in the pool, so a new id is unused."""
    highest = 0
    for p in patterns.values():
        _, _, n = str(p.get("pattern_id", "")).rpartition("_")
        if n.isdigit():
            highest = max(highest, int(n))
    return highest + 1


def write_atomic(path: Path, write) -> None:
    """Writes through write(fh) to a temporary file beside path, then os.replace()s it into place,
    keeping the old file's permission bits."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        with open(tmp, "x", newline="", encoding="utf-8") as fh:
            write(fh)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp, stat.S_IMODE(os.stat(path).st_mode))
        except FileNotFoundError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
