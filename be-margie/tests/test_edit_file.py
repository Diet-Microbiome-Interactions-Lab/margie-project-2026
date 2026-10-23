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
