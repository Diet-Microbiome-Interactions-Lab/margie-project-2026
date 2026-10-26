"""Each genome runs as <name>--<the first 8 characters of its hash> (workflow.named_with_hash: a folder
of links the run reads, the files as they are), keeping its own settings, so genomes that share a
file name stay apart. workflow.name_clashes, a check kept behind it, finds a name another genome
(other DNA) has in the MARGIE database; the same genome, or its file saved again, is not one."""

import json
import sqlite3

from bioinformatics_tools.workflow_tools.load_to_db import fasta_hashes
from bioinformatics_tools.workflow_tools.workflow import name_clashes, name_with_hash, named_with_hash
from bioinformatics_tools.workflow_tools.workflow_helpers import discover_genomes, genome_calls


def _db(tmp_path, logged=(), linked=()):
    path = tmp_path / "margie.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE run_log (id INTEGER PRIMARY KEY, organism_name TEXT, fasta_hash TEXT)")
    conn.execute("CREATE TABLE genome_proteomes (genome_hash TEXT PRIMARY KEY, names TEXT)")
    conn.executemany("INSERT INTO run_log (organism_name, fasta_hash) VALUES (?, ?)", logged)
    conn.executemany("INSERT INTO genome_proteomes VALUES (?, ?)", [(h, json.dumps(n)) for h, n in linked])
    conn.commit()
    return str(path)


def _fasta(tmp_path, name, seq, width=60):
    path = tmp_path / f"{name}.fna"
    path.write_text(">c1\n" + "\n".join(seq[i:i + width] for i in range(0, len(seq), width)) + "\n")
    return str(path)


def test_another_genome_under_the_name_stops_the_run(tmp_path):
    old = _fasta(tmp_path / "", "old", "ACGT" * 50)
    db = _db(tmp_path, logged=[("coli", fasta_hashes(old)[0])])
    new = _fasta(tmp_path, "coli", "TTGA" * 50)
    assert name_clashes(db, {"coli": new}) == ["coli"]


def test_the_same_genome_goes_on_even_saved_again(tmp_path):
    seq = "ACGT" * 50
    first = _fasta(tmp_path, "first", seq)
    db = _db(tmp_path, logged=[("coli", fasta_hashes(first)[1])], linked=[(fasta_hashes(first)[0], ["coli"])])
    again = _fasta(tmp_path, "coli", seq, width=70)
    assert name_clashes(db, {"coli": again}) == []


def test_a_name_seen_only_with_its_proteins_is_checked_too(tmp_path):
    db = _db(tmp_path, linked=[("someone-else", ["dorei"])])
    assert name_clashes(db, {"dorei": _fasta(tmp_path, "dorei", "GGCC" * 40)}) == ["dorei"]
    assert name_clashes(db, {"new": _fasta(tmp_path, "new", "GGCC" * 40)}) == []


def test_each_genome_runs_under_its_name_and_hash_with_its_settings(tmp_path):
    inputs = tmp_path / "in"
    inputs.mkdir()
    coli, dorei = _fasta(inputs, "coli", "TTGA" * 50), _fasta(inputs, "dorei", "GGCC" * 40)
    folder = named_with_hash({"coli": coli, "dorei": dorei}, str(tmp_path / "run" / ".margie-input"))
    genomes = discover_genomes(folder)
    named = {f"coli--{fasta_hashes(coli)[0][:8]}", f"dorei--{fasta_hashes(dorei)[0][:8]}"}
    assert set(genomes) == named
    renamed = f"coli--{fasta_hashes(coli)[0][:8]}"
    assert open(genomes[renamed]).read() == open(coli).read()
    # Its settings in config.yaml stay with it, by its file's name.
    config = {"margie_sb": {"genome_info": {"coli.fna": {"domain": "Archaea", "genetic_code": "11"}}}}
    assert genome_calls({renamed: genomes[renamed]}, config)[renamed]["domain"].lower().startswith("arch")


def test_a_name_that_already_carries_its_hash_keeps_it(tmp_path):
    coli = _fasta(tmp_path, "coli", "TTGA" * 50)
    named = name_with_hash("coli", coli)
    assert name_with_hash(named, coli) == named
    # Another genome's hash on the name is replaced by this genome's.
    assert name_with_hash("coli--0000aaaa", coli) == named
