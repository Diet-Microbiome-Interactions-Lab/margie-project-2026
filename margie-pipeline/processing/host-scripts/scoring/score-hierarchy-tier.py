#!/usr/bin/env python3
"""score-hierarchy-tier.py — scoring stage, step 1: hierarchy tier.

Maps each gene's product_descriptor_source in labeled-genes.tsv to a numeric
trust tier following assign-canonical-label.py's priority order
(Tier 1 PGAP/NCBIFAM/TIGRFAM ... Tier 8 COG); "NONE" scores below every tier,
and so does a label that is not informative by labeling's rule
(labeling/descriptor_rules.py), such as a "hypothetical protein" from
labeling's fallback pass.
"""
import argparse
import csv
import sys
from pathlib import Path

csv.field_size_limit(10_000_000)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labeling"))
import descriptor_rules as R  # noqa: E402

# tool_name -> (tier_score, tier_name), following assign-canonical-label.py.
HIERARCHY_TIER = {
    "PGAP": (4, "tier1_curated_prokaryote_family"),
    "NCBIFAM": (4, "tier1_curated_prokaryote_family"),
    "TIGRFAM": (4, "tier1_curated_prokaryote_family"),
    "HAMAP": (3, "tier2_curated_protein_assignment"),
    "PIRSF": (3, "tier2_curated_protein_assignment"),
    "UNIPROT": (3, "tier2_curated_protein_assignment"),
    "KEGG": (2, "tier3_pathway_assignment"),
    "EGGNOG": (2, "tier4_orthology_assignment"),
    "RAST": (1, "tier5_fallback"),
    "PFAM": (0, "tier6_domain_assignment"),
    "CDD": (0, "tier7_domain_assignment"),
    "COG": (0, "tier8_orthology_assignment"),
}
_NO_WINNER_SCORE, _NO_WINNER_NAME = -1, "no_qualifying_winner"
# A label that names no function scores as low as no winner.
_UNINFORMATIVE_SCORE, _UNINFORMATIVE_NAME = -1, "uninformative_label"
# labeled-genes.tsv column holding a source's best-hit statistic, for its gate.
_STAT_COLUMN = {"UNIPROT": "UNIPROT_best_hit_percent_identity"}

_IDENTITY_COLUMNS = [
    "feature_id",
    "organism_name",
    "best_consensus_product_descriptor",
    "product_descriptor_source",
    "product_descriptor_source_id",
]


def score_hierarchy_tier(product_descriptor_source, labeled_row=None):
    """Returns (tier_score, tier_name) for a label source, or the no-winner pair.

    With the labeled-genes.tsv row, a label that is not informative (R.hit_is_informative on
    the label, its source id and, for UniProt, the identity) gets the uninformative pair.
    """
    tier = HIERARCHY_TIER.get(product_descriptor_source, (_NO_WINNER_SCORE, _NO_WINNER_NAME))
    if labeled_row is None or product_descriptor_source not in HIERARCHY_TIER:
        return tier
    if not R.hit_is_informative(product_descriptor_source,
                                labeled_row.get("product_descriptor_source_id", "") or "",
                                labeled_row.get("best_consensus_product_descriptor", "") or "",
                                labeled_row.get(_STAT_COLUMN.get(product_descriptor_source, ""), "") or ""):
        return _UNINFORMATIVE_SCORE, _UNINFORMATIVE_NAME
    return tier


def main() -> None:
    """Streams labeled-genes.tsv with csv and writes each gene's hierarchy tier."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labeled-input", required=True,
                        help="assign-canonical-label.py's output TSV (labeled-genes.tsv)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    labeled_path = Path(args.labeled_input)
    if not labeled_path.is_file():
        print(f"[score-hierarchy-tier] ERROR: input not found: {labeled_path}", file=sys.stderr)
        raise SystemExit(1)

    out_columns = _IDENTITY_COLUMNS + ["hierarchy_tier_score", "hierarchy_tier_name"]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tier_counts = {}
    n = 0
    with open(labeled_path, newline="") as fh, open(output_path, "w", newline="") as out_fh:
        reader = csv.DictReader(fh, delimiter="\t")
        writer = csv.DictWriter(out_fh, fieldnames=out_columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            source = row.get("product_descriptor_source", "")
            out_row = {col: row.get(col, "") for col in _IDENTITY_COLUMNS}
            score, name = score_hierarchy_tier(source, row)
            out_row["hierarchy_tier_score"] = str(score)
            out_row["hierarchy_tier_name"] = name
            writer.writerow(out_row)
            tier_counts[name] = tier_counts.get(name, 0) + 1
            n += 1

    print(f"[score-hierarchy-tier] Wrote {n} genes → {output_path}")
    for name, count in sorted(tier_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {name:40s} {count:6d} ({100.0 * count / n:.1f}%)")


if __name__ == "__main__":
    main()
