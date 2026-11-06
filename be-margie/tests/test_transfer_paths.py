"""Copy and move in Files: a job on SLURM (or the login node), into a folder; what is there is left
as it is, or replaced when the paste asks."""

import json
import subprocess
from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.routers.ssh import TRANSFER_SCRIPT, _kept_why, _transfer_plan, _transfer_results
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


def test_the_script_replaces_only_when_the_line_says_so_and_runs_in_parallel():
    assert 'if [ "$rep" = replace ]; then swap' in TRANSFER_SCRIPT
    assert 'elif [ "$rep" = kept ]; then r=KEPT' in TRANSFER_SCRIPT and "else r=EXISTS" in TRANSFER_SCRIPT
    assert "cp -Rp --" in TRANSFER_SCRIPT and "mv --" in TRANSFER_SCRIPT
    assert "wait -n" in TRANSFER_SCRIPT


def _run_script(tmp_path, lines):
    """Runs the script on files in tmp_path (wait -n needs bash 4.3; plain wait does the same here)."""
    job = tmp_path / "job0123456789"
    job.mkdir()
    (job / "plan").write_text("".join("\t".join(x) + "\n" for x in lines))
    (tmp_path / "run.sh").write_text(TRANSFER_SCRIPT.replace("wait -n", "wait"))
    subprocess.run(["bash", str(tmp_path / "run.sh"), str(job), "2"], check=True)
    return dict(line.split("\t", 1) for line in (job / "results").read_text().splitlines())


def test_a_replace_puts_the_new_one_in_place_of_a_file_or_a_whole_folder(tmp_path):
    s, d = tmp_path / "s", tmp_path / "d"
    (s / "run" / ".margie").mkdir(parents=True)
    (d / "run" / ".margie").mkdir(parents=True)
    (d / "run" / "extra").mkdir()
    (s / "a.txt").write_text("new")
    (d / "a.txt").write_text("old")
    (s / "run" / ".margie" / "stores.json").write_text("new")
    (d / "run" / ".margie" / "stores.json").write_text("old")
    (s / "m.txt").write_text("new")
    (d / "m.txt").write_text("old")
    (s / "k.txt").write_text("new")
    (d / "k.txt").write_text("old")
    (s / "e.txt").write_text("new")
    (d / "e.txt").write_text("old")
    got = _run_script(tmp_path, [("copy", str(s / "a.txt"), str(d / "a.txt"), "replace"),
                                 ("copy", str(s / "run"), str(d / "run"), "replace"),
                                 ("move", str(s / "m.txt"), str(d / "m.txt"), "replace"),
                                 ("copy", str(s / "k.txt"), str(d / "k.txt"), "kept"),
                                 ("copy", str(s / "e.txt"), str(d / "e.txt"))])
    assert got == {"1": "OK", "2": "OK", "3": "OK", "4": "KEPT", "5": "EXISTS"}
    assert (d / "a.txt").read_text() == "new" and (s / "a.txt").exists()
    assert (d / "run" / ".margie" / "stores.json").read_text() == "new" and not (d / "run" / "extra").exists()
    assert (d / "m.txt").read_text() == "new" and not (s / "m.txt").exists()
    assert (d / "k.txt").read_text() == "old" and (d / "e.txt").read_text() == "old"
    assert sorted(x.name for x in d.iterdir()) == ["a.txt", "e.txt", "k.txt", "m.txt", "run"]


def test_a_replace_that_fails_leaves_both_as_they_were(tmp_path):
    s, d = tmp_path / "s", tmp_path / "d" / "ro"
    s.mkdir()
    d.mkdir(parents=True)
    (s / "a.txt").write_text("new")
    (d / "a.txt").write_text("old")
    d.chmod(0o555)
    try:
        got = _run_script(tmp_path, [("move", str(s / "a.txt"), str(d / "a.txt"), "replace")])
    finally:
        d.chmod(0o755)
    assert got["1"].startswith("ERR ")
    assert (d / "a.txt").read_text() == "old" and (s / "a.txt").read_text() == "new"
    assert [x.name for x in d.iterdir()] == ["a.txt"]


def test_a_replace_is_refused_for_an_item_inside_the_one_it_would_replace():
    items, refused = _transfer_plan("copy", ["/d/run/run"], "/d", replace=True)
    assert items == [] and "inside the run it would replace" in refused[0]["message"]
    items, refused = _transfer_plan("copy", ["/d/run/run"], "/d")
    assert len(items) == 1 and refused == []


def test_replace_results_say_what_was_kept_and_what_was_left():
    items = [{"source": "/a", "target": "/d/a", "kept": "MARGIE's own code, keys, settings or job records: they are not replaced from here."},
             {"source": "/b", "target": "/d/b"}]
    got = _transfer_results(items, "1\tKEPT\n2\tLEFT /d/.b.margie-x-2.old\n")
    assert got[0]["ok"] is False and "not replaced" in got[0]["message"]
    assert got[1]["ok"] is True and "/d/.b.margie-x-2.old" in got[1]["message"]


