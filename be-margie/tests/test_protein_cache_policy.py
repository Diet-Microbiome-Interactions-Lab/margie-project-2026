"""What the protein cache keeps (protein_cache): a protein's results for a tool, keyed by the protein
and the tool's settings, stay across new tool and database versions. A protein computed again keeps
its cached entry when its descriptors are the same and replaces it when they differ (a COG hit abc
in 2026, abd in 2030); the run's gene, genome and file columns are not descriptors. A tool new to a
protein is added and its other tools stay. Each genome's proteins and genes are linked to its
sequence hash."""

import sqlite3

from bioinformatics_tools.workflow_tools import protein_cache

HEADER = "organism_name\tfeature_id\tCOG_id\tCOG_tool_used\tinput_path\n"


def _genome(tmp_path, name, proteins, tool="cog", hits=None):
    """A genome's proteins and one tool's results for them: (feature id, sequence) each."""
    faa = tmp_path / f"{name}.faa"
    faa.write_text("".join(f">{fid} protein\n{seq}\n" for fid, seq in proteins))
    folder = tmp_path / name / tool
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{tool}_results.tsv").write_text(HEADER + "".join(
        f"{name}\t{fid}\t{(hits or {}).get(fid, 'COG0001')}\tCOGclassifier 2.0.0\t/runs/{name}/rast.faa\n" for fid, _ in proteins))
    return str(faa), f"{tmp_path / name}/"


def _entry(db, seq, tool="cog"):
    h = protein_cache.protein_hash(seq)
    return sqlite3.connect(db).execute(
        "SELECT lines, cached_at, genome FROM protein_cache WHERE tool = ? AND aa_hash = ?", (tool, h)).fetchone()


def test_the_key_is_the_tool_and_its_settings():
    assert protein_cache.tool_key("cog", {}) == protein_cache.tool_key("cog", {})
    assert protein_cache.tool_key("cog", {}) != protein_cache.tool_key("cog", {"cog": {"evalue": "1e-9"}})


