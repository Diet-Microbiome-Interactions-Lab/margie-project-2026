"""Genes by hash in the genome cache (output_cache): a cached table names each gene by a hash of its
contig, start, end, strand and protein, and comes back under the gene ids of the run restoring it,
however a submission numbered them. A gene the run's gene calls lack makes it a miss."""

from bioinformatics_tools.workflow_tools.output_cache import gene_hashes, restore, store

GENES = [("c1", 10, 90, "+", "MKVLAAG"), ("c1", 200, 410, "-", "MSTQRRW"), ("c2", 5, 300, "+", "MPPPLLK")]


def _calls(tmp_path, job, order):
    """RASTtk gene calls under submission `job`, numbering GENES in `order`."""
    folder = tmp_path / f"calls-{job}"
    folder.mkdir()
    gff, faa = [], []
    for n, k in enumerate(order, 1):
        contig, start, end, strand, seq = GENES[k]
        fid = f"fig|6666666.{job}.peg.{n}"
        gff.append(f"{contig}\tRAST\tCDS\t{start}\t{end}\t.\t{strand}\t0\tID={fid};Name=x\n")
        faa.append(f">{fid}\n{seq}\n")
    (folder / "rast.gff").write_text("##gff-version 3\n" + "".join(gff))
    (folder / "rast.faa").write_text("".join(faa))
    return gene_hashes(str(folder / "rast.gff"), str(folder / "rast.faa"))


def _genome(tmp_path):
    fasta = tmp_path / "g.fna"
    fasta.write_text(">c1\nACGTACGTAAACCCGGGTTT\n")
    return str(fasta)


def test_a_gene_keeps_its_hash_under_any_numbering(tmp_path):
    first, second = _calls(tmp_path, 111, [0, 1, 2]), _calls(tmp_path, 222, [2, 0, 1])
    assert len(first) == 3 and set(first.values()) == set(second.values())
    assert first["fig|6666666.111.peg.1"] == second["fig|6666666.222.peg.2"]


def test_a_table_comes_back_under_the_restoring_runs_gene_ids(tmp_path):
    db, fasta = str(tmp_path / "margie.db"), _genome(tmp_path)
    then, now = _calls(tmp_path, 111, [0, 1, 2]), _calls(tmp_path, 222, [2, 0, 1])
    table = tmp_path / "cog_results.tsv"
    table.write_text("feature_id\tcog\nfig|6666666.111.peg.1\tCOG1\nfig|6666666.111.peg.3\tCOG3\n")
    store(db, fasta, "cog", [str(table)], genes=then)
    out = tmp_path / "run" / "cog_results.tsv"
    assert restore(db, fasta, "cog", [str(out)], genes=now)
    assert out.read_text() == "feature_id\tcog\nfig|6666666.222.peg.2\tCOG1\nfig|6666666.222.peg.1\tCOG3\n"


def test_a_gene_the_run_lacks_makes_it_a_miss(tmp_path):
    db, fasta = str(tmp_path / "margie.db"), _genome(tmp_path)
    then = _calls(tmp_path, 111, [0, 1, 2])
    table = tmp_path / "cog_results.tsv"
    table.write_text("feature_id\tcog\nfig|6666666.111.peg.3\tCOG3\n")
    store(db, fasta, "cog", [str(table)], genes=then)
    fewer = {fid: h for fid, h in then.items() if not fid.endswith(".peg.3")}
    out = tmp_path / "run" / "cog_results.tsv"
    assert not restore(db, fasta, "cog", [str(out)], genes=fewer)
    assert not out.exists()


def test_a_table_naming_a_gene_outside_the_calls_is_stored_as_it_is(tmp_path):
    db, fasta = str(tmp_path / "margie.db"), _genome(tmp_path)
    then = _calls(tmp_path, 111, [0, 1, 2])
    table = tmp_path / "cog_results.tsv"
    table.write_text("feature_id\tcog\nfig|6666666.111.peg.9\tCOG9\n")
    store(db, fasta, "cog", [str(table)], genes=then)
    out = tmp_path / "run" / "cog_results.tsv"
    assert restore(db, fasta, "cog", [str(out)], genes=then)
    assert "fig|6666666.111.peg.9" in out.read_text()
