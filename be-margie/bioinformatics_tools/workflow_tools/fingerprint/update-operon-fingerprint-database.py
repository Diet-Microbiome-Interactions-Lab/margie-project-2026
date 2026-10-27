#!/usr/bin/env python3
"""update-operon-fingerprint-database.py — merges one genome's operon fingerprints into the shared pools.

Counts each distinct operon once and adds it to four pools, keyed by the
evidence/label ordered/composition hashes from add-operon-fingerprint.py,
using the same fcntl lock and atomic write (temporary file and os.replace) as
update-fingerprint-database.py. A genome is known by its full genome hash
(--genome-hash, kept in each pool's <pool>.genomes.tsv): one already in a pool,
under this name or another, has its previous entries replaced. Columns: pattern_id, fingerprint_hash,
members_in_order, fingerprint_frequency (operons with this hash),
fingerprint_label_frequency (operons with this member sequence), organisms,
organism_counts (each genome's operons with this hash, "name=count" joined by "|").
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

csv.field_size_limit(10_000_000)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pool_members as M  # noqa: E402

_LOG = "[update-operon-fingerprint-database]"

_OPERON_FP_RE = re.compile(
    r"^operon hash by evidence \(ordered\): (?P<evidence_ordered>\S+) \|\| "
    r"operon hash by evidence \(composition\): (?P<evidence_composition>\S+) \|\| "
    r"operon hash by label \(ordered\): (?P<label_ordered>\S+) \|\| "
    r"operon hash by label \(composition\): (?P<label_composition>\S+) \|\| "
    r"members \(in order\): (?P<members>.*?) \|\| "
    r"gene_pattern_hashes: .*$"
)


def parse_operon_fingerprint(value: str) -> dict | None:
    """Parses an operon fingerprint string by regex into its four hashes and member list, or None."""
    m = _OPERON_FP_RE.match(value)
    if not m:
        return None
    return m.groupdict()


def read_new_genome(operon_fp_tsv: Path) -> dict[str, dict]:
    """Reads the per-gene operon fingerprint TSV with csv and returns one parsed fingerprint per operon_id."""
    operons: dict[str, dict] = {}
    n_unparsed = 0
    with open(operon_fp_tsv, newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            oid = row.get("operon_id", "") or ""
            # Real operon ids start with "operon_" (NOT_IN_AN_OPERON and NOT_APPLICABLE_NON_CODING do not).
            if not oid.startswith("operon_") or oid in operons:
                continue
            parsed = parse_operon_fingerprint(row.get("operon_fingerprint", ""))
            if parsed is None:
                if row.get("operon_fingerprint", ""):
                    n_unparsed += 1
                continue
            operons[oid] = parsed
    if n_unparsed:
        print(f"[update-operon-fingerprint-database] WARNING: {n_unparsed} non-empty operon_fingerprint "
              f"values did not match the expected format, skipped", file=sys.stderr)
    return operons


def update_pool(operons: dict[str, dict], organism: str, db_tsv: Path, key: str,
                genome_hash: str = "") -> None:
    """Updates one pool keyed on the `key` hash, holding an exclusive fcntl lock."""
    db_tsv.parent.mkdir(parents=True, exist_ok=True)
    lock_path = db_tsv.with_suffix(".lock")
    with open(lock_path, "w") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            _do_update(operons, organism, db_tsv, key, genome_hash)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _do_update(new_operons: dict[str, dict], organism: str, db_tsv: Path, key: str,
               genome_hash: str = "") -> None:
    """Merges operon counts into a pool TSV, replacing the genome's previous entries, and writes it and its metadata JSON atomically."""
    patterns: dict[str, dict] = {}
    if db_tsv.exists() and db_tsv.stat().st_size > 0:
        with db_tsv.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                h = row["fingerprint_hash"]
                patterns[h] = {
                    "pattern_id": row["pattern_id"],
                    "members_in_order": row["members_in_order"],
                    "operon_count": int(row["fingerprint_frequency"]),
                    "organisms": set(o for o in row.get("organisms", "").split("|") if o),
                    "counts": M.parse_counts(row.get(M.COUNTS_COLUMN, "")),
                }

    # A genome counts once, by its genome hash: its previous entries (any name) are replaced.
    members = M.load_members(db_tsv)
    previous = M.remove_genome(patterns, organism, "operon_count", f"{_LOG} {db_tsv.name}:",
                               genome_hash, members)

    # Each distinct operon counts once, even when a genome shares a hash.
    next_id = M.next_pattern_number(patterns)
    for oid, parsed in new_operons.items():
        h = parsed[key]
        if h not in patterns:
            patterns[h] = {"pattern_id": f"pattern_{next_id}", "members_in_order": parsed["members"],
                           "operon_count": 0, "organisms": set(), "counts": {}}
            next_id += 1
        patterns[h]["operon_count"] += 1
        patterns[h]["organisms"].add(organism)
        patterns[h]["counts"][organism] = patterns[h]["counts"].get(organism, 0) + 1
    # Patterns that only the replaced entries held are dropped.
    patterns = {h: p for h, p in patterns.items() if p["operon_count"] > 0 and p["organisms"]}

    label_freq: dict[str, int] = {}
    for pdata in patterns.values():
        label_freq[pdata["members_in_order"]] = label_freq.get(pdata["members_in_order"], 0) + pdata["operon_count"]

    def _write(fh):
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["pattern_id", "fingerprint_hash", "members_in_order",
                         "fingerprint_frequency", "fingerprint_label_frequency", "organisms",
                         M.COUNTS_COLUMN])
        for h, pdata in sorted(patterns.items(), key=lambda item: -item[1]["operon_count"]):
            writer.writerow([
                pdata["pattern_id"], h, pdata["members_in_order"], pdata["operon_count"],
                label_freq[pdata["members_in_order"]], "|".join(sorted(pdata["organisms"])),
                M.format_counts(pdata["counts"]),
            ])
    M.write_atomic(db_tsv, _write)
    for name in previous:
        members.pop(name, None)
    members[organism] = genome_hash or M.genome_key(organism)
    M.save_members(db_tsv, members)

    meta_path = db_tsv.parent / f"operon-fingerprint-database-{key}-metadata.json"
    meta = {
        "total_organisms": len({o for p in patterns.values() for o in p["organisms"]}),
        "total_operons": sum(p["operon_count"] for p in patterns.values()),
        "total_patterns": len(patterns),
        "total_unique_member_sequences": len(label_freq),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "last_updated_by": organism,
    }
    M.write_atomic(meta_path, lambda fh: fh.write(json.dumps(meta, indent=2)))


