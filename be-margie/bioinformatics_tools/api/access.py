"""
Who may use this MARGIE, and a guard against guessing passwords.

Clusters: MARGIE_ALLOWED_CLUSTERS on the server lists the clusters accounts may be on, as
host patterns separated by commas (for example `*.example.edu,hpc.other.org`). Every account
is tied to a cluster account (sign-up logs in to it with the user's key), so this decides who
can sign up and sign in. Empty, any cluster is accepted.

Guessing: failed sign-ins lock the username, and the address they come from, for a while;
sign-ups are limited per address too, since each makes the server log in to a cluster.
Counted in memory, per API process (one replica: SQLite).
"""

from __future__ import annotations

import fnmatch
import os
import threading
import time

from fastapi import HTTPException, Request, status

ENV = 'MARGIE_ALLOWED_CLUSTERS'


def allowed_clusters() -> list[str]:
    """The accepted cluster host patterns, lower case; empty when any cluster is accepted."""
    return [p.strip().lower() for p in os.getenv(ENV, '').replace(';', ',').split(',') if p.strip()]


def _host(value: str | None) -> str:
    """The host name in a cluster address ('user@host', 'host:22' and 'host.' are reduced to 'host')."""
    host = (value or '').strip().lower().rsplit('@', 1)[-1]
    if host.count(':') == 1:
        host = host.split(':', 1)[0]
    return host.rstrip('.')


def cluster_allowed(value: str | None) -> bool:
    """Whether accounts may be on this cluster."""
    patterns = allowed_clusters()
    if not patterns:
        return True
    host = _host(value)
    return bool(host) and any(fnmatch.fnmatchcase(host, p) for p in patterns)


def check_cluster(value: str | None) -> None:
    """Refuses (403) a cluster this MARGIE does not accept."""
    if not cluster_allowed(value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This MARGIE accepts accounts on these clusters only: {', '.join(allowed_clusters())}.",
        )


class Guard:
    """Counts attempts per key in a sliding window: `limit` of them within `window` seconds lock
    the key for `lock` seconds."""

    def __init__(self, limit: int, window: float, lock: float):
        self.limit, self.window, self.lock = limit, window, lock
        self._seen: dict[str, list[float]] = {}
        self._until: dict[str, float] = {}
        self._mutex = threading.Lock()

    def wait(self, key: str) -> float:
        """Seconds until the key may try again; 0 when it may now."""
        with self._mutex:
            left = self._until.get(key, 0) - time.monotonic()
            if left <= 0:
                self._until.pop(key, None)
                return 0.0
            return left

    def count(self, key: str) -> None:
        """Counts one attempt (a failure, or for sign-ups any attempt)."""
        now = time.monotonic()
        with self._mutex:
            seen = [t for t in self._seen.get(key, []) if now - t < self.window]
            seen.append(now)
            if len(seen) >= self.limit:
                self._until[key] = now + self.lock
                seen = []
            self._seen[key] = seen
            # Keeps the table small: keys with nothing recent are forgotten.
            if len(self._seen) > 10_000:
                for k in [k for k, v in self._seen.items() if not v or now - v[-1] > self.window]:
                    del self._seen[k]

    def clear(self, key: str) -> None:
        with self._mutex:
            self._seen.pop(key, None)
            self._until.pop(key, None)

    def reset(self) -> None:
        with self._mutex:
            self._seen.clear()
            self._until.clear()


# Five wrong passwords for a username, or twenty from one address, within 15 minutes: 15 minutes off.
SIGNIN_BY_NAME = Guard(limit=5, window=15 * 60, lock=15 * 60)
SIGNIN_BY_ADDRESS = Guard(limit=20, window=15 * 60, lock=15 * 60)
# Ten sign-ups from one address in an hour: an hour off.
SIGNUP_BY_ADDRESS = Guard(limit=10, window=60 * 60, lock=60 * 60)


def client_address(request: Request) -> str:
    """The caller's address: X-Real-IP, which the ingress in front sets, else the connection's."""
    return (request.headers.get('x-real-ip') or (request.client.host if request.client else '') or '?').strip()


def too_many(wait: float, what: str) -> HTTPException:
    """A 429 saying when to try again."""
    minutes = max(1, round(wait / 60))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f'Too many {what}. Try again in {minutes} minute{"s" if minutes != 1 else ""}.',
        headers={'Retry-After': str(int(wait) + 1)},
    )
