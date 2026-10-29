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
    # Pfam's answer depends on no setting, so entries made under an earlier key (schema 1 named the
    # container and database files) move under the current one, the newest first.
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    h = protein_cache.protein_hash("MKVLAAG")
    conn = protein_cache._connect(db)
    with conn:
        for key, at, hit in (("old-container", "2026-01-01", "PF0old"), ("newer-container", "2026-06-01", "PF0new")):
            conn.execute("INSERT INTO protein_cache VALUES (?, 'pfam', ?, 'pfam_results.tsv', ?, ?, 'A')",
                         (h, key, f"A\ta1\t{hit}\tx\ty", at))
    conn.close()
    protein_cache._carried.clear()
    assert protein_cache.split(db, faa, pre, "A", ["pfam"], {}) == {"pfam": (1, 0)}
    rows = sqlite3.connect(db).execute("SELECT tool_key, lines FROM protein_cache WHERE aa_hash = ?", (h,)).fetchall()
    assert rows == [(protein_cache.tool_key("pfam", {}), "A\ta1\tPF0new\tx\ty")]


def test_entries_under_other_settings_stay_apart(tmp_path):
    # COG's answer depends on its E-value: entries made under another key are not reused.
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    h = protein_cache.protein_hash("MKVLAAG")
    conn = protein_cache._connect(db)
    with conn:
        conn.execute("INSERT INTO protein_cache VALUES (?, 'cog', 'evalue-1e-5', 'cog_results.tsv', ?, '2026-06-01', 'A')",
                     (h, "A\ta1\tCOG0old\tx\ty"))
    conn.close()
    protein_cache._carried.clear()
    assert protein_cache.split(db, faa, pre, "A", ["cog"], {}) == {"cog": (0, 1)}
    keys = [r[0] for r in sqlite3.connect(db).execute("SELECT tool_key FROM protein_cache WHERE aa_hash = ?", (h,))]
    assert keys == ["evalue-1e-5"]


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


def _labeled(tmp_path, name, rows, localization=None):
    """A genome folder with labeled-genes.tsv: (feature id, sequence, {TOOL: (ids, descriptions)})."""
    folder = tmp_path / name
    (folder / "labeling").mkdir(parents=True)
    tools = sorted({tool for _, _, hits in rows for tool in hits})
    head = ["feature_id", "aa_seq"] + [f"{tl}_{k}" for tl in tools for k in ("all_ids", "all_descriptions")]
    lines = ["\t".join(head)] + ["\t".join([fid, seq] + [v for tl in tools for v in hits.get(tl, ("", ""))]) for fid, seq, hits in rows]
    (folder / "labeling" / "labeled-genes.tsv").write_text("\n".join(lines) + "\n")
    for tool, text in (localization or {}).items():
        (folder / tool).mkdir()
        (folder / tool / f"{tool}_results.tsv").write_text(text)
    return str(folder / "labeling" / "labeled-genes.tsv"), f"{folder}/"


CORE = {t: (f"{t}1", f"{t} one") for t in protein_cache.CORE_TOOLS}


def _record(db, seq):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return dict(conn.execute("SELECT * FROM protein_records WHERE protein_hash = ?", (protein_cache.protein_hash(seq),)).fetchone())


def test_a_protein_record_reads_core_tools_then_additional_ones(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, _ = _genome(tmp_path, "A", [("a1", "MKVLAAG")])
    protein_cache.link_genome(db, faa, "hashA", "A")
    psortb = "feature_id\tPSORTB_localization\tPSORTB_gram_class\na1\tCytoplasmic\tnegative\n"
    labeled, prefix = _labeled(tmp_path, "GA", [("a1", "MKVLAAG", {**CORE, "DBCAN": ("GH13", "alpha-amylase")})], {"psortb": psortb})
    assert protein_cache.record_proteins(db, labeled, prefix, "hashA") == 1
    rec = _record(db, "MKVLAAG")
    assert rec["genomes"] == 1 and rec["genome_hashes"] == "hashA"
    assert rec["cog"] == "COG1 — COG one" and rec["pgap"] == "PGAP1 — PGAP one"
    assert rec["additional"] == "DBCAN: GH13 — alpha-amylase"
    assert rec["core_fingerprint"] and rec["extra_fingerprint"]
    # PSORTb depends on the genome too: kept by genome hash and protein hash.
    assert sqlite3.connect(db).execute("SELECT genome_hash, tool, value FROM genome_protein_descriptors").fetchall() == [
        ("hashA", "PSORTB", "Cytoplasmic (negative)")]


def test_a_new_tool_changes_only_the_additional_fingerprint(tmp_path):
    db = str(tmp_path / "margie.db")
    labeled, prefix = _labeled(tmp_path, "GA", [("a1", "MKVLAAG", CORE)])
    protein_cache.record_proteins(db, labeled, prefix)
    first = _record(db, "MKVLAAG")
    labeled, prefix = _labeled(tmp_path, "GB", [("b1", "MKVLAAG", {**CORE, "TCDB": ("2.A.1", "MFS")})])
    protein_cache.record_proteins(db, labeled, prefix)
    second = _record(db, "MKVLAAG")
    assert second["core_fingerprint"] == first["core_fingerprint"]
    assert second["extra_fingerprint"] != first["extra_fingerprint"] and second["additional"] == "TCDB: 2.A.1 — MFS"


def test_a_different_core_descriptor_replaces_and_moves_the_core_fingerprint(tmp_path):
    db = str(tmp_path / "margie.db")
    labeled, prefix = _labeled(tmp_path, "GA", [("a1", "MKVLAAG", CORE)])
    protein_cache.record_proteins(db, labeled, prefix)
    first = _record(db, "MKVLAAG")
    labeled, prefix = _labeled(tmp_path, "GB", [("b1", "MKVLAAG", {**CORE, "COG": ("COG2", "COG two")})])
    protein_cache.record_proteins(db, labeled, prefix)
    second = _record(db, "MKVLAAG")
    assert second["cog"] == "COG2 — COG two" and second["core_fingerprint"] != first["core_fingerprint"]


def test_a_tool_restored_from_the_cache_adds_nothing(tmp_path):
    db = str(tmp_path / "margie.db")
    faa, pre = _genome(tmp_path, "A", [("a1", "MKVLAAG")], hits={"a1": "COG0abc"})
    protein_cache.store(db, faa, pre, "cog", {}, genome="A")
    # The genome's results came back from the MARGIE database: the cache stays as it is.
    faa, pre = _genome(tmp_path, "B", [("b9", "MKVLAAG"), ("b10", "MSTNPKP")], hits={"b9": "COG0abd"})
    assert protein_cache.store(db, faa, pre, "cog", {}, genome="B", ran=False) == 0
    lines, _, genome = _entry(db, "MKVLAAG")
    assert "COG0abc" in lines and genome == "A"
    assert _entry(db, "MSTNPKP") is None
