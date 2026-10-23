"""A run started before cache-report.tsv was written gets its report back from its job log
(cache_report.rows_from_log): genome-level restores, protein-level shares and the database."""

import re

from bioinformatics_tools.workflow_tools import cache_report as cr

RUN = "/scratch/c/u/margie/margie-output/2026-10-23-1510"
G = "Bacteroides_thetaiotaomicron_GCF_014131755.1"
LOG = [
    "[11:10:58 INFO workflow] - main_database: /scratch/c/u/margie-2026/sqlite/u-margie-base-v1.db",
    "[2026-10-23 11:11:09] DEBUG workflow: Received command: ['snakemake', \"main_database='/elsewhere.db'\"]",
    f"[2026-10-23 12:01:02] INFO output_cache: Restored from cache: {RUN}/{G}/interpro/interpro_results.tsv",
    f"- Restored from cache: {RUN}/{G}/interpro/interpro_results.tsv",
    f"[2026-10-23 12:01:03] INFO output_cache: Restored from cache: {RUN}/{G}/cog/cog_results.tsv",
    f"[2026-10-23 12:01:04] INFO output_cache: Restored from cache: {RUN}/gtdbtk/batch/summary.tsv",
    f"[2026-10-23 12:02:00] INFO workflow: Protein cache for {G}: cog 5000/5135 cached, kegg 120/5135 cached, pfam 0/5135 cached",
    "[2026-10-23 12:02:01] INFO workflow: Protein cache for Other_genome: no tool to split",
]


def _rows():
    return {(r["genome"], r["step"]): r for r in cr.rows_from_log(LOG, RUN)}


def test_genome_level_restores_and_the_database_come_from_the_log():
    rows = _rows()
    r = rows[(G, "interpro")]
    assert (r["source"], r["level"], r["stage"]) == ("restored", "genome", "after gene calling")
    assert r["database"] == "/scratch/c/u/margie-2026/sqlite/u-margie-base-v1.db"
    assert not any(g == "gtdbtk" for g, _ in rows)


def test_protein_level_shares_and_a_genome_level_restore_wins():
    rows = _rows()
    assert rows[(G, "cog")]["level"] == "genome"
    assert (rows[(G, "kegg")]["source"], rows[(G, "kegg")]["level"]) == ("partly restored", "protein")
    assert "120 of 5,135 proteins" in rows[(G, "kegg")]["detail"]
    assert rows[(G, "pfam")]["source"] == "fresh"
    assert rows[(G, "pfam")]["database"] == ""


def test_the_pattern_finds_every_line_the_parser_reads():
    kept = [line for line in LOG if re.search(cr.LOG_PATTERN, line)]
    assert {(r["genome"], r["step"]) for r in cr.rows_from_log(kept, RUN)} == set(_rows())
