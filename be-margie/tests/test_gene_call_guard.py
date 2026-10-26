"""The gene-call guard (output_cache.gene_calls_match): a genome's cached tables move onto a new
RASTtk submission's id only when the cached gene calls under their id hold the same protein under
each feature number as the new calls; a renumbered submission sends the tools to run again."""

from bioinformatics_tools.workflow_tools.output_cache import gene_calls_match, rast_genome_ids, store

PROTEINS = ["MKVLA", "MATTQ", "MLLRSG"]


def _faa(path, gid, proteins):
    path.write_text("".join(f">fig|6666666.{gid}.peg.{i + 1} protein {i + 1}\n{p}\n" for i, p in enumerate(proteins)))
    return str(path)


def _cached(tmp_path, gid, proteins):
    """A database holding the genome's gene calls under RASTtk id 6666666.<gid>."""
    fasta = tmp_path / "g.fna"
    fasta.write_text(">c1\nACGTACGTAAACCCGGGTTT\n")
    folder = tmp_path / "cached"
    folder.mkdir()
    db = str(tmp_path / "margie.db")
    store(db, str(fasta), "rasttk", [_faa(folder / "rast.faa", gid, proteins)])
    return db, str(fasta)


def test_the_same_proteins_under_each_number_match(tmp_path):
    db, fasta = _cached(tmp_path, 111, PROTEINS)
    assert gene_calls_match(db, fasta, _faa(tmp_path / "now.faa", 222, PROTEINS), "111") is True


def test_renumbered_gene_calls_do_not_match(tmp_path):
    db, fasta = _cached(tmp_path, 111, PROTEINS)
    assert gene_calls_match(db, fasta, _faa(tmp_path / "now.faa", 222, PROTEINS[::-1]), "111") is False


def test_a_gene_more_or_less_does_not_match(tmp_path):
    db, fasta = _cached(tmp_path, 111, PROTEINS)
    assert gene_calls_match(db, fasta, _faa(tmp_path / "now.faa", 222, PROTEINS[:2]), "111") is False


def test_gene_calls_cached_under_another_id_give_no_answer(tmp_path):
    db, fasta = _cached(tmp_path, 111, PROTEINS)
    assert gene_calls_match(db, fasta, _faa(tmp_path / "now.faa", 222, PROTEINS), "333") is None


def test_the_ids_a_table_names(tmp_path):
    table = tmp_path / "cog.tsv"
    table.write_text("feature_id\tcog\nfig|6666666.111.peg.1\tCOG1\nfig|6666666.111.peg.2\tCOG2\n")
    assert rast_genome_ids([str(table), str(tmp_path / "missing.tsv")]) == {"111"}
