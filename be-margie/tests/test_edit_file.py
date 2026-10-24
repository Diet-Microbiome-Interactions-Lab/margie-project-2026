"""Settings → Advanced: editing config.yaml and the workflow by hand, checked and kept."""

from unittest.mock import patch

from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

ROUTE = "/v1/ssh/edit_file"
SSH = "bioinformatics_tools.api.routers.ssh"


@patch(f"{SSH}._build_connection")
def test_broken_yaml_is_refused_and_nothing_written(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}.ssh_sftp.write_remote_text_file") as write:
        r = authed_client.post(ROUTE, json={"path": "~/.config/bioinformatics-tools/config.yaml", "content": "a: [1, 2\nb: 3", "check": "yaml"})
    assert r.status_code == 400 and "not valid YAML" in r.json()["detail"] and "line" in r.json()["detail"]
    write.assert_not_called()


@patch(f"{SSH}._build_connection")
def test_yaml_must_be_a_mapping(_conn, authed_client):  # noqa: F811
    r = authed_client.post(ROUTE, json={"path": "~/c.yaml", "content": "- just\n- a list\n", "check": "yaml"})
    assert r.status_code == 400 and "mapping" in r.json()["detail"]


@patch(f"{SSH}._build_connection")
def test_the_old_version_is_kept_beside_it(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, "KEPT")) as run, patch(f"{SSH}.ssh_sftp.write_remote_text_file") as write:
        d = authed_client.post(ROUTE, json={"path": "~/bioinformatics-tools/x/margie_sb.smk", "content": "rule all:\n    input: []\n"}).json()
    assert d["path"] == "/home/testuser/bioinformatics-tools/x/margie_sb.smk"
    assert d["backup"].startswith(d["path"] + ".bak-")
    assert "cp -p --" in run.call_args[0][1]
    write.assert_called_once()
    assert write.call_args[0][0] == d["path"]


# ---- putting the defaults back ----

RESTORE = "/v1/ssh/restore_default"


@patch(f"{SSH}._build_connection")
def test_restoring_the_config_keeps_yours_and_writes_the_default(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, "KEPT")) as run, patch(f"{SSH}.ssh_sftp.write_remote_text_file") as write:
        d = authed_client.post(RESTORE, json={"which": "config"}).json()
    assert d["path"].endswith("/.config/bioinformatics-tools/config.yaml")
    assert d["backup"].startswith(d["path"] + ".bak-") and "cp -p --" in run.call_args[0][1]
    assert write.call_args[0][0] == d["path"] and "margie_sb" in write.call_args[0][1]


@patch(f"{SSH}._build_connection")
def test_restoring_the_workflow_takes_it_back_from_git(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, "KEPT\nRESTORED")) as run, patch(f"{SSH}.ssh_sftp.write_remote_text_file") as write:
        d = authed_client.post(RESTORE, json={"which": "workflow"}).json()
    command = run.call_args[0][1]
    assert d["path"] == "/home/testuser/bioinformatics-tools/bioinformatics_tools/workflow_tools/margie_sb.smk"
    assert "cp -p --" in command and "git checkout -- margie_sb.smk" in command and d["backup"]
    write.assert_not_called()


@patch(f"{SSH}._build_connection")
def test_a_workflow_that_git_cannot_restore_is_an_error(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(128, "fatal: not a git repository")):
        r = authed_client.post(RESTORE, json={"which": "workflow"})
    assert r.status_code == 500 and "not a git repository" in r.json()["detail"]


@patch(f"{SSH}._build_connection")
def test_only_the_config_or_the_workflow_is_restored(_conn, authed_client):  # noqa: F811
    assert authed_client.post(RESTORE, json={"which": "/etc/passwd"}).status_code == 400


@patch(f"{SSH}._build_connection")
def test_settings_learns_when_the_workflow_has_edits(_conn, authed_client):  # noqa: F811
    with patch(f"{SSH}._run_remote_check", return_value=(0, " M margie_sb.smk\n")):
        assert authed_client.get("/v1/ssh/advanced_files").json()["workflow_edited"] is True
    with patch(f"{SSH}._run_remote_check", return_value=(0, "")):
        assert authed_client.get("/v1/ssh/advanced_files").json()["workflow_edited"] is False
