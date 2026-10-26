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


# ---- renaming a file or folder where it is ----

RENAME = "/v1/ssh/rename_path"


def _rename(authed_client, answer, **body):
    """Posts a rename; the cluster says where things really are, then `answer` for the move."""
    def run(conn, command):
        if command.startswith("printf"):
            src = body.get("path", "")
            return 0, f"@/home/testuser/margie-project-2026/be-margie\n@{src}\n"
        return 0, answer
    with patch(f"{SSH}._build_connection"), patch(f"{SSH}._read_config", return_value={}), \
         patch(f"{SSH}._run_remote_check", side_effect=run) as remote:
        r = authed_client.post(RENAME, json=body)
    return r, remote


def test_a_file_or_folder_is_renamed_where_it_is(authed_client):  # noqa: F811
    r, remote = _rename(authed_client, "RENAMED", path="/scratch/u/runs/old name", name="new name")
    assert r.status_code == 200 and r.json() == {"path": "/scratch/u/runs/new name", "old": "/scratch/u/runs/old name", "renamed": True}
    assert "mv -n -T -- '/scratch/u/runs/old name' '/scratch/u/runs/new name'" in remote.call_args[0][1]


def test_a_rename_replaces_nothing(authed_client):  # noqa: F811
    r, _ = _rename(authed_client, "EXISTS", path="/scratch/u/a.txt", name="b.txt")
    assert r.status_code == 409 and "nothing was replaced" in r.json()["detail"]


def test_a_new_name_is_one_name(authed_client):  # noqa: F811
    for bad in ("", "..", "x/y", "a\nb"):
        r, _ = _rename(authed_client, "RENAMED", path="/scratch/u/a.txt", name=bad)
        assert r.status_code == 400


def test_what_is_not_deleted_from_here_is_not_renamed(authed_client):  # noqa: F811
    for path in ("/home/testuser", "/home/testuser/.ssh", "/home/testuser/.config/bioinformatics-tools"):
        r, _ = _rename(authed_client, "RENAMED", path=path, name="moved")
        assert r.status_code == 403 and "not renamed" in r.json()["detail"], path


def test_the_same_name_changes_nothing(authed_client):  # noqa: F811
    r, remote = _rename(authed_client, "RENAMED", path="/scratch/u/a.txt", name="a.txt")
    assert r.json() == {"path": "/scratch/u/a.txt", "old": "/scratch/u/a.txt", "renamed": False}
    remote.assert_not_called()


# ---- a run without the cache ----

def test_a_run_without_the_cache_says_so_on_its_command_line():
    from bioinformatics_tools.api.routers import ssh
    on = ssh._dane_wf_command("margie_sb", "/g", "/o", "cog")
    off = ssh._dane_wf_command("margie_sb", "/g", "/o", "cog", use_cache=False)
    assert "use_cache" not in on and off.endswith(" margie_sb.use_cache: false")
    script = ssh._command_script("j", "margie_sb", "/g", "/o", "cog", use_cache=False)
    assert "  margie_sb.use_cache: false" in script


def test_resume_and_restart_keep_a_run_without_the_cache():
    from bioinformatics_tools.api.routers import ssh
    with patch(f"{SSH}._run_remote_check", return_value=(0, "NOCACHE\n")) as run:
        assert ssh._ran_without_cache(None, "/scratch/u/run-1") is True
    assert "/scratch/u/run-1/run-command.sh" in run.call_args[0][1]
    with patch(f"{SSH}._run_remote_check", return_value=(1, "")):
        assert ssh._ran_without_cache(None, "/scratch/u/run-2") is False
    assert ssh._ran_without_cache(None, None) is False
