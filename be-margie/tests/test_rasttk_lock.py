"""RASTtk jobs take turns through lock slots (margie_sb.phase3.max_parallel_genomes of them). A
cancelled job is killed before it can remove its slot, and the next RASTtk job waited until the slot
was as old as its own time limit, so it sat idle and then ran out of time. The holder writes
alive_at every minute, and a slot with no sign of life for 10 minutes is taken over. These run the
rule's own lock code with bash."""

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

SMK = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'margie_sb.smk'
GNU_STAT = subprocess.run(['stat', '-c', '%Y', '/'], capture_output=True).returncode == 0


def _lock_script(lock: Path, beat: int = 60, slots: int = 1) -> str:
    rule = re.search(r"rule run_rasttk:.*?\nrule ", SMK.read_text(), re.S).group(0)
    code = re.search(r"\n( *STALE_SECONDS=.*?trap .*? EXIT)\n", rule, re.S).group(1)
    code = code.replace('{params.lock}', str(lock)).replace('{params.slots}', str(slots))
    code = code.replace('{{', '{').replace('}}', '}')
    return f"set -euo pipefail\n{code.replace('sleep 60', f'sleep {beat}')}\necho ACQUIRED\n"


def _run(script: str, timeout: float):
    return subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=timeout)


def _slot(lock: Path, n: int = 1) -> Path:
    return lock.parent / f'{lock.name}.{n}'


def _left_lock(lock: Path, acquired: int, alive: int | None = None) -> None:
    lock.mkdir()
    (lock / 'acquired_at').write_text(f'{acquired}\n')
    if alive is not None:
        (lock / 'alive_at').write_text(f'{alive}\n')


def test_a_lock_left_by_a_cancelled_job_is_taken_over(tmp_path):
    lock = tmp_path / 'rasttk_bvbrc.lock'
    _left_lock(_slot(lock), int(time.time()) - 3600)
    done = _run(_lock_script(lock), timeout=20)
    assert done.returncode == 0 and 'ACQUIRED' in done.stdout
    assert 'its holder has stopped, taking over' in done.stderr
    assert not _slot(lock).exists()


def test_a_holder_that_is_alive_keeps_the_lock(tmp_path):
    lock = tmp_path / 'rasttk_bvbrc.lock'
    now = int(time.time())
    _left_lock(_slot(lock), now - 3600, alive=now)
    with pytest.raises(subprocess.TimeoutExpired):
        _run(_lock_script(lock), timeout=3)
    assert (_slot(lock) / 'acquired_at').read_text().strip() == str(now - 3600)


def test_the_holder_writes_that_it_is_alive(tmp_path):
    lock = tmp_path / 'rasttk_bvbrc.lock'
    done = _run(_lock_script(lock, beat=1) + f'sleep 2.5\ncat "{_slot(lock)}/alive_at"\n', timeout=20)
    assert done.returncode == 0
    assert abs(int(done.stdout.split()[-1]) - time.time()) < 10
    assert not _slot(lock).exists()


@pytest.mark.skipif(not GNU_STAT, reason='reads the folder time with GNU stat, as on the cluster')
def test_an_empty_lock_folder_counts_from_its_own_time(tmp_path):
    lock = tmp_path / 'rasttk_bvbrc.lock'
    _slot(lock).mkdir()
    old = time.time() - 3600
    os.utime(_slot(lock), (old, old))
    done = _run(_lock_script(lock), timeout=20)
    assert done.returncode == 0 and 'ACQUIRED' in done.stdout


def test_a_free_slot_lets_another_rasttk_job_start(tmp_path):
    lock = tmp_path / 'rasttk_bvbrc.lock'
    now = int(time.time())
    _left_lock(_slot(lock, 1), now, alive=now)
    _left_lock(_slot(lock, 2), now, alive=now)
    done = _run(_lock_script(lock, slots=3) + f'ls -d "{lock}".*\n', timeout=20)
    assert done.returncode == 0 and 'ACQUIRED' in done.stdout
    assert f'{lock}.3' in done.stdout


def test_all_slots_alive_make_the_next_job_wait(tmp_path):
    lock = tmp_path / 'rasttk_bvbrc.lock'
    now = int(time.time())
    for n in (1, 2, 3):
        _left_lock(_slot(lock, n), now, alive=now)
    with pytest.raises(subprocess.TimeoutExpired):
        _run(_lock_script(lock, slots=3), timeout=3)
