"""
One writer at a time on the MARGIE database, across every genome and run of the account.

A write takes the database's turn first: a POSIX lock on <database>.write-turn, which the
file system keeps across nodes as it keeps SQLite's own locks. The writer that has it works
while the others wait in turn, so a load does not meet "database is locked" from writers in
other genomes and runs. Readers take no turn.
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import functools
import os
import threading
import time

# Seconds between tries while another writer has the turn.
POLL = 1.0
# Seconds the run's controller waits for the turn to write a genome's caches, at most; it looks
# after every genome of the run, so then the write goes ahead on SQLite's lock.
CONTROLLER_WAIT = 600.0

_lock = threading.RLock()
# Turns this process holds: turn file -> (descriptor, depth). A POSIX lock belongs to the
# process, so a nested or concurrent write in the same process shares the one lock.
_held: dict[str, tuple[int, int]] = {}


def turn_path(db_path: str) -> str:
    """The database's turn file, beside it."""
    return f'{os.path.expanduser(str(db_path))}.write-turn'


def _take(path: str, wait: float | None) -> bool:
    deadline = None if wait is None else time.monotonic() + wait
    with _lock:
        if path in _held:
            fd, depth = _held[path]
            _held[path] = (fd, depth + 1)
            return True
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError:
            return False
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                _held[path] = (fd, 1)
                return True
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    # A file system without these locks: the write goes on SQLite's lock alone.
                    os.close(fd)
                    return False
            if deadline is not None and time.monotonic() >= deadline:
                os.close(fd)
                return False
            time.sleep(POLL)


def _give(path: str) -> None:
    with _lock:
        fd, depth = _held[path]
        if depth > 1:
            _held[path] = (fd, depth - 1)
            return
        del _held[path]
        try:
            fcntl.lockf(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


@contextlib.contextmanager
def turn(db_path: str, wait: float | None = None):
    """Holds the database's write turn for the block; yields whether it was had. It waits as
    long as it takes, or `wait` seconds at most; without the turn the write goes ahead on
    SQLite's own lock and busy timeout."""
    path = turn_path(db_path)
    had = _take(path, wait)
    try:
        yield had
    finally:
        if had:
            _give(path)


def writes(wait: float | None = None):
    """Decorates a function whose first argument is the database path: it runs in the turn."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(db_path, *args, **kwargs):
            if not db_path:
                return fn(db_path, *args, **kwargs)
            with turn(db_path, wait=wait):
                return fn(db_path, *args, **kwargs)
        return inner
    return wrap
