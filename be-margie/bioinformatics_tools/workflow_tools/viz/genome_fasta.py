"""genome_fasta.py -- the genome's own sequences, for the map and the circular figure.

A run keeps a link to each genome's file in <run folder>/.margie-input/<genome>.<fna|fa|fasta>[.gz]
(workflow.named_with_hash). From it the maps take each sequence's length and what its FASTA header
calls it. Only the header's own words are used: "plasmid" or "chromosome". A header that says
neither, or both, leaves the sequence unnamed.
"""
from __future__ import annotations

import glob
import gzip
import re
from pathlib import Path

FASTA_NAME = re.compile(r"\.(fna|fa|fasta|fas|fsa|fsa_nt|seq)(\.gz)?$", re.I)


def find_fasta(table: str | Path, genome: str, given: str | None = None) -> Path | None:
    """The genome's FASTA: the one given, else the run's link to it, looked for beside the table's
    folder and up to three folders above it; None when it is not there."""
    if given:
        p = Path(given)
        return p if p.is_file() else None
    here = Path(table).resolve().parent
    for d in (here, *list(here.parents)[:3]):
        links = d / ".margie-input"
        if not links.is_dir():
            continue
        for p in sorted(links.glob(glob.escape(genome) + ".*")):
            if FASTA_NAME.search(p.name) and p.is_file():
                return p
    return None


def kind_of(header: str) -> str:
    """What a FASTA header calls its sequence: "plasmid", "chromosome", or "" (neither, or both)."""
    h = header.lower()
    plasmid, chromosome = bool(re.search(r"\bplasmids?\b", h)), bool(re.search(r"\bchromosomes?\b", h))
    return "plasmid" if plasmid and not chromosome else "chromosome" if chromosome and not plasmid else ""


def read_sequences(path: str | Path) -> dict[str, dict]:
    """{sequence id: {"len": bases, "kind": from its header}}, in the file's order."""
    opener = gzip.open if str(path).endswith(".gz") else open
    seqs: dict[str, dict] = {}
    cur = None
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith(">"):
                parts = line[1:].strip().split(None, 1)
                if not parts:
                    cur = None
                    continue
                cur = seqs.setdefault(parts[0], {"len": 0, "kind": kind_of(parts[1] if len(parts) > 1 else "")})
            elif cur is not None:
                cur["len"] += len(line.strip())
    return seqs


def genome_sequences(table: str | Path, genome: str, given: str | None = None) -> tuple[dict[str, dict], Path | None]:
    """The genome's sequences ({} when its FASTA cannot be found or read) and the file read."""
    path = find_fasta(table, genome, given)
    if path is None:
        return {}, None
    try:
        return read_sequences(path), path
    except OSError:
        return {}, None
