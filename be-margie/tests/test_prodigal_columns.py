"""Prodigal's gene-call columns keep Prodigal's name (PRODIGAL_) from its table to the final tables;
RASTtk's keep RAST_ as before. Prodigal names no function, so its genomes have no RAST_description,
and labeling says RASTtk did not run for them."""

import csv
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from bioinformatics_tools.api.services import final_summary
from bioinformatics_tools.workflow_tools import gene_caller

WT = Path(__file__).resolve().parents[1] / "bioinformatics_tools" / "workflow_tools"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, rows: list[dict]) -> Path:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    return path


def _rows(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


GENE = {"organism_name": "G", "feature_id": "c1_2", "domain": "Bacteria", "gene_id": "c1_10+300",
        "gene_start": "10", "gene_end": "309", "na_seq": "ATG", "aa_seq": "M", "na_length": "300", "aa_length": "99",
        "KEGG_id": "K00001", "KEGG_description": "alcohol dehydrogenase", "KEGG_evalue": "1e-50"}
RASTTK = {"RAST_feature_type": "CDS", "RAST_strand": "+", "RAST_description": "Alcohol dehydrogenase (EC 1.1.1.1)"}
PRODIGAL = {"PRODIGAL_feature_type": "CDS", "PRODIGAL_strand": "-", "PRODIGAL_conf": "99.9"}


def test_the_caller_is_read_from_the_columns():
    assert gene_caller.prefix_of(["feature_id", "RAST_strand"]) == "RAST_"
    assert gene_caller.prefix_of(["feature_id", "PRODIGAL_strand", "PRODIGAL_conf"]) == "PRODIGAL_"
    assert gene_caller.prefix_of(["Column-E: PRODIGAL_feature_id", "Column-H: PRODIGAL_start"]) == "PRODIGAL_"
    assert gene_caller.prefix_of([]) == "RAST_"
    assert gene_caller.value({"PRODIGAL_strand": "-"}, "strand") == "-"
    assert gene_caller.value({"RAST_strand": "+"}, "strand") == "+"
    assert gene_caller.identity_columns("RAST_") == ["RAST_feature_type", "RAST_strand", "RAST_description"]
    assert gene_caller.identity_columns("PRODIGAL_") == ["PRODIGAL_feature_type", "PRODIGAL_strand"]


def test_run_prodigal_names_the_table_for_prodigal(tmp_path):
    """The awk step in run_prodigal, as Snakemake runs it: RAST_ names become PRODIGAL_, the empty
    RAST_description goes, empty cells stay, and a table already in Prodigal's names is left as it is."""
    line = next(x for x in (WT / "margie_sb.smk").read_text().splitlines() if 'RAST_description") d=i' in x).strip()
    cmd = eval('"""' + line + '"""')  # the rule's shell string is a plain Python string
    cmd = re.sub(r"\{params\.output_dir\}", str(tmp_path), cmd).replace("{output.results}", str(tmp_path / "prodigal.tsv"))
    cmd = cmd.replace("{{", "{").replace("}}", "}")
    (tmp_path / "processed").mkdir()
    src = tmp_path / "processed" / "prodigal_gene_calls.tsv"
    header = ["organism", "feature_id", "RAST_strand", "gene_start", "RAST_feature_type", "RAST_description", "partial", "prodigal_mode"]
    src.write_text("\t".join(header) + "\nG\tc1_1\t+\t10\tCDS\t\t00\tsingle\nG\tc1_2\t-\t400\tCDS\t\t\tmeta\n")
    subprocess.run(["bash", "-c", cmd], check=True)
    out = (tmp_path / "prodigal.tsv").read_text().splitlines()
    assert out[0].split("\t") == ["organism", "feature_id", "PRODIGAL_strand", "gene_start", "PRODIGAL_feature_type", "partial", "prodigal_mode"]
    assert out[2].split("\t") == ["G", "c1_2", "-", "400", "CDS", "", "meta"]
    src.write_text("\n".join(out) + "\n")
    subprocess.run(["bash", "-c", cmd], check=True)
    assert (tmp_path / "prodigal.tsv").read_text().splitlines() == out


def test_consolidation_keeps_the_callers_columns():
    plan = _module("fns_t", WT / "consolidation" / "filter-no-stat.py").build_column_plan
    rast = [c[0] for c in plan({"feature_id", *RASTTK})]
    prodigal = [c[0] for c in plan({"feature_id", *PRODIGAL})]
    assert rast[8:13] == ["RAST_feature_type", "RAST_strand", "RAST_description", "na_seq", "aa_seq"]
    assert prodigal[8:12] == ["PRODIGAL_feature_type", "PRODIGAL_strand", "na_seq", "aa_seq"]
    assert not any(c.startswith("RAST_") for c in prodigal)


def test_labeling_keeps_prodigal_columns_and_says_rasttk_did_not_run(tmp_path):
    script = WT / "labeling" / "assign-canonical-label.py"
    got = {}
    for name, extra in (("rast", RASTTK), ("prodigal", PRODIGAL)):
        src = _write(tmp_path / f"{name}.tsv", [{**GENE, **extra}])
        subprocess.run([sys.executable, str(script), "--input", str(src), "--output", str(tmp_path / f"{name}-out.tsv")],
                       check=True, capture_output=True)
        got[name] = _rows(tmp_path / f"{name}-out.tsv")[0]
    rast, prodigal = got["rast"], got["prodigal"]
    assert rast["RAST_strand"] == "+" and rast["RAST_description"].startswith("Alcohol")
    assert "RAST(hit)" in rast["product_descriptor_hierarchy"]
    assert prodigal["PRODIGAL_strand"] == "-" and prodigal["PRODIGAL_feature_type"] == "CDS"
    assert not any(k.startswith("RAST_") for k in prodigal)
    assert "RAST(not run)" in prodigal["product_descriptor_hierarchy"]
    assert "RAST=[not_run]" in prodigal["product_descriptor_audit_trail"]
    assert prodigal["best_consensus_product_descriptor"] == "alcohol dehydrogenase"


def test_fingerprints_carry_the_callers_columns(tmp_path):
    script = WT / "fingerprint" / "add-gene-fingerprint.py"
    labeled = _write(tmp_path / "labeled.tsv", [{**GENE, **PRODIGAL, "best_consensus_product_descriptor": "x"}])
    scores = _write(tmp_path / "scores.tsv", [{"feature_id": "c1_2", "c1_score": "0.1"}])
    outs = {k: tmp_path / f"{k}.tsv" for k in ("hash-pattern", "hash-label", "label-pattern", "full", "full-with-scores")}
    subprocess.run([sys.executable, str(script), "--labeled-input", str(labeled), "--confidence-final-input", str(scores),
                    *[a for k, p in outs.items() for a in (f"--output-{k}", str(p))]], check=True, capture_output=True)
    row = _rows(outs["full"])[0]
    assert row["PRODIGAL_strand"] == "-" and "RAST_strand" not in row


def test_the_final_table_names_the_gene_columns_for_the_caller():
    sys.path.insert(0, str(WT / "scoring"))
    try:
        final = _module("mfawc_prod_t", WT / "scoring" / "make-final-annotation-with-confidence.py")
    finally:
        sys.path.remove(str(WT / "scoring"))
    assert final._named_columns({"c1_2": {**GENE, **RASTTK}}) == final.BASE_COLUMNS
    named = final._named_columns({"c1_2": {**GENE, **PRODIGAL}})
    for f in ("feature_id", "strand", "start", "end", "na_sequence", "aa_sequence"):
        assert f"PRODIGAL_{f}" in named and f"RAST_{f}" not in named


def test_the_website_summary_reads_prodigal_coordinates():
    lines = ["Column-A: gene_id\tColumn-B: PRODIGAL_feature_id\tColumn-C: PRODIGAL_strand\tColumn-D: PRODIGAL_start\tColumn-E: PRODIGAL_end\tColumn-F: CONFIDENCE_TIER",
             "c1_10+300\tc1_1\t-\t10\t309\thigh", "c1_500+300\tc1_2\t+\t500\t799\tlow"]
    got = final_summary.tally(lines)
    assert got["genes"] == 2 and got["glyph"]["length"] == 799 and got["glyph"]["contigs"] == 1


def test_the_gene_report_finds_neighbours_for_both_callers():
    report = _module("bgr_t", WT / "evidence" / "build-gene-report.py")
    rast = {f"fig|1.2.peg.{n}": {"RAST_strand": "+", "best_consensus_product_descriptor": f"p{n}"} for n in (4, 5, 6)}
    prodigal = {f"contig_7_{n}": {"PRODIGAL_strand": "-", "best_consensus_product_descriptor": f"p{n}"} for n in (4, 5, 6)}
    assert "fig|1.2.peg.4" in report.physical_neighbors_block("fig|1.2.peg.5", rast, {}, n=1)
    block = report.physical_neighbors_block("contig_7_5", prodigal, {}, n=1)
    assert "contig_7_4" in block and "contig_7_6" in block
    assert report.rows_rast({"PRODIGAL_strand": "-"})[0][-1].startswith("not run")
