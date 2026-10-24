"""A first visit: a missing config.yaml stays missing, so Settings offers the default config."""

from unittest.mock import patch

from bioinformatics_tools.api.services import read_cache
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

SSH = "bioinformatics_tools.api.routers.ssh"


@patch(f"{SSH}._build_connection")
def test_a_missing_config_is_read_as_empty_and_not_written(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={}), \
         patch(f"{SSH}.user_stores.fill_default_folders") as fill, \
         patch(f"{SSH}.ssh_sftp.write_remote_yaml") as write:
        assert authed_client.get("/v1/ssh/config").json() == {}
    fill.assert_not_called()
    write.assert_not_called()


@patch(f"{SSH}._build_connection")
def test_an_existing_config_gets_its_empty_folders_filled(_conn, authed_client):  # noqa: F811
    read_cache.drop(FAKE_USER["user_id"])
    with patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"margie_sb": {"threads": 4}}), \
         patch(f"{SSH}.user_stores.fill_default_folders", return_value=True), \
         patch(f"{SSH}.user_stores.fill_default_partition", return_value=False), \
         patch(f"{SSH}.ssh_sftp.write_remote_yaml") as write:
        authed_client.get("/v1/ssh/config")
    write.assert_called_once()
