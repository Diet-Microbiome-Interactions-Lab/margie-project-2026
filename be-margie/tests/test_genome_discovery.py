"""A run uses the genomes directly in its folder, as the step plan (margie_sb.smk) and the website
see them: one in a subfolder would go to GTDB-Tk and then have no rule to call its genes."""

import re
from pathlib import Path

from bioinformatics_tools.workflow_tools.workflow_helpers import discover_genomes

ROOT = Path(__file__).resolve().parents[1] / "bioinformatics_tools" / "workflow_tools"


def test_only_the_folders_own_genomes(tmp_path):
    (tmp_path / "a.fna").write_text(">a\nACGT\n")
    (tmp_path / "b.fasta").write_text(">b\nACGT\n")
    (tmp_path / "fna").mkdir()
    (tmp_path / "fna" / "c.fna").write_text(">c\nACGT\n")
    assert sorted(discover_genomes(str(tmp_path))) == ["a", "b"]


def test_the_run_and_the_step_plan_find_genomes_alike():
    # Neither asks for subfolders: dane_wf (workflow.py) and Snakemake (margie_sb.smk).
    for name in ("workflow.py", "margie_sb.smk"):
        calls = re.findall(r"discover_genomes\(([^)]*)\)", (ROOT / name).read_text())
        assert calls and not any("recursive=True" in c for c in calls), name
