"""The cache report's dates come from output_cache_when, never by reading the stored files:
cached_at sits after a file's content in output_cache, so reading it there walks every stored file."""

import sqlite3

from bioinformatics_tools.workflow_tools import output_cache as oc


def test_dates_are_kept_beside_the_files_and_read_from_there(tmp_path):
    fasta = tmp_path / "g.fna"
    fasta.write_text(">c1\nACGT\n")
    out = tmp_path / "cog.tsv"
    out.write_text("x\n")
    db = str(tmp_path / "m.db")
    oc.store(db, str(fasta), "cog", [str(out)])
    when = oc.cached_when(db, str(fasta))
    assert set(when) == {"cog"}
    row = sqlite3.connect(db).execute("SELECT tool, cached_at FROM output_cache_when").fetchall()
    assert row == [("cog", when["cog"])]


def test_files_cached_before_the_dates_table_have_no_date(tmp_path):
    fasta = tmp_path / "g.fna"
    fasta.write_text(">c1\nACGT\n")
    db = str(tmp_path / "m.db")
    c = sqlite3.connect(db)
    c.execute(oc.CREATE_OUTPUT_CACHE_SQL)
    c.execute("INSERT INTO output_cache (input_hash, tool, filename, content, size_bytes, cached_at) VALUES (?, 'kegg', 'k.tsv', x'00', 1, '2026-01-01')",
              (oc.genome_hash(str(fasta)),))
    c.commit()
    assert oc.cached_when(db, str(fasta)) == {}
