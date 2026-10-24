"""Fresh databases for a new lab: every store starts empty as its next version; nothing is copied or overwritten."""

from unittest.mock import patch

import pytest

from bioinformatics_tools.api.services import user_stores
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)


def _plan(versions):
    """Runs start_setup(fresh=True) with the stores at these versions; returns the plan and what it records."""
    stores = [{"version": v} for v in versions]
    got = {}
    with patch.object(user_stores, "status", return_value={"root": "/scratch/c/u/margie-2026", "op": None, "stores": stores}), \
         patch.object(user_stores, "_start", side_effect=lambda conn, root, kind, plan, after, cfg: got.update(plan=plan, after=after)), \
         patch.object(user_stores, "_backups", side_effect=AssertionError("fresh never reads backups")), \
         patch.object(user_stores, "resolve_base", side_effect=AssertionError("fresh never copies a base")):
        user_stores.start_setup(None, {}, "u", fresh=True)
    return got["plan"], got["after"]


def test_every_store_starts_empty_as_its_next_version():
    versions = [None, 2, None, 1][: len(user_stores.STORES)] + [None] * max(0, len(user_stores.STORES) - 4)
    plan, after = _plan(versions)
    assert not [p for p in plan if p[0] in ("copy", "files")]
    for s, v in zip(user_stores.STORES, versions):
        assert after["versions"][s["id"]] == (v or 0) + 1
    occ = [p for p in plan if p[0] == "occ"]
    assert len(occ) == 1 and occ[0][3].endswith(".venv/bin/python") and occ[0][4].endswith("workflow_tools/scoring")
    job_db = next(s for s in user_stores.STORES if s["id"] == "job_db")
    new = [p for p in plan if p[0] == "new"]
    assert len(new) == 1 and job_db["name"] in new[0][2] and "-v" in new[0][2]


def test_the_copy_script_knows_the_empty_reference_step():
    assert "\n    occ)\n" in user_stores.COPY_SCRIPT
    assert "c3_occ.new_reference()" in user_stores.COPY_SCRIPT


def test_fresh_needs_the_build_password(authed_client):  # noqa: F811
    r = authed_client.post("/v1/ssh/stores/setup", json={"fresh": True, "build_password": "wrong"})
    assert r.status_code == 403


def test_a_first_run_without_a_base_it_reads_starts_new_ones():
    """Outside the lab (no backup, no base the account reads): the operon reference from MARGIE's
    starter in the backend copy, the other stores new and empty; nothing from depot."""
    stores = [{"version": None, "found": None} for _ in user_stores.STORES]
    got = {}
    run = lambda conn, cmd, timeout=60.0: (0, "/home/u") if cmd.startswith("printf") else (0, "")  # noqa: E731
    with patch.object(user_stores, "status", return_value={"root": "/scratch/c/u/margie/margie-databases", "op": None, "stores": stores}), \
         patch.object(user_stores, "_start", side_effect=lambda conn, root, kind, plan, after, cfg: got.update(plan=plan, after=after)), \
         patch.object(user_stores, "_backups", return_value=[]), \
         patch.object(user_stores, "resolve_base", return_value=""), \
         patch.object(user_stores, "_size", return_value=1), \
         patch.object(user_stores, "_run", side_effect=run):
        user_stores.start_setup(None, {}, "u")
    plan = got["plan"]
    copies = [p for p in plan if p[0] in ("copy", "files")]
    assert len(copies) == 1 and copies[0][2] == f"/home/u/{user_stores.STARTER_OCC}"
    assert all(v == 1 for v in got["after"]["versions"].values()) and len(got["after"]["versions"]) == len(user_stores.STORES)
    assert [p for p in plan if p[0] == "new"]