_POOLS = [
    ("evidence_ordered", "--evidence-ordered-database"),
    ("evidence_composition", "--evidence-composition-database"),
    ("label_ordered", "--label-ordered-database"),
    ("label_composition", "--label-composition-database"),
]


def main() -> None:
    """Reads the genome's operon fingerprints and updates all four pools."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--operon-fingerprint-input", required=True,
                        help="this genome's labeled-genes-operon-fingerprint.tsv")
    parser.add_argument("--organism", required=True, help="organism identifier to stamp in the pools")
    parser.add_argument("--evidence-ordered-database", required=True)
    parser.add_argument("--evidence-composition-database", required=True)
    parser.add_argument("--label-ordered-database", required=True)
    parser.add_argument("--label-composition-database", required=True)
    parser.add_argument("--genome-hash", default="",
                        help="the genome's full hash (fa1: and 64 hexadecimal digits); without it, the hash ending its name")
    args = parser.parse_args()

    operon_fp_path = Path(args.operon_fingerprint_input)
    if not operon_fp_path.is_file():
        print(f"[update-operon-fingerprint-database] ERROR: input not found: {operon_fp_path}", file=sys.stderr)
        raise SystemExit(1)

    operons = read_new_genome(operon_fp_path)
    print(f"[update-operon-fingerprint-database] {args.organism}: {len(operons)} distinct operons")

    for key, flag in _POOLS:
        db_path = getattr(args, flag.lstrip("-").replace("-", "_"))
        update_pool(operons, args.organism, Path(db_path), key, args.genome_hash)
        print(f"[update-operon-fingerprint-database] Updated {key} pool: {db_path}")
    print(f"[update-operon-fingerprint-database] Done.")


if __name__ == "__main__":
    main()
