"""The build password: builds and cloning margie-build need it; copying does not. Only its
SHA-256 is set (MARGIE_BUILD_PASSWORD_SHA256), never the password, and nothing in the code."""

import hashlib

import pytest
from fastapi import HTTPException

from bioinformatics_tools.api import build_gate

PHRASE = "a-test-phrase-"


@pytest.fixture
def password_set(monkeypatch):
    monkeypatch.setenv(build_gate.ENV, hashlib.sha256(PHRASE.encode()).hexdigest())


def test_the_password_opens_builds(password_set):
    assert build_gate.matches(PHRASE)
    build_gate.check(PHRASE)


@pytest.mark.parametrize("given", [None, "", "a-test-phrase", "A-TEST-PHRASE-", " a-test-phrase-"])
def test_anything_else_is_refused(password_set, given):
    assert not build_gate.matches(given)
    with pytest.raises(HTTPException) as e:
        build_gate.check(given)
    assert e.value.status_code == 403


def test_with_no_password_set_building_stays_closed(monkeypatch):
    monkeypatch.delenv(build_gate.ENV, raising=False)
    assert not build_gate.matches(PHRASE)
    assert not build_gate.matches("")