def test_the_same_descriptors_keep_the_cached_entry(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    protein_cache.store(db, faa, pre, "cog", {}, genome="A")
    before = _entry(db, "MKVLAAG")
    # Another genome computes the protein again: its own gene id, name and files, the same hit.
    faa, pre = _genome(tmp_path, "B", [("b9", "MKVLAAG")])
    assert protein_cache.store(db, faa, pre, "cog", {}, genome="B") == 0
    assert _entry(db, "MKVLAAG") == before


def test_different_descriptors_replace_the_cached_entry(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")], hits={"a1": "COG0abc"})
    protein_cache.store(db, faa, pre, "cog", {}, genome="A")
    faa, pre = _genome(tmp_path, "B", [("b9", "MKVLAAG")], hits={"b9": "COG0abd"})
    assert protein_cache.store(db, faa, pre, "cog", {}, genome="B") == 1
    lines, _, genome = _entry(db, "MKVLAAG")
    assert "COG0abd" in lines and genome == "B"


def test_a_protein_served_from_the_cache_is_not_compared(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")], hits={"a1": "COG0abc"})
    protein_cache.store(db, faa, pre, "cog", {}, genome="A")
    faa, pre = _genome(tmp_path, "B", [("b9", "MKVLAAG")], hits={"b9": "COG0abd"})
    # The split served it: novel.faa does not hold it, so this run did not compute it.
    assert protein_cache.split(db, faa, pre, "B", ["cog"], {}) == {"cog": (1, 0)}
    assert protein_cache.store(db, faa, pre, "cog", {}, genome="B") == 0
    assert "COG0abc" in _entry(db, "MKVLAAG")[0]


def test_a_tool_new_to_a_protein_is_added_and_the_others_stay(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    protein_cache.store(db, faa, pre, "cog", {}, genome="A")
    faa, pre = _genome(tmp_path, "B", [("b9", "MKVLAAG")], tool="kegg")
    assert protein_cache.store(db, faa, pre, "kegg", {}, genome="B") == 1
    assert _entry(db, "MKVLAAG", "cog") is not None and _entry(db, "MKVLAAG", "kegg") is not None


def test_entries_under_earlier_keys_move_to_the_settings_key(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    h = protein_cache.protein_hash("MKVLAAG")
    conn = protein_cache._connect(db)
    with conn:
        for key, at, hit in (("old-container", "2026-01-01", "COG0old"), ("newer-container", "2026-06-01", "COG0new")):
            conn.execute("INSERT INTO protein_cache VALUES (?, 'cog', ?, 'cog_results.tsv', ?, ?, 'A')",
                         (h, key, f"A\ta1\t{hit}\tx\ty", at))
    conn.close()
    protein_cache._carried.clear()
    assert protein_cache.split(db, faa, pre, "A", ["cog"], {}) == {"cog": (1, 0)}
    rows = sqlite3.connect(db).execute("SELECT tool_key, lines FROM protein_cache WHERE aa_hash = ?", (h,)).fetchall()
    assert rows == [(protein_cache.tool_key("cog", {}), "A\ta1\tCOG0new\tx\ty")]


def test_a_genomes_proteins_and_genes_are_linked_to_its_hash(tmp_path):
    db = str(tmp_path / "margie.db")
    faa_a, _ = _genome(tmp_path, "A", [("a1", "MKVLAAG"), ("a2", "MSTQRRW")])
    faa_b, _ = _genome(tmp_path, "B", [("b1", "MKVLAAG"), ("b2", "MSTQRRW")])
    faa_c, _ = _genome(tmp_path, "C", [("c1", "MKVLAAG")])
    assert protein_cache.link_genome(db, faa_a, "hashA", "A", {"a1": "gene1", "a2": "gene2"}) == 2
    protein_cache.link_genome(db, faa_b, "hashB", "B")
    protein_cache.link_genome(db, faa_c, "hashC", "C")
    conn = sqlite3.connect(db)
    shared = protein_cache.protein_hash("MKVLAAG")
    assert sorted(r[0] for r in conn.execute("SELECT genome_hash FROM protein_genomes WHERE aa_hash = ?", (shared,))) == ["hashA", "hashB", "hashC"]
    sets = dict(conn.execute("SELECT genome_hash, protein_set FROM genome_proteomes"))
    assert sets["hashA"] == sets["hashB"] != sets["hashC"]
    assert conn.execute("SELECT aa_hash FROM genome_genes WHERE genome_hash = 'hashA' AND gene_hash = 'gene1'").fetchone() == (shared,)


def test_each_gene_gets_its_fingerprint(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, _ = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    protein_cache.link_genome(db, faa, "hashA", "A", {"a1": "gene1"})
    table = tmp_path / "hash-label.tsv"
    table.write_text("feature_id\tfingerprint\na1\tpattern hash: de5259bf240c0f63 || label: MioC\n")
    assert protein_cache.record_fingerprints(db, "hashA", str(table), {"a1": "gene1"}) == 1
    assert sqlite3.connect(db).execute("SELECT fingerprint FROM genome_genes WHERE gene_hash = 'gene1'").fetchone() == ("de5259bf240c0f63",)


def test_each_protein_has_one_fingerprint_replaced_when_it_differs(tmp_path):
    db = str(tmp_path / "margie.db")
    faa_a, _ = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    faa_b, _ = _genome(tmp_path, "B", [("b1", "MKVLAAG")])
    protein_cache.link_genome(db, faa_a, "hashA", "A", {"a1": "geneA"})
    protein_cache.link_genome(db, faa_b, "hashB", "B", {"b1": "geneB"})
    h = protein_cache.protein_hash("MKVLAAG")
    for name, fid, genome, fp, label in (("a", "a1", "hashA", "1111aaaa2222bbbb", "MioC"), ("b", "b1", "hashB", "1111aaaa2222bbbb", "MioC"),
                                         ("c", "b1", "hashB", "3333cccc4444dddd", "MioC flavodoxin")):
        table = tmp_path / f"hash-label-{name}.tsv"
        table.write_text(f"feature_id\tfingerprint\n{fid}\tpattern hash: {fp} || label: {label}\n")
        protein_cache.record_fingerprints(db, genome, str(table), {fid: "geneA" if genome == "hashA" else "geneB"})
        row = sqlite3.connect(db).execute("SELECT fingerprint, label FROM protein_fingerprints WHERE aa_hash = ?", (h,)).fetchone()
        assert row == (fp, label)
