"""A step that runs again for a genome at the same pipeline version reloads when its results
differ, replacing the genome's rows, and is skipped when the file is the same one loaded last."""

import csv
import sqlite3
import subprocess
import sys
from pathlib import Path

LOADER = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'load_to_db.py'


def _load(db: Path, rows: list[dict], fasta: Path, name: str) -> str:
    tsv = db.parent / name
    with tsv.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter='\t')
        w.writeheader()
        w.writerows(rows)
    r = subprocess.run([sys.executable, str(LOADER), 'tsv', str(tsv), str(db), 'labeling_labeled', '--fasta', str(fasta),
                        '--delete-organism', 'gA'], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _labels(db: Path) -> list[str]:
    conn = sqlite3.connect(db)
    try:
        return sorted(r[0] for r in conn.execute('SELECT label FROM labeling_labeled'))
    finally:
        conn.close()


def test_new_results_replace_the_rows_and_the_same_file_is_skipped(tmp_path):
    db, fasta = tmp_path / 'main.db', tmp_path / 'gA.fna'
    fasta.write_text('>c1\n' + 'ACGT' * 200 + '\n')
    first = [{'organism_name': 'gA', 'feature_id': 'f1', 'label': 'old label'}]
    second = [{'organism_name': 'gA', 'feature_id': 'f1', 'label': 'new label'},
              {'organism_name': 'gA', 'feature_id': 'f2', 'label': 'another'}]
    _load(db, first, fasta, 'a.tsv')
    assert _labels(db) == ['old label']
    # Labeling ran again with other tools: its rows replace the earlier ones.
    out = _load(db, second, fasta, 'b.tsv')
    assert 'Skipped' not in out and _labels(db) == ['another', 'new label']
    # The same file again: nothing to do.
    out = _load(db, second, fasta, 'c.tsv')
    assert out.startswith('Skipped') and _labels(db) == ['another', 'new label']
