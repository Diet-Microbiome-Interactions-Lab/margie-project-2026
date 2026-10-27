"""The protein cache keeps its rows when a tool's columns change (a new container): merge.sh lays
cached rows out under the new header by column name, and store() moves the cached rows to the new
header and replaces it, so rows never sit under another layout's columns."""

import sqlite3
import subprocess

from bioinformatics_tools.workflow_tools import protein_cache


def _merge(tmp_path, produced: str, cached: str) -> str:
    pc = tmp_path / 'pc'
    (pc / 'cached').mkdir(parents=True)
    (tmp_path / 'out.tsv').write_text(produced)
    (pc / 'cached' / 'out.tsv').write_text(cached)
    script = tmp_path / 'merge.sh'
    script.write_text(protein_cache.MERGE_SH)
    dest = tmp_path / 'dest.tsv'
    subprocess.run(['sh', str(script), str(tmp_path / 'out.tsv'), str(dest), str(pc), 'out.tsv', 'tsv'], check=True)
    return dest.read_text()


def test_cached_rows_follow_the_tools_new_columns(tmp_path):
    out = _merge(tmp_path, 'feature_id\tA\tB\ng1\ta1\tb1\n', 'feature_id\tB\tC\ng2\tb2\tc2\n')
    assert out == 'feature_id\tA\tB\ng1\ta1\tb1\ng2\t\tb2\n'
    assert not (tmp_path / 'dest.tsv.header').exists()


def test_cached_rows_under_the_same_columns_are_appended(tmp_path):
    out = _merge(tmp_path, 'feature_id\tA\ng1\ta1\n', 'feature_id\tA\ng2\ta2\n')
    assert out == 'feature_id\tA\ng1\ta1\ng2\ta2\n'


def test_stored_rows_move_to_a_new_header():
    conn = sqlite3.connect(':memory:')
    conn.executescript(protein_cache.CREATE_SQL)
    cols = {r[1] for r in conn.execute('PRAGMA table_info(protein_cache)')}
    extra = ', genome' if 'genome' in cols else ''
    conn.execute(f'INSERT INTO protein_cache (aa_hash, tool, tool_key, filename, lines, cached_at{extra}) '
                 f'VALUES (?, ?, ?, ?, ?, ?{", ?" if extra else ""})',
                 ('h1', 'pfam', 'k', 'pfam_results.tsv', 'g1\tx1\ty1\ng1\tx2\ty2', 'now', *(['gA'] if extra else [])))
    assert protein_cache._reheader(conn, 'pfam', 'k', 'pfam_results.tsv', 'feature_id\tX\tY', 'feature_id\tY\tZ') == 1
    lines = conn.execute('SELECT lines FROM protein_cache WHERE aa_hash = ?', ('h1',)).fetchone()[0]
    assert lines == 'g1\ty1\t\ng1\ty2\t'