def test_what_is_not_deleted_is_not_replaced_except_margies_own_folder():
    home, code, group = "/home/u", "/home/u/margie-backend", "/depot/lab/margie"
    assert _kept_why({"/home/u/.margie/selections"}, home, code, group, replacing=True) == ""
    assert "not deleted" in _kept_why({"/home/u/.margie/selections"}, home, code, group)
    assert "this paste runs from" in _kept_why({"/home/u/.margie"}, home, code, group, replacing=True)
    assert "MARGIE's own" in _kept_why({"/home/u/.ssh/authorized_keys"}, home, code, group, replacing=True)
    assert "shared databases" in _kept_why({"/depot/lab/margie/databases/x"}, home, code, group, replacing=True)
    assert _kept_why({"/scratch/c/u/margie/.margie"}, home, code, group, replacing=True) == ""


def _remote(calls, sbatch=(0, "4242\n"), size=1000):
    def run(conn, command):
        calls.append(command)
        if command.startswith("test -d"):
            return (0, "")
        if "sbatch" in command:
            return sbatch
        if command.startswith("du -sb"):
            return (0, f"{size}\n")
        if "setsid nohup" in command:
            return (0, "started")
        return (0, "")
    return run


@patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"compute": {"cluster_default": {"account": "mylab", "partition": "cpu"}}})
@patch(f"{SSH}.ssh_sftp.write_remote_text_file")
@patch(f"{SSH}._build_connection")
def test_it_goes_to_slurm_with_the_account_partition_and_16_cores(_conn, written, _yaml, authed_client):  # noqa: F811
    calls = []
    with patch(f"{SSH}._run_remote_check", side_effect=_remote(calls)):
        d = authed_client.post(ROUTE, json={"op": "copy", "sources": ["/s/a.tsv", "/s/run"], "into": "/d"}).json()
    assert d["where"] == "slurm" and d["job"] == "4242" and d["state"] == "queued"
    sb = next(c for c in calls if "sbatch" in c)
    assert "--account=mylab" in sb and "--partition=cpu" in sb and "--cpus-per-task=16" in sb
    plan = next(c.args[1] for c in written.call_args_list if c.args[0].endswith("/plan"))
    assert plan == "copy\t/s/a.tsv\t/d/a.tsv\ncopy\t/s/run\t/d/run\n"


@patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"compute": {"cluster_default": {"account": "mylab"}}})
@patch(f"{SSH}.ssh_sftp.write_remote_text_file")
@patch(f"{SSH}._build_connection")
def test_a_replace_marks_each_line_and_keeps_margies_keys(_conn, written, _yaml, authed_client):  # noqa: F811
    calls = []
    home = FAKE_USER["home_dir"]
    with patch(f"{SSH}._run_remote_check", side_effect=_remote(calls)):
        authed_client.post(ROUTE, json={"op": "copy", "sources": ["/s/a.tsv", "/s/.ssh"], "into": home, "replace": True})
    plan = next(c.args[1] for c in written.call_args_list if c.args[0].endswith("/plan"))
    assert plan == f"copy\t/s/a.tsv\t{home}/a.tsv\treplace\ncopy\t/s/.ssh\t{home}/.ssh\tkept\n"
    meta = json.loads(next(c.args[1] for c in written.call_args_list if c.args[0].endswith("/meta.json")))
    assert "MARGIE's own" in meta["items"][1]["kept"]


@patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"compute": {"cluster_default": {"account": "mylab"}}})
@patch(f"{SSH}.ssh_sftp.write_remote_text_file")
@patch(f"{SSH}._build_connection")
def test_without_slurm_it_runs_on_the_login_node(_conn, _written, _yaml, authed_client):  # noqa: F811
    calls = []
    with patch(f"{SSH}._run_remote_check", side_effect=_remote(calls, sbatch=(1, "sbatch: error: invalid account"))):
        d = authed_client.post(ROUTE, json={"op": "move", "sources": ["/s/a.tsv"], "into": "/d"}).json()
    assert d["where"] == "login" and d["job"] is None
    assert any("setsid nohup bash run.sh" in c and c.rstrip().endswith("& echo started") for c in calls)


@patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"compute": {"cluster_default": {"account": "mylab"}}})
@patch(f"{SSH}.ssh_sftp.write_remote_text_file")
@patch(f"{SSH}._build_connection")
def test_without_slurm_a_transfer_over_500_mb_is_refused(_conn, _written, _yaml, authed_client):  # noqa: F811
    calls = []
    with patch(f"{SSH}._run_remote_check", side_effect=_remote(calls, sbatch=(1, "sbatch: error: invalid account"), size=600 * 1024 * 1024)):
        r = authed_client.post(ROUTE, json={"op": "copy", "sources": ["/s/big"], "into": "/d"})
    assert r.status_code == 409 and "500.0 MB" in r.json()["detail"]
    assert not any("setsid nohup bash run.sh" in c for c in calls)


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
