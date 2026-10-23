"""Copy and move in Files: a job on SLURM (or the login node), into a folder, never overwriting."""

import json
from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.routers.ssh import TRANSFER_SCRIPT, _transfer_plan, _transfer_results
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

ROUTE = "/v1/ssh/transfer_paths"
SSH = "bioinformatics_tools.api.routers.ssh"


def test_refusals_are_found_before_anything_runs():
    items, refused = _transfer_plan("move", ["/s/run", "/d/a.tsv", "/s/x/b.tsv", "/s/y/b.tsv", "/s/c"], "/d")
    assert [i["source"] for i in items] == ["/s/run", "/s/x/b.tsv", "/s/c"]
    why = {r["source"]: r["message"] for r in refused}
    assert "already in this folder" in why["/d/a.tsv"]
    assert "same name" in why["/s/y/b.tsv"]
    _, refused = _transfer_plan("move", ["/s/run"], "/s/run/sub")
    assert "inside itself" in refused[0]["message"]


def test_results_become_messages():
    items = [{"source": "/a", "target": "/d/a"}, {"source": "/b", "target": "/d/b"}, {"source": "/c", "target": "/d/c"}]
    got = _transfer_results(items, "1\tOK\n2\tEXISTS\n")
    assert [g["ok"] for g in got] == [True, False, None]
    assert "nothing was replaced" in got[1]["message"]
    assert _transfer_results(items[:1], "1\tERR cp: Permission denied")[0]["message"] == "cp: Permission denied"


def test_the_script_never_overwrites_and_runs_in_parallel():
    assert 'elif [ -e "$dst" ] || [ -L "$dst" ]; then r=EXISTS' in TRANSFER_SCRIPT
    assert "cp -Rp --" in TRANSFER_SCRIPT and "mv --" in TRANSFER_SCRIPT
    assert "wait -n" in TRANSFER_SCRIPT


def _remote(calls, sbatch=(0, "4242\n")):
    def run(conn, command):
        calls.append(command)
        if command.startswith("test -d"):
            return (0, "")
        if "sbatch" in command:
            return sbatch
        if "setsid nohup" in command:
            return (0, "started")
        return (0, "")
    return run


@patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"compute": {"cluster_default": {"account": "mylab", "partition": "cpu"}}})
@patch(f"{SSH}.ssh_sftp.write_remote_text_file")
@patch(f"{SSH}._build_connection")
def test_it_goes_to_slurm_with_the_account_partition_and_8_cores(_conn, written, _yaml, authed_client):  # noqa: F811
    calls = []
    with patch(f"{SSH}._run_remote_check", side_effect=_remote(calls)):
        d = authed_client.post(ROUTE, json={"op": "copy", "sources": ["/s/a.tsv", "/s/run"], "into": "/d"}).json()
    assert d["where"] == "slurm" and d["job"] == "4242" and d["state"] == "queued"
    sb = next(c for c in calls if "sbatch" in c)
    assert "--account=mylab" in sb and "--partition=cpu" in sb and "--cpus-per-task=8" in sb
    plan = next(c.args[1] for c in written.call_args_list if c.args[0].endswith("/plan"))
    assert plan == "copy\t/s/a.tsv\t/d/a.tsv\ncopy\t/s/run\t/d/run\n"


@patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"compute": {"cluster_default": {"account": "mylab"}}})
@patch(f"{SSH}.ssh_sftp.write_remote_text_file")
@patch(f"{SSH}._build_connection")
def test_without_slurm_it_runs_on_the_login_node(_conn, _written, _yaml, authed_client):  # noqa: F811
    calls = []
    with patch(f"{SSH}._run_remote_check", side_effect=_remote(calls, sbatch=(1, "sbatch: error: invalid account"))):
        d = authed_client.post(ROUTE, json={"op": "move", "sources": ["/s/a.tsv"], "into": "/d"}).json()
    assert d["where"] == "login" and d["job"] is None
    assert any("setsid nohup bash run.sh" in c and c.rstrip().endswith("& echo started") for c in calls)


@patch(f"{SSH}._build_connection")
def test_status_reports_each_item(_conn, authed_client):  # noqa: F811
    meta = {"op": "copy", "into": "/d", "items": [{"source": "/s/a", "target": "/d/a"}], "refused": []}
    out = f"@@meta\n{json.dumps(meta)}\n@@status\nstate=done\nhost=a123\n@@job\n4242\n@@results\n1\tOK\n@@end\n"
    with patch(f"{SSH}._run_remote_check", return_value=(0, out)):
        d = authed_client.get(f"{ROUTE}/0123456789ab").json()
    assert d["state"] == "done" and d["where"] == "slurm" and d["results"][0]["ok"] is True


@patch(f"{SSH}._build_connection")
def test_a_job_that_left_the_queue_without_starting_failed(_conn, authed_client):  # noqa: F811
    meta = {"op": "copy", "into": "/d", "items": [{"source": "/s/a", "target": "/d/a"}], "refused": []}
    out = f"@@meta\n{json.dumps(meta)}\n@@status\nstate=queued\n@@job\n4242\n@@results\n@@end\n"
    answers = iter([(0, out), (0, ""), (0, "state=queued\n")])
    with patch(f"{SSH}._run_remote_check", side_effect=lambda conn, c: next(answers)):
        d = authed_client.get(f"{ROUTE}/0123456789ab").json()
    assert d["state"] == "failed"


def test_bad_requests_are_refused(authed_client):  # noqa: F811
    assert authed_client.post(ROUTE, json={"op": "delete", "sources": ["/a"], "into": "/b"}).status_code == 400
    assert authed_client.post(ROUTE, json={"op": "copy", "sources": [], "into": "/b"}).status_code == 400
    assert authed_client.get(f"{ROUTE}/not-an-id").status_code == 400
