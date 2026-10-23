"""
The build password: building containers and reference databases with margie-build (and
cloning it onto the cluster) is open only to whoever knows it. Copying what the group
already has stays open to everyone.

The API never holds the password itself, only its SHA-256, from MARGIE_BUILD_PASSWORD_SHA256
(a secret on the server; never in the repository, which is public). Unset, building stays closed.
"""

import hashlib
import hmac
import os

from fastapi import HTTPException, status

ENV = "MARGIE_BUILD_PASSWORD_SHA256"


def _expected() -> str:
    return (os.getenv(ENV) or "").strip().lower()


def matches(given: str | None) -> bool:
    """Whether `given` is the build password (compared in constant time); never, when none is set."""
    expected = _expected()
    if not expected or not given:
        return False
    got = hashlib.sha256(given.encode()).hexdigest()
    return hmac.compare_digest(got, expected)


def check(given: str | None) -> None:
    """Refuses with 403 unless `given` is the build password."""
    if not matches(given):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Building needs the build password.")
