"""
Short-lived answers to the slow reads that every page makes over SSH (the job list, config.yaml,
the databases and the tools), per user. An answer younger than `fresh` seconds is reused; one up
to `stale` seconds old is returned at once while a background thread asks again, so a page never
waits on the cluster twice for the same thing; anything older is asked for and waited on. Writes
drop what they change (drop()).
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


def get(key: tuple, ask: Callable[[], Any], fresh: float = FRESH, stale: float = STALE) -> Any:
    """Returns the answer for key (user id first): reused, returned while refreshed, or asked for.
    An error from ask() is raised and nothing is kept."""
    with _lock:
        hit = _answers.get(key)
    if hit:
        age = time.monotonic() - hit[0]
        if age < fresh:
            return hit[1]
        if age < stale:
            _refresh(key, ask)
            return hit[1]
    value = ask()
    with _lock:
        _answers[key] = (time.monotonic(), value)
    return value


def _refresh(key: tuple, ask: Callable[[], Any]) -> None:
    """Asks again in the background, once at a time per key; a failure keeps the old answer."""
    with _lock:
        if key in _asking:
            return
        _asking.add(key)

    def run() -> None:
        try:
            value = ask()
            with _lock:
                _answers[key] = (time.monotonic(), value)
        except Exception as exc:  # the old answer stands; the next read tries again
            LOGGER.debug("Background refresh of %s failed: %s", key[1:], exc)
        finally:
            with _lock:
                _asking.discard(key)

    threading.Thread(target=run, name=f"read-cache-{key[1]}", daemon=True).start()


def drop(user_id: Any, *names: str) -> None:
    """Forgets this user's answers named (all of them when none is named)."""
    with _lock:
        for key in [k for k in _answers if k[0] == user_id and (not names or k[1] in names)]:
            del _answers[key]
