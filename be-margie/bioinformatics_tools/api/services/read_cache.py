"""
Short-lived answers to the slow reads that every page makes over SSH (the job list, config.yaml,
the databases and the tools), per user. An answer younger than `fresh` seconds is reused; one up
to `stale` seconds old is returned at once while a background thread asks again, so a page never
waits on the cluster twice for the same thing; anything older is asked for and waited on. Writes
drop what they change (drop()).

An answer can have a backup (scratch_cache: a copy kept on the cluster): with nothing in memory
(an API just started), the copy is returned at once while the cluster is asked again, and each
fresh answer is saved to it. After drop(), the copy waits until a fresh answer replaces it.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

FRESH = 15.0
STALE = 120.0

_lock = threading.Lock()
_answers: dict[tuple, tuple[float, Any]] = {}
_asking: set[tuple] = set()
# (user id, name) dropped since their last fresh answer: their backups wait.
_dropped: set[tuple] = set()

Backup = tuple[Callable[[], Any], Callable[[Any], None]]


def get(key: tuple, ask: Callable[[], Any], fresh: float = FRESH, stale: float = STALE,
        backup: Backup | None = None) -> Any:
    """Returns the answer for key (user id first): reused, returned while refreshed, taken from
    its backup (load, save) while refreshed, or asked for. An error from ask() is raised and
    nothing is kept."""
    with _lock:
        hit = _answers.get(key)
        dropped = key[:2] in _dropped
    if hit:
        age = time.monotonic() - hit[0]
        if age < fresh:
            return hit[1]
        if age < stale:
            _refresh(key, ask, backup)
            return hit[1]
    if backup and not hit and not dropped:
        try:
            kept = backup[0]()
        except Exception as exc:
            LOGGER.debug("Reading the backup of %s failed: %s", key[1:], exc)
            kept = None
        if kept is not None:
            with _lock:
                _answers[key] = (time.monotonic() - fresh, kept)
            _refresh(key, ask, backup)
            return kept
    value = ask()
    _keep(key, value, backup)
    return value


def _keep(key: tuple, value: Any, backup: Backup | None) -> None:
    """Keeps a fresh answer, and saves it to its backup in the background."""
    with _lock:
        _answers[key] = (time.monotonic(), value)
        _dropped.discard(key[:2])
    if backup:
        threading.Thread(target=_save, args=(backup[1], value, key), name=f"read-cache-save-{key[1]}", daemon=True).start()


def _save(save: Callable[[Any], None], value: Any, key: tuple) -> None:
    try:
        save(value)
    except Exception as exc:
        LOGGER.debug("Saving the backup of %s failed: %s", key[1:], exc)


def _refresh(key: tuple, ask: Callable[[], Any], backup: Backup | None = None) -> None:
    """Asks again in the background, once at a time per key; a failure keeps the old answer."""
    with _lock:
        if key in _asking:
            return
        _asking.add(key)

    def run() -> None:
        try:
            value = ask()
            _keep(key, value, backup)
        except Exception as exc:  # the old answer stands; the next read tries again
            LOGGER.debug("Background refresh of %s failed: %s", key[1:], exc)
        finally:
            with _lock:
                _asking.discard(key)

    threading.Thread(target=run, name=f"read-cache-{key[1]}", daemon=True).start()


def drop(user_id: Any, *names: str) -> None:
    """Forgets this user's answers named (all of them when none is named)."""
    with _lock:
        gone = [k for k in _answers if k[0] == user_id and (not names or k[1] in names)]
        for key in gone:
            del _answers[key]
        _dropped.update({(user_id, n) for n in names} | {(user_id, k[1]) for k in gone})
