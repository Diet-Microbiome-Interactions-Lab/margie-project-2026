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


def _turns(monkeypatch, *modules):
    """Counts the write turns taken through these modules' db_turn, and whether one was held each time."""
    taken = []
    real_turn = db_turn.turn

    def turn(db_path, wait=None):
        taken.append(wait)
        return real_turn(db_path, wait=wait)

    for module in modules:
        monkeypatch.setattr(module.db_turn, 'turn', turn)
    return taken


def test_the_run_s_cache_writes_take_the_turn_for_a_while_at_most(tmp_path, monkeypatch):
    """The run's own writes wait CONTROLLER_WAIT for the turn at most, and take it only to write."""
    assert db_turn.CONTROLLER_WAIT == 600.0
    db = str(tmp_path / 'main.db')
    fasta = tmp_path / 'g.fa'
    fasta.write_text('>c1\nACGTACGT\n')
    out = tmp_path / 'cog_results.tsv'
    out.write_text('feature_id\tCOG_id\na1\tCOG1\n')
    taken = _turns(monkeypatch, output_cache)
    output_cache.store(db, str(fasta), 'cog', [str(out)])
    assert taken == [db_turn.CONTROLLER_WAIT]


def test_a_file_cached_as_it_is_writes_nothing(tmp_path, monkeypatch):
    """A genome stored again (a resumed or repeated run) leaves the cache as it is, without the
    turn; a file that changed is written again."""
    db = str(tmp_path / 'main.db')
    fasta = tmp_path / 'g.fa'
    fasta.write_text('>c1\nACGTACGT\n')
    out = tmp_path / 'cog_results.tsv'
    out.write_text('feature_id\tCOG_id\na1\tCOG1\n')
    output_cache.store(db, str(fasta), 'cog', [str(out)])
    taken = _turns(monkeypatch, output_cache)
    output_cache.store(db, str(fasta), 'cog', [str(out)])
    assert taken == []
    out.write_text('feature_id\tCOG_id\na1\tCOG2\n')
    output_cache.store(db, str(fasta), 'cog', [str(out)])
    assert len(taken) == 1
    assert output_cache.restore(db, str(fasta), 'cog', [str(tmp_path / 'back' / 'cog_results.tsv')])
    assert (tmp_path / 'back' / 'cog_results.tsv').read_text().endswith('COG2\n')


def _protein_genome(tmp_path, name='A'):
    faa = tmp_path / f'{name}.faa'
    faa.write_text('>a1 p\nMKVLAAG\n>a2 p\nMSTNPKP\n')
    folder = tmp_path / name
    (folder / 'labeling').mkdir(parents=True)
    core = protein_cache.CORE_TOOLS
    head = ['feature_id', 'aa_seq'] + [f'{t}_{k}' for t in core for k in ('all_ids', 'all_descriptions')]
    rows = [['a1', 'MKVLAAG'] + [v for t in core for v in (f'{t}1', f'{t} one')],
            ['a2', 'MSTNPKP'] + [v for t in core for v in (f'{t}2', f'{t} two')]]
    (folder / 'labeling' / 'labeled-genes.tsv').write_text('\n'.join('\t'.join(r) for r in [head] + rows) + '\n')
    table = folder / 'hash-label.tsv'
    table.write_text('feature_id\tfingerprint\na1\tpattern hash: 1111aaaa || label: MioC\na2\tpattern hash: 2222bbbb || label: FldA\n')
    return str(faa), f'{folder}/', str(table)


def test_a_genome_recorded_before_takes_no_turn(tmp_path, monkeypatch):
    """Linking, fingerprints and protein records read first and write what differs: a genome done
    before (a copied genome in a resumed run) writes nothing and leaves the turn to the loads."""
    db = str(tmp_path / 'main.db')
    faa, prefix, table = _protein_genome(tmp_path)
    genes = {'a1': 'gene1', 'a2': 'gene2'}

    def record():
        protein_cache.link_genome(db, faa, 'hashA', 'A', genes)
        protein_cache.record_fingerprints(db, 'hashA', table, genes)
        protein_cache.record_proteins(db, f'{prefix}labeling/labeled-genes.tsv', prefix, 'hashA')

    record()
    import sqlite3
    before = [sqlite3.connect(db).execute(f'SELECT * FROM {t} ORDER BY 1, 2').fetchall()
              for t in ('protein_genomes', 'genome_genes', 'protein_fingerprints', 'protein_descriptors')]
    taken = _turns(monkeypatch, protein_cache)
    record()
    assert taken == []
    after = [sqlite3.connect(db).execute(f'SELECT * FROM {t} ORDER BY 1, 2').fetchall()
             for t in ('protein_genomes', 'genome_genes', 'protein_fingerprints', 'protein_descriptors')]
    assert after == before


