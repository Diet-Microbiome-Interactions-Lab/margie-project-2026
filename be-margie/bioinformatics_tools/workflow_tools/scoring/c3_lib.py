#!/usr/bin/env python3
"""Descriptor gate and per-organism loader for the C3 operon-context scorer.

is_uninformative() and clean_descriptor() decide whether a descriptor names a
function and normalise it (the gate is labeling/descriptor_rules.py, shared
with labeling and score-c1-tool-coverage.py);
load_organism() joins labeled-genes.tsv and labeled-genes-operon-info.tsv into
one pandas row per gene.
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

csv.field_size_limit(10_000_000)


# The informative gate is labeling's (labeling/descriptor_rules.py), shared with C1.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labeling"))
import descriptor_rules as _rules  # noqa: E402

is_uninformative = _rules.is_uninformative


# ─── Descriptor cleaning: SOURCE: tags stripped so sources group together ───
_SOURCE_PREFIX_RE = _rules.SOURCE_TAG_RE


def clean_descriptor(desc: str) -> str:
    """Returns the functional text: the right side of "raw ## readable", without leading SOURCE: tags (regex)."""
    d = (desc or "").strip()
    if not d:
        return ""
    # "5S rRNA ## 5S ribosomal RNA" -> keeps the more descriptive right side.
    if " ## " in d:
        left, right = d.split(" ## ", 1)
        d = right.strip() if right.strip() else left.strip()
    # Strips leading SOURCE: tags until none remain (e.g. "JCVI: PRK: x").
    return _rules.strip_source_tags(d)


def sha256_hash(seq: str) -> str:
    """Returns the SHA-256 hex digest of the upper-cased sequence (hashlib)."""
    return hashlib.sha256((seq or "").strip().upper().encode("utf-8")).hexdigest()


def genome_fingerprint(aa_hashes) -> str:
    """Returns a genome content fingerprint: SHA-256 over its sorted non-empty per-gene aa_hashes.

    Identifies a genome in the OCC reference independent of its name; "" when there are no hashes.
    """
    hs = sorted(h for h in aa_hashes if h)
    if not hs:
        return ""
    return hashlib.sha256("\n".join(hs).encode("utf-8")).hexdigest()


# Fields of a genome's pool-stats record, in sidecar TSV order
POOL_STAT_FIELDS = ("total_genes", "operonic_genes", "singleton_genes",
                    "n_operons", "n_informative_operons", "n_uninformative_operons")


def genome_pool_stats(genes) -> dict:
    """Counts genes and operons for one genome from a load_organism() DataFrame (pandas groupby).

    An operon is informative when informative members outnumber uninformative
    ones (the OCC qualifying gate). Returns a dict over POOL_STAT_FIELDS.
    """
    total = len(genes)
    op = genes[genes["operon_id"].astype(str).str.startswith("operon_")]
    n_op = n_inf_op = n_unf_op = 0
    for _, sub in op.groupby("operon_id"):
        inf = sum(1 for u, d in zip(sub["uninformative"], sub["clean_descriptor"])
                  if (not bool(u)) and str(d).strip())
        n_op += 1
        if inf > (len(sub) - inf) and inf > 0:
            n_inf_op += 1
        else:
            n_unf_op += 1
    return dict(total_genes=total, operonic_genes=len(op),
                singleton_genes=total - len(op), n_operons=n_op,
                n_informative_operons=n_inf_op, n_uninformative_operons=n_unf_op)


def _to_int(v, default=0):
    """Returns int(float(v)), or default when it cannot be parsed."""
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return default


def _to_float(v, default=float("nan")):
    """Returns float(v), or default when it cannot be parsed."""
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return default


def load_organism(organism: str, labeled_path: Path, operon_path: Path,
                  compute_hash: bool = True) -> pd.DataFrame:
    """Joins labeled-genes.tsv and labeled-genes-operon-info.tsv on feature_id into a pandas DataFrame."""
    # Pass 1: operon-info (small, authoritative for operon membership)
    operon = {}
    with open(operon_path, newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            fid = (row.get("feature_id") or "").strip()
            if not fid:
                continue
            operon[fid] = {
                "operon_id": (row.get("operon_id") or "").strip(),
                "member_count": _to_int(row.get("operon_member_count")),
                "position_in_operon": _to_int(row.get("operon_gene_position_in_operon")),
                "operon_prob": _to_float(row.get("operon_probability_geometric_mean")),
            }

    # Pass 2: labeled-genes (coordinates, descriptor, aa_seq)
    records = []
    with open(labeled_path, newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            fid = (row.get("feature_id") or "").strip()
            if not fid:
                continue
            full_desc = (row.get("best_consensus_product_descriptor") or "").strip()
            clean = clean_descriptor(full_desc)
            aa_seq = (row.get("aa_seq") or "").strip()
            op = operon.get(fid, {})
            operon_id = op.get("operon_id", "")
            in_operon = operon_id.startswith("operon_")
            rec = {
                "organism": organism,
                "feature_id": fid,
                "full_descriptor": full_desc,
                "clean_descriptor": clean,
                "aa_hash": sha256_hash(aa_seq) if (compute_hash and aa_seq) else "",
                "aa_length": _to_int(row.get("aa_length")),
                "start": _to_int(row.get("gene_start")),
                "end": _to_int(row.get("gene_end")),
                "strand": (row.get("RAST_strand") or "").strip() or "+",
                "operon_id": operon_id if in_operon else "",
                "in_operon": in_operon,
                "member_count": op.get("member_count", 0),
                "position_in_operon": op.get("position_in_operon", 0),
                "operon_prob": op.get("operon_prob", float("nan")),
                "uninformative": is_uninformative(clean),
            }
            records.append(rec)
    return pd.DataFrame.from_records(records)
