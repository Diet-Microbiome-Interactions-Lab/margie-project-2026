"""A genome loaded again replaces its earlier rows (load_to_db --delete-organism): every per-genome
load rule passes it, and the gene calls' table, which names the genome in its organism column,
has its earlier rows removed as the tool tables do."""

import re
import sqlite3
from pathlib import Path

from bioinformatics_tools.workflow_tools.load_to_db import _delete_stale_organism_rows, load_csv_to_db

SMK = Path(__file__).resolve().parents[1] / "bioinformatics_tools" / "workflow_tools" / "margie_sb.smk"
RUN_WIDE = {"ani", "aai", "closest", "llm"}


def _load(db, tmp_path, table, col, genome, n):
    tsv = tmp_path / f"{table}-{genome}.tsv"
    tsv.write_text(f"{col}\tfeature_id\n" + "".join(f"{genome}\tfig|6666666.1.peg.{i}\n" for i in range(n)))
    load_csv_to_db(str(tsv), db, table, delimiter="\t")


def _rows(db, table, col, genome):
    return sqlite3.connect(db).execute(f'SELECT count(*) FROM "{table}" WHERE "{col}" = ?', (genome,)).fetchone()[0]


def test_the_gene_calls_table_drops_a_genomes_earlier_rows(tmp_path):
    db = str(tmp_path / "margie.db")
    _load(db, tmp_path, "rasttk", "organism", "g1", 3)
    _load(db, tmp_path, "rasttk", "organism", "g2", 2)
    assert _delete_stale_organism_rows(db, "rasttk", "g1") == 3
    assert (_rows(db, "rasttk", "organism", "g1"), _rows(db, "rasttk", "organism", "g2")) == (0, 2)


def test_a_tool_table_drops_a_genomes_earlier_rows(tmp_path):
    db = str(tmp_path / "margie.db")
    _load(db, tmp_path, "cog", "organism_name", "g1", 4)
    assert _delete_stale_organism_rows(db, "cog", "g1") == 4


def test_each_per_genome_load_rule_replaces_the_genomes_rows():
    text = SMK.read_text()
    for name, body in re.findall(r"^rule (load_\w+)_to_db:(.*?)(?=^rule |^localrules|\Z)", text, re.S | re.M):
        tool = name[len("load_"):]
        if tool in RUN_WIDE:
            continue
        assert "--delete-organism" in body, f"{name}_to_db keeps a genome's earlier rows on a reload"
