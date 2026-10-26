"""A genome's name stands for it in the database's tables (workflow.name_clashes): a run whose genome
has a name another genome (other DNA) already has there stops before anything is loaded; the same
genome under its name, or its file saved again with other line lengths, goes on."""

import json
import sqlite3

from bioinformatics_tools.workflow_tools.load_to_db import fasta_hashes
from bioinformatics_tools.workflow_tools.workflow import name_clashes


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
    assert name_clashes(db, {"coli": new}) == ["coli (coli.fna)"]


def test_the_same_genome_goes_on_even_saved_again(tmp_path):
    seq = "ACGT" * 50
    first = _fasta(tmp_path, "first", seq)
    db = _db(tmp_path, logged=[("coli", fasta_hashes(first)[1])], linked=[(fasta_hashes(first)[0], ["coli"])])
    again = _fasta(tmp_path, "coli", seq, width=70)
    assert name_clashes(db, {"coli": again}) == []


def test_a_name_seen_only_with_its_proteins_is_checked_too(tmp_path):
    db = _db(tmp_path, linked=[("someone-else", ["dorei"])])
    assert name_clashes(db, {"dorei": _fasta(tmp_path, "dorei", "GGCC" * 40)}) == ["dorei (dorei.fna)"]
    assert name_clashes(db, {"new": _fasta(tmp_path, "new", "GGCC" * 40)}) == []
