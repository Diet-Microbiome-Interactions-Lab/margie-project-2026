"""The protein cache names the genomes a genome's cached proteins came from (protein_cache.split's
`sources`): from the genome stored with each protein, or for a cache made before that, from the
organism its rows name. The cache report says it (cache_report.proteins)."""

import json
import sqlite3
from unittest.mock import patch

from bioinformatics_tools.workflow_tools import cache_report, protein_cache

PC = "bioinformatics_tools.workflow_tools.protein_cache"


def _genome(tmp_path, name, proteins):
    """A genome's protein FASTA and its pfam results, one row per protein."""
    faa = tmp_path / f"{name}.faa"
    faa.write_text("".join(f">{fid} protein\n{seq}\n" for fid, seq in proteins))
    folder = tmp_path / name / "pfam"
    folder.mkdir(parents=True)
    (folder / "pfam_results.tsv").write_text(
        "organism_name\tfeature_id\tpfam_hit\n" + "".join(f"{name}\t{fid}\tPF0000{k}\n" for k, (fid, _) in enumerate(proteins)))
    return str(faa), f"{tmp_path / name}/"


def test_a_genome_learns_which_genome_its_cached_proteins_came_from(tmp_path):
    db = str(tmp_path / "margie.db")
    with patch(f"{PC}.tool_key", return_value="k"):
        faa_a, pre_a = _genome(tmp_path, "GenomeA", [("a1", "MKVLAAG"), ("a2", "MSTQRRW")])
        assert protein_cache.store(db, faa_a, pre_a, "pfam", {}, genome="GenomeA") == 2
        faa_b, pre_b = _genome(tmp_path, "GenomeB", [("b1", "MKVLAAG"), ("b2", "MPPPPPP")])
        sources = {}
        counts = protein_cache.split(db, faa_b, pre_b, "GenomeB", ["pfam"], {}, sources=sources)
    assert counts["pfam"] == (1, 1)
    assert sources == {"pfam": {"GenomeA": 1}}
    plan = json.loads((tmp_path / "GenomeB" / "pfam" / "protein-cache" / "plan.json").read_text())
    assert plan["sources"] == {"GenomeA": 1}


def test_a_cache_made_before_the_genome_column_is_read_from_its_rows(tmp_path):
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE protein_cache (aa_hash TEXT NOT NULL, tool TEXT NOT NULL, tool_key TEXT NOT NULL, filename TEXT NOT NULL,
            lines TEXT NOT NULL, cached_at TEXT NOT NULL, PRIMARY KEY (tool, tool_key, filename, aa_hash)) WITHOUT ROWID;
        CREATE TABLE protein_cache_header (tool TEXT NOT NULL, tool_key TEXT NOT NULL, filename TEXT NOT NULL,
            header TEXT NOT NULL, PRIMARY KEY (tool, tool_key, filename)) WITHOUT ROWID;
    """)
    h = protein_cache.protein_hash("MKVLAAG")
    conn.execute("INSERT INTO protein_cache VALUES (?, 'pfam', 'k', 'pfam_results.tsv', ?, 'then')", (h, "OldGenome\tx1\tPF00001"))
    conn.execute("INSERT INTO protein_cache_header VALUES ('pfam', 'k', 'pfam_results.tsv', ?)", ("organism_name\tfeature_id\tpfam_hit",))
    conn.commit()
    conn.close()
    with patch(f"{PC}.tool_key", return_value="k"):
        faa, pre = _genome(tmp_path, "GenomeC", [("c1", "MKVLAAG")])
        sources = {}
        protein_cache.split(db, faa, pre, "GenomeC", ["pfam"], {}, sources=sources)
    assert sources == {"pfam": {"OldGenome": 1}}
    cols = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(protein_cache)")]
    assert "genome" in cols


def test_the_report_names_the_matched_genomes():
    d = cache_report.proteins(812, 1969, sources={"Kytococcus": 600, "Legionella": 200, "Pontimonas": 10, "Other": 2})
    assert d["source"] == cache_report.PARTLY
    assert "matched from Kytococcus (600), Legionella (200), Pontimonas (10) and 1 more" in d["detail"]
    assert "matched from" not in cache_report.proteins(0, 50)["detail"]
