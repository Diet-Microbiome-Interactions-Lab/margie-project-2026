"""The MARGIE database's write turn (db_turn): one writer at a time across processes, the loads
waiting for it (load_to_db) and the run's cache writes waiting a bounded time (output_cache,
protein_cache)."""

import subprocess
import sys
import time
from pathlib import Path

from bioinformatics_tools.workflow_tools import db_turn, output_cache, protein_cache

LOADER = Path(db_turn.__file__).with_name('load_to_db.py')

# Holds the turn of argv[1] until stdin closes; prints "held" once it has it.
_HOLDER = '''
import sys
from bioinformatics_tools.workflow_tools import db_turn
with db_turn.turn(sys.argv[1]) as had:
    print("held" if had else "missed", flush=True)
    sys.stdin.read()
'''


def _hold(db):
    proc = subprocess.Popen([sys.executable, '-c', _HOLDER, str(db)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == 'held'
    return proc


def _let_go(proc):
    proc.stdin.close()
    proc.wait(timeout=30)


def test_a_turn_held_elsewhere_is_waited_for(tmp_path, monkeypatch):
    monkeypatch.setattr(db_turn, 'POLL', 0.05)
    db = tmp_path / 'main.db'
    holder = _hold(db)
    try:
        with db_turn.turn(db, wait=0.3) as had:
            assert not had
    finally:
        _let_go(holder)
    with db_turn.turn(db, wait=5) as had:
        assert had
    assert Path(db_turn.turn_path(db)).exists()


def test_a_process_shares_its_turn_with_its_nested_writes(tmp_path):
    db = tmp_path / 'main.db'
    path = db_turn.turn_path(db)
    with db_turn.turn(db) as outer:
        with db_turn.turn(db, wait=0) as inner:
            assert outer and inner
            assert db_turn._held[path][1] == 2
        assert db_turn._held[path][1] == 1
    assert path not in db_turn._held


def test_a_load_waits_for_the_turn(tmp_path):
    db = tmp_path / 'main.db'
    tsv = tmp_path / 'cog.tsv'
    tsv.write_text('gene\tcog\ng1\tCOG1\n')
    token = tmp_path / 'cog_db.tkn'
    holder = _hold(db)
    try:
        load = subprocess.Popen([sys.executable, str(LOADER), 'tsv', str(tsv), str(db), 'cog', '--token', str(token)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(2.0)
        assert load.poll() is None and not token.exists()
    finally:
        _let_go(holder)
    out, err = load.communicate(timeout=60)
    assert load.returncode == 0, err
    assert token.read_text().startswith('1 rows loaded from cog')


def test_the_run_s_cache_writes_take_the_turn_for_a_while_at_most():
    for fn in (output_cache.store, output_cache.store_all, output_cache.log_workflow_run,
               protein_cache.link_genome, protein_cache.record_fingerprints, protein_cache.record_proteins):
        assert fn.__wrapped__, fn
    assert db_turn.CONTROLLER_WAIT == 600.0


def test_the_protein_cache_compares_without_the_turn_and_writes_in_it(tmp_path, monkeypatch):
    """protein_cache.store reads and compares a genome's proteins first, which can take minutes for a
    large genome; loads in other genomes and runs go on meanwhile, and only its writes wait their turn."""
    db = tmp_path / 'main.db'
    faa = tmp_path / 'A.faa'
    faa.write_text('>a1 p\nMKVLAAG\n')
    (tmp_path / 'A' / 'cog').mkdir(parents=True)
    (tmp_path / 'A' / 'cog' / 'cog_results.tsv').write_text(
        'organism_name\tfeature_id\tCOG_id\nA\ta1\tCOG0001\n')
    path = db_turn.turn_path(db)
    held_while = {}
    real_computed = protein_cache._computed_here

    def computed(prefix, tool, proteins):
        held_while['comparing'] = path in db_turn._held
        return real_computed(prefix, tool, proteins)

    monkeypatch.setattr(protein_cache, '_computed_here', computed)
    real_turn = db_turn.turn

    def turn(db_path, wait=None):
        held_while['writing'] = True
        return real_turn(db_path, wait=wait)

    monkeypatch.setattr(protein_cache.db_turn, 'turn', turn)
    assert protein_cache.store(str(db), str(faa), f'{tmp_path / "A"}/', 'cog', {}, genome='A') == 1
    assert held_while == {'comparing': False, 'writing': True}


def test_a_cache_write_runs_in_the_turn(tmp_path, monkeypatch):
    db = tmp_path / 'main.db'
    seen = []

    @db_turn.writes(wait=1)
    def write(db_path):
        seen.append(db_turn.turn_path(db_path) in db_turn._held)

    write(str(db))
    write('')
    assert seen == [True, False]
