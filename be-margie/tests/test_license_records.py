"""A licence acceptance's record copy is written on the user's cluster, as the user: in the group's
records folder (LICENSE_RECORDS_DIR) when it can be, else in the user's own home folder."""

import json
from unittest.mock import patch

from bioinformatics_tools.api import licensing
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"
SFTP = "bioinformatics_tools.utilities.ssh_sftp.write_remote_text_file"


def _accept(authed_client):  # noqa: F811
    terms = licensing.load_terms()
    items = [a["id"] for a in licensing.catalog.ACK_ITEMS]
    return authed_client.post("/v1/license/accept", json={
        "accepted_items": items, "terms_version": terms["version"], "terms_sha256": terms["sha256"],
        "usage_type": "academic", "licensed_tools": [],
    })


def test_the_record_goes_to_the_groups_folder_on_the_cluster(authed_client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LICENSE_RECORDS_DIR", "/group/margie/licensing-records")
    with patch(f"{SSH}._build_connection"), patch(SFTP) as write:
        r = _accept(authed_client)
    assert r.status_code == 200
    path = r.json()["depot_record_path"]
    assert path.startswith("/group/margie/licensing-records/") and path.endswith("/testuser")
    names = [c[0][0] for c in write.call_args_list]
    assert names == [f"{path}/terms.txt", f"{path}/record.json"]
    record = json.loads(write.call_args_list[1][0][1])
    assert record["username"] == "testuser" and record["usage_type"] == "academic"


def test_without_room_in_the_group_folder_it_goes_home(authed_client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LICENSE_RECORDS_DIR", "/group/margie/licensing-records")
    def write(path, text, connection):
        if path.startswith("/group/"):
            raise PermissionError("Permission denied")
    with patch(f"{SSH}._build_connection"), patch(SFTP, side_effect=write):
        r = _accept(authed_client)
    assert r.status_code == 200
    assert r.json()["depot_record_path"].startswith(f"{FAKE_USER['home_dir']}/.local/share/bioinformatics-tools/licensing-records/")


def test_the_acceptance_counts_even_when_no_copy_can_be_written(authed_client, monkeypatch):  # noqa: F811
    monkeypatch.delenv("LICENSE_RECORDS_DIR", raising=False)
    with patch(f"{SSH}._build_connection"), patch(SFTP, side_effect=OSError("cluster unreachable")):
        r = _accept(authed_client)
    assert r.status_code == 200 and r.json()["accepted"] is True
    assert r.json()["depot_record_path"] is None and "cluster unreachable" in r.json()["depot_record_error"]
