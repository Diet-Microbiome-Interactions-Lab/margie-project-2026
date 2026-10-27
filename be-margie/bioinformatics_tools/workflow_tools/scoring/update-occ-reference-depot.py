#!/usr/bin/env python3
"""Adds one organism to the depot-hosted OCC reference, or replaces its counts when it is there.

Runs before per-organism C3 scoring so scoring reads the current cross-organism
operon database. A genome already in the reference (by content fingerprint, else
by name) has its stored contribution replaced by its current one, so a second run
of the same annotation leaves the counts as they were.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
# Starter reference shipped with MARGIE (see reference/operon-db.manifest.txt);
# a run's own reference is seeded from it the first time none exists.
DEFAULT_REFERENCE = _THIS_DIR / "reference" / "operon-db.pkl"
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import c3_lib as L  # noqa: E402
import c3_occ  # noqa: E402


def _read_organism_from_labeled(labeled_path: Path) -> str:
    """Returns organism_name from the first row of labeled-genes.tsv (csv)."""
    with labeled_path.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            return (row.get("organism_name") or "").strip()
    return ""


def main() -> None:
    """Loads the organism's genes and, under an fcntl lock, adds or replaces them in the OCC reference and writes a token file."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--organism", required=True, help="Genome stem / organism name")
    ap.add_argument("--labeled-input", required=True, help="labeling/labeled-genes.tsv")
    ap.add_argument("--operon-info-input", required=True, help="labeling/labeled-genes-operon-info.tsv")
    ap.add_argument("--reference", required=True, help="Depot OCC reference pickle path")
    ap.add_argument("--output-token", required=True, help="Token file marking OCC update completion")
    args = ap.parse_args()

    organism = (args.organism or "").strip()
    labeled_path = Path(args.labeled_input)
    operon_info_path = Path(args.operon_info_input)
    reference_path = Path(args.reference)
    token_path = Path(args.output_token)

    for p in (labeled_path, operon_info_path):
        if not p.is_file():
            print(f"[update-occ-reference] ERROR: input not found: {p}", file=sys.stderr)
            raise SystemExit(1)

    labeled_org = _read_organism_from_labeled(labeled_path)
    if labeled_org and organism and labeled_org != organism:
        print(
            f"[update-occ-reference] ERROR: organism mismatch: --organism={organism} "
            f"but labeled-genes has organism_name={labeled_org}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not organism:
        organism = labeled_org
    if not organism:
        print("[update-occ-reference] ERROR: organism could not be determined", file=sys.stderr)
        raise SystemExit(1)

    run_root = labeled_path.parents[2]
    # compute_hash=True adds per-gene aa_hash for the genome content fingerprint.
    genes = L.load_organism(organism, labeled_path, operon_info_path, compute_hash=True)
    if genes.empty:
        print(f"[update-occ-reference] ERROR: no genes loaded for organism {organism}", file=sys.stderr)
        raise SystemExit(1)

    reference_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = Path(str(reference_path) + ".lock")
    with lock_path.open("a+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        if reference_path.is_file():
            ref = c3_occ.load_reference(reference_path)
        elif DEFAULT_REFERENCE.is_file():
            ref = c3_occ.load_reference(DEFAULT_REFERENCE)
            print(f"[update-occ-reference] no reference at {reference_path}; starting from the shipped "
                  f"operon-db.pkl ({len(ref.get('organisms_added', ()))} organisms)")
        else:
            ref = c3_occ.new_reference()

        before = len(ref.get("organisms_added", set()))
        # The same genome is known by its content (its proteins), whatever name it comes under, else by
        # name: one already in the reference has its counts replaced under the name it has there, so
        # they follow its current annotation.
        fingerprint = L.genome_fingerprint(genes["aa_hash"])
        known_as = c3_occ.load_members(reference_path).get(fingerprint) if fingerprint else None
        in_ref = ref.get("organisms_added", set())
        if known_as and known_as in in_ref:
            token = known_as
        elif organism in in_ref:
            token = organism
        else:
            token = None
        same_genome = token if token is not None and token != organism else None
        already_present = token is not None

        replaced = c3_occ.replace_organism(ref, genes, run_root, organism, token=token)
        c3_occ.finalize_reference(ref)
        c3_occ.save_reference(ref, reference_path)
        # Records the content fingerprint so scoring can leave this genome out by content.
        c3_occ.record_member(reference_path, fingerprint, token or organism)
        # Records gene/operon tallies used for figure provenance.
        c3_occ.record_pool_stats(reference_path, fingerprint, token or organism,
                                 L.genome_pool_stats(genes))

        after = len(ref.get("organisms_added", set()))
        # The reference's size now, for Results (a genome scored against fewer can be scored again).
        c3_occ.write_text_atomic(Path(str(reference_path) + ".summary.json"), json.dumps({
            "genomes": after, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")
        added = after - before
        status = (f"already_present_as={same_genome}" if same_genome else
                  "already_present" if already_present else ("added" if added > 0 else "no_change"))
        # replaced: the old counts came off exactly; replaced_from_recomputed_counts: they predate
        # stored contributions, so the counts recomputed from the current files came off.
        contribution = {"added": "added", "stored": "replaced",
                        "recomputed": "replaced_from_recomputed_counts"}[replaced]
        msg = (
            f"occ reference status={status}; contribution={contribution}; organism={organism}; "
            f"fingerprint={fingerprint[:12] or '(none)'}; "
            f"organisms_in_reference={after}; reference={reference_path}"
        )
        token_path.write_text(msg + "\n")

    print(f"[update-occ-reference] {msg}")


if __name__ == "__main__":
    main()
