"""The gene caller's columns, named for the caller that called the genome's genes.

RASTtk's gene table names its own columns RAST_ (strand, feature type, description). Prodigal's
names them PRODIGAL_ (strand, feature type; Prodigal calls genes and names no function, so it has
no description). A genome's tables keep its caller's names through consolidation, labeling,
scoring and the final tables (RAST_start or PRODIGAL_start, and so on), and the readers here take
whichever is there. Standard library only: the pipeline's scripts import it by path.
"""
from __future__ import annotations

from typing import Iterable, Mapping

RAST = "RAST_"
PRODIGAL = "PRODIGAL_"
PREFIXES = (RAST, PRODIGAL)

# The fields a gene caller's columns carry, with or without a "Column-X: " prefix (final tables).
FIELDS = ("feature_id", "feature_type", "strand", "start", "end", "na_sequence", "aa_sequence", "description")


def bare(column: str) -> str:
    """A final table's column without its "Column-X: " prefix."""
    return column.split(": ", 1)[1] if column.startswith("Column-") and ": " in column else column


def prefix_of(columns: Iterable[str] | None) -> str:
    """PRODIGAL_ when the columns are Prodigal's gene calls (and none are RASTtk's), else RAST_."""
    names = {bare(c) for c in (columns or ())}
    prodigal = any(PRODIGAL + f in names for f in FIELDS)
    rast = any(RAST + f in names for f in FIELDS)
    return PRODIGAL if prodigal and not rast else RAST


def value(row: Mapping[str, str], field: str, default: str = "") -> str:
    """The row's gene-call field (strand, feature_type, start ...) under either caller's name."""
    for p in PREFIXES:
        v = row.get(p + field)
        if v not in (None, ""):
            return v
    return default


def identity_columns(prefix: str) -> list[str]:
    """The caller's columns that consolidation, labeling and the final tables carry for each gene:
    feature type and strand, and RASTtk's description (Prodigal names no function)."""
    return [prefix + "feature_type", prefix + "strand"] + ([prefix + "description"] if prefix == RAST else [])
