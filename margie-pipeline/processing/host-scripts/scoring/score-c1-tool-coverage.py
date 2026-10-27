#!/usr/bin/env python3
"""score-c1-tool-coverage.py — scoring stage, metric C1: tool coverage.

C1 = informative sources / 7, over RAST, KEGG, EGGNOG, COG, PFAM, UNIPROT and
one TIGRFAM cluster slot (PGAP/TIGRFAM/NCBIfam share models). A hit counts only
when labeling's rule finds it informative (labeling/descriptor_rules.py: its own
description, not an accession standing in for one, that names a function, and
for UniProt identity >= 40%); the cluster slot counts when TIGRFAM, PGAP or
NCBIfam (looked at in that order) gives an informative one, and names it. HAMAP, PIRSF, CDD and GENEPROP overlap the
counted tools, and MEROPS/TCDB/DBCAN cover few genes, so none are counted.
Writes the score, count, contributing tools and a "k/7 = x" formula per gene.
"""
import argparse
import csv
import sys
from pathlib import Path

csv.field_size_limit(10_000_000)

# Independent decision tools; TIGRFAM/PGAP/NCBIfam count as one slot.
STANDALONE_DECISION_TOOLS = ["RAST", "COG", "PFAM", "KEGG", "EGGNOG", "UNIPROT"]
TIGRFAM_CLUSTER_SLOT = "TIGRFAM_CLUSTER"
# The slot's members, in the order add-cluster-agreement.py prefers them.
TIGRFAM_CLUSTER_MEMBERS = ["TIGRFAM", "PGAP", "NCBIFAM"]
DECISION_TOOLS = STANDALONE_DECISION_TOOLS + [TIGRFAM_CLUSTER_SLOT]

_IDENTITY_COLUMNS = [
    "feature_id",
    "organism_name",
    "best_consensus_product_descriptor",
    "product_descriptor_source",
    "product_descriptor_source_id",
]

# ─── Informative hit rule ────────────────────────────────────────────────────
# Labeling's rule (labeling/descriptor_rules.py): a hit counts when its description is its
# own (not the accession standing in for a missing one), names a function, and, for UniProt,
# its identity is at least 40%.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labeling"))
import descriptor_rules as R  # noqa: E402

is_uninformative = R.is_uninformative
# labeled-genes.tsv column holding each tool's best-hit statistic (assign-canonical-label.py).
_STAT_COLUMN = {"UNIPROT": "UNIPROT_best_hit_percent_identity"}


def tool_counts(labeled_row, tool):
    """Returns True when the tool's best hit in a labeled-genes.tsv row is informative (R.hit_is_informative)."""
    if tool == "RAST":
        return R.hit_is_informative("RAST", "", labeled_row.get("RAST_description", "") or "")
    return R.hit_is_informative(
        tool,
        labeled_row.get(f"{tool}_best_hit_id", "") or "",
        labeled_row.get(f"{tool}_best_hit_description", "") or "",
        labeled_row.get(_STAT_COLUMN.get(tool, ""), "") or "",
    )


def compute_c1(labeled_row, cluster_row=None):
    """Returns (C1 score, contributing tools) from each tool's best hit in a labeled-genes.tsv row.

    cluster_row is accepted for older callers and not read: the slot follows the descriptions.
    """
    informative_tools = [tool for tool in STANDALONE_DECISION_TOOLS if tool_counts(labeled_row, tool)]
    # The shared slot: the first of its members whose best hit is informative ("hypothetical" counts for nothing).
    member = next((t for t in TIGRFAM_CLUSTER_MEMBERS if tool_counts(labeled_row, t)), None)
    if member:
        informative_tools.append(f"{TIGRFAM_CLUSTER_SLOT}({member})")
    return len(informative_tools) / len(DECISION_TOOLS), informative_tools


def main() -> None:
    """Streams labeled genes with csv and writes the C1 table."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labeled-input", required=True, help="labeled-genes.tsv")
    parser.add_argument("--cluster-agreement-input", required=False,
                        help="accepted for older callers and not read (the TIGRFAM cluster slot "
                             "follows the members' descriptions in labeled-genes.tsv)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    labeled_path = Path(args.labeled_input)
    if not labeled_path.is_file():
        print(f"[score-c1-tool-coverage] ERROR: input not found: {labeled_path}", file=sys.stderr)
        raise SystemExit(1)

    out_columns = _IDENTITY_COLUMNS + [
        "c1_score", "c1_informative_tool_count", "c1_total_tools_considered",
        "c1_informative_tools", "c1_formula",
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    score_sum = 0.0
    with open(labeled_path, newline="") as fh, open(output_path, "w", newline="") as out_fh:
        reader = csv.DictReader(fh, delimiter="\t")
        writer = csv.DictWriter(out_fh, fieldnames=out_columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            c1, informative_tools = compute_c1(row)
            out_row = {col: row.get(col, "") for col in _IDENTITY_COLUMNS}
            out_row["c1_score"] = f"{c1:.4f}"
            out_row["c1_informative_tool_count"] = str(len(informative_tools))
            out_row["c1_total_tools_considered"] = str(len(DECISION_TOOLS))
            out_row["c1_informative_tools"] = ";".join(informative_tools)
            out_row["c1_formula"] = f"{len(informative_tools)}/{len(DECISION_TOOLS)} = {c1:.4f}"
            writer.writerow(out_row)
            score_sum += c1
            n += 1

    print(f"[score-c1-tool-coverage] Wrote {n} genes → {output_path}")
    print(f"    mean C1 = {score_sum / n:.4f}" if n else "    no genes scored")


if __name__ == "__main__":
    main()
