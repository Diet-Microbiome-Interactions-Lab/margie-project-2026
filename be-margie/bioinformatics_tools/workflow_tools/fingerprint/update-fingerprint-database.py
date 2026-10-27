#!/usr/bin/env python3
"""update-fingerprint-database.py — merges one genome's gene fingerprints into the shared database.

Adds the genome's labeled-genes-fingerprint-hash-label.tsv counts to
fingerprint-database.tsv incrementally, under an fcntl lock, written through a
temporary file and os.replace. A genome is known by its full genome hash
(--genome-hash, kept in fingerprint-database.tsv.genomes.tsv): one already in the
database, under this name or another, has its previous entries replaced, so it
counts once and follows its current annotation. Columns: pattern_id, fingerprint_hash, fingerprint_label,
fingerprint_frequency (genes with this pattern), fingerprint_label_frequency
(genes with this label), organisms ("|"-joined), organism_counts (each
genome's genes with this pattern, "name=count" joined by "|").
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

_LOG = "[update-fingerprint-database]"

_HASH_LABEL_RE = re.compile(r"^pattern hash: (?P<hash>\S+) \|\| label: (?P<label>.*)$")


def parse_hash_label(fingerprint_value: str) -> tuple[str, str] | None:
    """Extracts (hash, label) from "pattern hash: ... || label: ..." by regex, or None."""
    m = _HASH_LABEL_RE.match(fingerprint_value)
    if not m:
        return None
    return m.group("hash"), m.group("label")


def read_new_genome(hash_label_tsv: Path, organism: str) -> dict[str, int]:
    """Counts genes per fingerprint hash in one genome with csv and returns ({hash: count}, {hash: label})."""
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    n_unparsed = 0
    with open(hash_label_tsv, newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            parsed = parse_hash_label(row.get("fingerprint", ""))
            if parsed is None:
                n_unparsed += 1
                continue
            h, label = parsed
            counts[h] = counts.get(h, 0) + 1
            labels[h] = label
    if n_unparsed:
        print(f"[update-fingerprint-database] WARNING: {n_unparsed} rows in {hash_label_tsv} "
              f"did not match the expected fingerprint format, skipped", file=sys.stderr)
    return counts, labels


def update_database(counts: dict[str, int], labels: dict[str, str], organism: str,
                     db_tsv: Path, genome_hash: str = "") -> None:
    """Runs _do_update while holding an exclusive fcntl lock on a sibling .lock file."""
    db_tsv.parent.mkdir(parents=True, exist_ok=True)
    lock_path = db_tsv.with_suffix(".lock")
    with open(lock_path, "w") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            _do_update(counts, labels, organism, db_tsv, genome_hash)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def _do_update(new_counts: dict[str, int], new_labels: dict[str, str], organism: str,
                db_tsv: Path, genome_hash: str = "") -> None:
    """Merges new counts into the database TSV, replacing the genome's previous entries, and writes it and its metadata JSON atomically.

    Runs under the lock taken by update_database().
    """
    patterns: dict[str, dict] = {}
    if db_tsv.exists() and db_tsv.stat().st_size > 0:
        with db_tsv.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                h = row["fingerprint_hash"]
                patterns[h] = {
                    "pattern_id": row["pattern_id"],
                    "label": row["fingerprint_label"],
                    "gene_count": int(row["fingerprint_frequency"]),
                    "organisms": set(o for o in row.get("organisms", "").split("|") if o),
                    "counts": M.parse_counts(row.get(M.COUNTS_COLUMN, "")),
                }

    # A genome counts once, by its genome hash: its previous entries (any name) are replaced.
    members = M.load_members(db_tsv)
    previous = M.remove_genome(patterns, organism, "gene_count", _LOG, genome_hash, members)

    next_id = M.next_pattern_number(patterns)
    for h, count in new_counts.items():
        if h in patterns and patterns[h]["organisms"]:
            # Identical hashes should carry identical labels.
            if patterns[h]["label"] != new_labels[h]:
                print(f"{_LOG} WARNING: hash {h} previously mapped to "
                      f"label '{patterns[h]['label']}', now seeing '{new_labels[h]}' from {organism} "
                      f"-- keeping the original, this shouldn't happen if assign-canonical-label.py "
                      f"is deterministic", file=sys.stderr)
        elif h in patterns:
            patterns[h]["label"] = new_labels[h]
        else:
            patterns[h] = {"pattern_id": f"pattern_{next_id}", "label": new_labels[h],
                           "gene_count": 0, "organisms": set(), "counts": {}}
            next_id += 1
        patterns[h]["gene_count"] += count
        patterns[h]["organisms"].add(organism)
        patterns[h]["counts"][organism] = count
    # Patterns that only the replaced entries held are dropped.
    patterns = {h: p for h, p in patterns.items() if p["gene_count"] > 0 and p["organisms"]}

    label_freq: dict[str, int] = {}
    for pdata in patterns.values():
        label_freq[pdata["label"]] = label_freq.get(pdata["label"], 0) + pdata["gene_count"]

    def _write(fh):
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["pattern_id", "fingerprint_hash", "fingerprint_label",
                         "fingerprint_frequency", "fingerprint_label_frequency", "organisms",
                         M.COUNTS_COLUMN])
        for h, pdata in sorted(patterns.items(), key=lambda item: -item[1]["gene_count"]):
            writer.writerow([
                pdata["pattern_id"], h, pdata["label"], pdata["gene_count"],
                label_freq[pdata["label"]], "|".join(sorted(pdata["organisms"])),
                M.format_counts(pdata["counts"]),
            ])
    M.write_atomic(db_tsv, _write)
    for name in previous:
        members.pop(name, None)
    members[organism] = genome_hash or M.genome_key(organism)
    M.save_members(db_tsv, members)

    meta_path = db_tsv.parent / "fingerprint-database-metadata.json"
    meta = {
        "total_organisms": len({o for p in patterns.values() for o in p["organisms"]}),
        "total_genes": sum(p["gene_count"] for p in patterns.values()),
        "total_patterns": len(patterns),
        "total_unique_labels": len(label_freq),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "last_updated_by": organism,
    }
    M.write_atomic(meta_path, lambda fh: fh.write(json.dumps(meta, indent=2)))


def main() -> None:
    """Reads the genome's hash-label table and merges it into the shared database."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hash-label-input", required=True,
                        help="this genome's labeled-genes-fingerprint-hash-label.tsv")
    parser.add_argument("--organism", required=True, help="organism identifier to stamp in the pool")
    parser.add_argument("--fingerprint-database", required=True,
                        help="shared fingerprint-database.tsv path (created if absent, updated in place)")
    parser.add_argument("--genome-hash", default="",
                        help="the genome's full hash (fa1: and 64 hexadecimal digits); without it, the hash ending its name")
    args = parser.parse_args()

    hash_label_path = Path(args.hash_label_input)
    if not hash_label_path.is_file():
        print(f"[update-fingerprint-database] ERROR: input not found: {hash_label_path}", file=sys.stderr)
        raise SystemExit(1)

    db_path = Path(args.fingerprint_database)
    counts, labels = read_new_genome(hash_label_path, args.organism)
    print(f"[update-fingerprint-database] {args.organism}: {sum(counts.values())} genes, "
          f"{len(counts)} distinct patterns")
    print(f"[update-fingerprint-database] Updating: {db_path}")
    update_database(counts, labels, args.organism, db_path, args.genome_hash)
    print(f"[update-fingerprint-database] Done.")


if __name__ == "__main__":
    main()
