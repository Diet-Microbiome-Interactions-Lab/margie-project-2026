"""Files: deleting files and folders as a job on the login node; MARGIE's own folders, home and the
lab's shared databases are refused before anything runs."""

from unittest.mock import patch

from bioinformatics_tools.api.routers.ssh import _claim_run_folder, _delete_plan
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

ROUTE = "/v1/ssh/delete_paths"
SSH = "bioinformatics_tools.api.routers.ssh"
HOME = "/home/u"
CODE = "/home/u/margie-backend"
GROUP = "/depot/lab/margie"


def _plan(*paths, seen=None):
    return _delete_plan(list(paths), seen or {}, HOME, CODE, GROUP)


def test_files_and_folders_of_ones_own_are_deleted():
    items, refused = _plan("/scratch/c/u/old-run", "/home/u/notes.txt", "/depot/lab/margie/data/mine")
    assert [it["source"] for it in items] == ["/scratch/c/u/old-run", "/home/u/notes.txt", "/depot/lab/margie/data/mine"]
    assert refused == []


def test_home_and_above_it_are_refused():
    items, refused = _plan("/home/u", "/home", "/")
    assert items == [] and len(refused) == 3


def test_margies_own_folders_are_refused_in_them_and_above_them():
    _, refused = _plan("/home/u/bioinformatics-tools", "/home/u/margie-backend/bioinformatics_tools",
                       "/home/u/.ssh/id_ed25519", "/home/u/.config", "/home/u/.local/share/bsp/jobs/x.log")
    assert len(refused) == 5 and all("MARGIE's own" in r["message"] for r in refused)


def test_the_labs_shared_databases_and_containers_are_refused():
    _, refused = _plan("/depot/lab/margie", "/depot/lab/margie/databases/margie-generated-databases/sqlite",
                       "/depot/lab/margie/sif/rasttk.sif", "/depot/lab")
    assert len(refused) == 4


def test_a_path_through_a_symlink_is_judged_where_it_really_is():
    items, refused = _plan("/scratch/c/u/link-to-code/x", seen={"/scratch/c/u/link-to-code/x": "/home/u/margie-backend/x"})
    assert items == [] and "MARGIE's own" in refused[0]["message"]


def test_the_same_path_twice_is_deleted_once():
    items, _ = _plan("/scratch/c/u/a", "/scratch/c/u/a")
    assert len(items) == 1


def test_only_refused_paths_start_no_job(authed_client):  # noqa: F811
    with patch(f"{SSH}._build_connection"), patch(f"{SSH}.ssh_sftp") as sftp, \
            patch(f"{SSH}._run_remote_check", return_value=(0, "@/home/testuser/margie-backend\n@/home/testuser")) as run:
        sftp.read_remote_yaml.return_value = {}
        r = authed_client.post(ROUTE, json={"paths": ["~"]})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] is None and body["state"] == "done" and body["results"][0]["ok"] is False
    assert run.call_count == 1  # only the look at where things really are


def test_deleting_starts_a_job_on_the_login_node(authed_client):  # noqa: F811
    answers = iter([(0, "@/home/testuser/margie-backend\n@/scratch/c/testuser/old"), (0, ""), (0, "started")])
    with patch(f"{SSH}._build_connection"), patch(f"{SSH}.ssh_sftp") as sftp, \
            patch(f"{SSH}._run_remote_check", side_effect=lambda *_: next(answers)) as run:
        sftp.read_remote_yaml.return_value = {}
        r = authed_client.post(ROUTE, json={"paths": ["/scratch/c/testuser/old/"]})
    assert r.status_code == 200
    body = r.json()
    assert body["op"] == "delete" and body["where"] == "login" and body["state"] == "running"
    assert body["results"] == [{"source": "/scratch/c/testuser/old", "target": "", "ok": None, "message": ""}]
    plan = next(c for c in sftp.write_remote_text_file.call_args_list if c[0][0].endswith("/plan"))
    assert plan[0][1] == "delete\t/scratch/c/testuser/old\t\n"
    assert "setsid nohup bash run.sh" in run.call_args[0][1]


def test_bad_requests_are_refused(authed_client):  # noqa: F811
    assert authed_client.post(ROUTE, json={"paths": []}).status_code == 400
    assert authed_client.post(ROUTE, json={"paths": [""]}).status_code == 400


def test_a_run_folder_taken_in_the_same_minute_gets_a_number():
    with patch(f"{SSH}._run_remote_check", return_value=(0, "/out/2026-10-23-0314-2\n")) as run:
        assert _claim_run_folder(object(), "/out/2026-10-23-0314") == "/out/2026-10-23-0314-2"
    assert "until mkdir" in run.call_args[0][1]
    with patch(f"{SSH}._run_remote_check", return_value=(0, "")):
        assert _claim_run_folder(object(), "/out/2026-10-23-0314") == "/out/2026-10-23-0314"
    with patch(f"{SSH}._run_remote_check", return_value=(1, "/elsewhere")):
        assert _claim_run_folder(object(), "/out/2026-10-23-0314") == "/out/2026-10-23-0314"
