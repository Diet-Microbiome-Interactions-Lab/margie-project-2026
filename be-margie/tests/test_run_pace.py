"""The pace of a running annotation, read from its log (run_pace.py)."""
from bioinformatics_tools.api.services.run_pace import RunPace


def _feed(pace: RunPace, lines: list[str]) -> dict:
    for line in lines:
        pace.feed(line)
    return pace.snapshot()


def test_the_writer_s_genome_waiting_genomes_and_time_left_follow_the_log():
    pace = RunPace()
    snap = _feed(pace, [
        '[23:00:00 INFO w] - === STAGE 2: genome 1/4 (gA--fa1:aaaaaaaa) phase4-12 starting, up to 3 at a time ===',
        '[23:00:05 INFO w] - Protein cache for gA--fa1:aaaaaaaa: cog 0/100 cached, kegg 0/100 cached',
        '[23:20:00 INFO w] - === STAGE 2: genome 2/4 (gB--fa1:bbbbbbbb) phase4-12 starting, up to 3 at a time ===',
        '[23:20:05 INFO w] - Protein cache for gB--fa1:bbbbbbbb: cog 0/100 cached',
        '[23:30:00 INFO w] - === LOADS: gA--fa1:aaaaaaaa loading into the MARGIE database; its place goes to the next genome ===',
        '[23:40:00 INFO w] - === STAGE 2: genome 3/4 (gC--fa1:cccccccc) phase4-12 starting, up to 3 at a time ===',
        '[23:40:05 INFO w] - Protein cache for gC--fa1:cccccccc: cog 100/100 cached',
        '[23:45:00 INFO w] - Protein cache: 100 new protein(s) of gA--fa1:aaaaaaaa kept for cog',
        '[23:50:00 INFO w] - === LOADS: gB--fa1:bbbbbbbb waiting for a place to load (1 genomes loading) ===',
    ])
    # gA is being written; gB is computed and waits; starts come 20 min apart, one genome to go.
    assert snap['writing'] == 'gA--fa1:aaaaaaaa'
    assert snap['writes_waiting'] == 1
    assert snap['start_gap_s'] == 1200 and snap['starts_left_s'] == 1200
    assert snap['write_genome_s'] is None

    # Past midnight: gA written 60 min after its compute ended, at 00:30.
    snap = _feed(pace, [
        '[00:30:00 INFO o] - Logged workflow run: margie_sb run_id=r status=success rules_completed=2 (hash fa1:aaaaaaaa...)',
        '[00:31:00 INFO w] - === LOADS: gC--fa1:cccccccc loading into the MARGIE database; its place goes to the next genome ===',
    ])
    assert snap['writing'] == ''
    assert snap['write_genome_s'] == 3600
    # gB (new proteins) and gC (all from the cache) are not written; only gB takes the writer's time.
    assert snap['writes_waiting'] == 2
    assert snap['writes_left_s'] == 3600


def test_the_closing_steps_follow_the_writes():
    pace = RunPace()
    snap = _feed(pace, [
        '[09:50:30 INFO w] - Waiting for 474 write(s) to the MARGIE database to finish',
        '[19:00:00 INFO w] - === FINALIZE: generate pangenome report figures ===',
    ])
    assert snap['draining'] is True
    assert snap['closing'] == 'FINALIZE: generate pangenome report figures'


def test_lines_without_a_time_change_nothing():
    pace = RunPace()
    assert pace.feed('Protein cache: 3 new protein(s) of gA--fa1:aaaaaaaa kept for cog') is False
    assert pace.snapshot()['writing'] == ''
