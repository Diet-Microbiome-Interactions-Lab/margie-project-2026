"""Files: making a folder (with the folders above it) or a new text file; refused where the account may not write."""

from unittest.mock import patch

from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

ROUTE = "/v1/ssh/make_path"
SSH = "bioinformatics_tools.api.routers.ssh"


def _post(authed_client, out, **body):
    with patch(f"{SSH}._build_connection"), patch(f"{SSH}._run_remote_check", return_value=(0, out)) as run:
        r = authed_client.post(ROUTE, json=body)
    return r, run


def test_a_folder_is_made_with_the_folders_above_it(authed_client):  # noqa: F811
    r, run = _post(authed_client, "MADE\n", path="~/new/deep/folder", kind="folder")
    assert r.status_code == 200 and r.json() == {"path": "/home/testuser/new/deep/folder", "kind": "folder", "made": True}
    assert "mkdir -p -- /home/testuser/new/deep/folder" in run.call_args[0][1]


def test_a_folder_already_there_is_fine(authed_client):  # noqa: F811
    r, _ = _post(authed_client, "THERE", path="/scratch/u", kind="folder")
    assert r.status_code == 200 and r.json()["made"] is False


def test_someone_elses_folders_are_refused(authed_client):  # noqa: F811
    r, _ = _post(authed_client, "mkdir: cannot create directory '/home/other/x': Permission denied", path="/home/other/x", kind="folder")
    assert r.status_code == 403 and "permission denied" in r.json()["detail"]


def test_a_file_never_replaces_one(authed_client):  # noqa: F811
    r, run = _post(authed_client, "EXISTS", path="/scratch/u/notes.txt", kind="file")
    assert r.status_code == 409 and "nothing was replaced" in r.json()["detail"]
    assert "noclobber" in run.call_args[0][1]


def test_a_file_needs_its_folder(authed_client):  # noqa: F811
    r, _ = _post(authed_client, "NO_FOLDER", path="/scratch/u/missing/notes.txt", kind="file")
    assert r.status_code == 404


def test_bad_requests_are_refused(authed_client):  # noqa: F811
    assert authed_client.post(ROUTE, json={"path": "/a", "kind": "link"}).status_code == 400
    assert authed_client.post(ROUTE, json={"path": "", "kind": "folder"}).status_code == 400
