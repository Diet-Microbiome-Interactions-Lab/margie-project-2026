"""One command lists several folders a few levels deep (Results reads its runs' genome folders
with it, in place of a trip to the cluster per folder)."""

from unittest.mock import patch

from bioinformatics_tools.api.auth import create_access_token
from bioinformatics_tools.api.services import read_cache
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"
OUT = ("@@/r/run2\nd\t4096\tg1\nf\t52113\tg1/FINAL_ANNOTATION_WITH_CONFIDENCE.tsv\nd\t4096\tg1/cog\n"
       "@@/r/run1\nd\t4096\tg2\nd\t4096\tg2/scoring\nf\t12\tg2/scoring/x.tsv\n")


@patch(f"{SSH}._build_connection")
def test_several_folders_in_one_command(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}._run_remote_check", return_value=(0, OUT)) as run:
        d = authed_client.post("/v1/ssh/tree", json={"paths": ["/r/run2", "/r/run1"], "depth": 3, "prune": ["original_container_outputs"]}).json()
    assert run.call_count == 1
    command = run.call_args[0][1]
    assert "-maxdepth 3" in command and "-path /r/run2/original_container_outputs" in command and "-name '.*'" in command
    assert "%y\\t%s\\t%P" in command
    # Type and path first, as before, then the size in bytes.
    assert d["trees"]["/r/run2"] == [["d", "g1", 4096], ["f", "g1/FINAL_ANNOTATION_WITH_CONFIDENCE.tsv", 52113], ["d", "g1/cog", 4096]]
    assert d["trees"]["/r/run1"][-1] == ["f", "g2/scoring/x.tsv", 12]


@patch(f"{SSH}._build_connection")
def test_the_answer_is_reused(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}._run_remote_check", return_value=(0, OUT)) as run:
        for _ in range(3):
            authed_client.post("/v1/ssh/tree", json={"paths": ["/r/run2", "/r/run1"]})
    assert run.call_count == 1


@patch(f"{SSH}._build_connection")
def test_a_signed_in_listing_keeps_the_reads(_conn, authed_client):  # noqa: F811
    # A POST with a token drops the user's reads (_changes_drop_reads); the listing only reads, so its
    # answer and the others stand.
    read_cache.drop(FAKE_USER["user_id"])
    token = {"Authorization": f"Bearer {create_access_token(FAKE_USER['user_id'], FAKE_USER['username'])}"}
    with patch(f"{SSH}._run_remote_check", return_value=(0, OUT)) as run:
        for _ in range(3):
            assert authed_client.post("/v1/ssh/tree", json={"paths": ["/r/run2", "/r/run1"]}, headers=token).status_code == 200
    assert run.call_count == 1


@patch(f"{SSH}._build_connection")
def test_odd_requests_are_refused(_conn, authed_client):  # noqa: F811
    assert authed_client.post("/v1/ssh/tree", json={"paths": []}).status_code == 400
    assert authed_client.post("/v1/ssh/tree", json={"paths": ["/a"], "depth": 9}).status_code == 400
    assert authed_client.post("/v1/ssh/tree", json={"paths": ["/a"], "prune": ["../x/y"]}).status_code == 400