def test_a_shared_protein_s_fingerprints_follow_its_record_in_the_turn(tmp_path, monkeypatch):
    """Another genome can add to a shared protein's record between the read and the write: the
    fingerprints written are made from the record as it stands in the turn."""
    import sqlite3
    db = str(tmp_path / 'main.db')
    faa, prefix, _ = _protein_genome(tmp_path)
    labeled = f'{prefix}labeling/labeled-genes.tsv'
    protein_cache.record_proteins(db, labeled, prefix)
    # Genome B gives MKVLAAG a TCDB answer while A, whose PFAM answer changed, records again.
    (tmp_path / 'B' / 'labeling').mkdir(parents=True)
    (tmp_path / 'B' / 'labeling' / 'labeled-genes.tsv').write_text(
        'feature_id\taa_seq\tTCDB_all_ids\tTCDB_all_descriptions\nb1\tMKVLAAG\t2.A.1\tMFS\n')
    text = Path(labeled).read_text()
    Path(labeled).write_text(text.replace('PFAM1\tPFAM one', 'PFAM7\tPFAM seven'))
    real_turn = db_turn.turn
    ran = []

    def turn(db_path, wait=None):
        if not ran:
            ran.append(1)
            with real_turn(db_path, wait=wait):
                protein_cache.record_proteins(db, str(tmp_path / 'B' / 'labeling' / 'labeled-genes.tsv'), f'{tmp_path / "B"}/')
        return real_turn(db_path, wait=wait)

    monkeypatch.setattr(protein_cache.db_turn, 'turn', turn)
    protein_cache.record_proteins(db, labeled, prefix)
    assert ran
    conn = sqlite3.connect(db)
    h = protein_cache.protein_hash('MKVLAAG')
    have = dict(conn.execute('SELECT tool, value FROM protein_descriptors WHERE aa_hash = ?', (h,)))
    assert have['TCDB'] == '2.A.1 — MFS' and have['PFAM'] == 'PFAM7 — PFAM seven'
    core, extra = conn.execute('SELECT core_fingerprint, extra_fingerprint FROM protein_fingerprints WHERE aa_hash = ?', (h,)).fetchone()
    assert (core, extra) == protein_cache._prints(have) and extra


def test_a_load_reads_its_file_before_the_turn(tmp_path, monkeypatch):
    """The loader hashes, checks and parses its file outside the turn; the turn holds the delete,
    the insert and the record of the load. A file loaded already takes no turn."""
    from bioinformatics_tools.workflow_tools import load_to_db
    db = str(tmp_path / 'main.db')
    tsv = tmp_path / 'cog.tsv'
    tsv.write_text('feature_id\tcog\ng1\tCOG1\n')
    fasta = tmp_path / 'g.fa'
    fasta.write_text('>c1\nACGTACGT\n')
    path = db_turn.turn_path(db)
    held_while = {}
    real_read = load_to_db._read_csv

    def read(*args, **kwargs):
        held_while['reading'] = path in db_turn._held
        return real_read(*args, **kwargs)

    monkeypatch.setattr(load_to_db, '_read_csv', read)
    taken = _turns(monkeypatch, load_to_db)
    argv = ['load_to_db.py', 'tsv', str(tsv), db, 'cog', '--fasta', str(fasta), '--delete-organism', 'G',
            '--token', str(tmp_path / 'cog_db.tkn')]
    monkeypatch.setattr(sys, 'argv', argv)
    load_to_db.main()
    assert held_while == {'reading': False} and len(taken) == 1
    load_to_db.main()
    assert len(taken) == 1  # already loaded: no turn


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


def test_two_threads_of_a_process_take_turns(tmp_path):
    import threading
    db = tmp_path / 'main.db'
    inside, order = threading.Event(), []

    def first():
        with db_turn.turn(db):
            inside.set()
            time.sleep(0.5)
            order.append('first done')

    t = threading.Thread(target=first)
    t.start()
    inside.wait(5)
    with db_turn.turn(db, wait=0.1) as had:
        assert not had
    with db_turn.turn(db) as had:
        assert had
        order.append('second')
    t.join()
    assert order == ['first done', 'second']


def test_the_protein_cache_lets_others_write_between_its_chunks(tmp_path, monkeypatch):
    import threading
    monkeypatch.setattr(protein_cache, 'STORE_CHUNK', 2)
    monkeypatch.setattr(protein_cache, 'STORE_PAUSE', 0.2)
    db = tmp_path / 'main.db'
    seqs = ['MKVLAAG', 'MSTNPKP', 'MAAAKKL', 'MPPQQRS', 'MGGHHLL', 'MDDEEFF']
    faa = tmp_path / 'A.faa'
    faa.write_text(''.join(f'>a{i} p\n{q}\n' for i, q in enumerate(seqs)))
    (tmp_path / 'A' / 'cog').mkdir(parents=True)
    (tmp_path / 'A' / 'cog' / 'cog_results.tsv').write_text(
        'organism_name\tfeature_id\tCOG_id\n' + ''.join(f'A\ta{i}\tCOG000{i}\n' for i in range(len(seqs))))
    got_in = []

    def other_writer():
        time.sleep(0.1)
        with db_turn.turn(db, wait=5) as had:
            got_in.append(had)

    t = threading.Thread(target=other_writer)
    t.start()
    assert protein_cache.store(str(db), str(faa), f'{tmp_path / "A"}/', 'cog', {}, genome='A') == len(seqs)
    t.join()
    assert got_in == [True]


def test_the_run_writes_on_a_thread_and_waits_for_the_writes_before_it_ends():
    """The run's caches and a finished genome's records go to the writes' thread, so the controller
    goes on with the other genomes meanwhile; the run waits for them before Stage 3."""
    src = (Path(db_turn.__file__).parent / 'workflow.py').read_text()
    ready = src[src.index('def _store_ready(slot'):src.index('def _record(slot')]
    assert 'db_work.put(' in ready and 'protein_cache.store(' not in ready and '_safely(' not in ready
    finish = src[src.index('def _finish(slot'):src.index('def _cache_gtdbtk(')]
    assert 'db_work.put(lambda: _record(slot' in finish and 'record_proteins' not in finish
    loop_end = src.index('_requests_open(False)\n')
    assert src.index('db_work.join()', loop_end) < src.index("target='llm_all'", loop_end)
    assert "threading.Thread(target=_write" in src
