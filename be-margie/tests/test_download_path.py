"""Downloads from the Files page: a path's size first, then the file whole or the folder zipped."""

from unittest.mock import MagicMock, patch

import pytest

from bioinformatics_tools.api.routers.ssh import _archive_command, _attachment, _parse_path_size
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)


def test_a_folder_size_is_read_from_du_and_find():
    assert _parse_path_size("d\n123456\n42\n") == {"kind": "directory", "bytes": 123456, "files": 42}
    assert _parse_path_size("f\n99\n1\n") == {"kind": "file", "bytes": 99, "files": 1}


def test_a_missing_path_has_no_size():
    with pytest.raises(FileNotFoundError):
        _parse_path_size("missing\n")


def test_a_folder_is_zipped_or_else_tarred():
    cmd, name, media = _archive_command("/scratch/u", "run 1", True)
    assert cmd.startswith("cd /scratch/u && zip -r -q - 'run 1'")
    assert (name, media) == ("run 1.zip", "application/zip")
    cmd, name, media = _archive_command("/scratch/u", "run1", False)
    assert cmd.startswith("tar -C /scratch/u -czf - run1")
    assert (name, media) == ("run1.tar.gz", "application/gzip")


def test_the_file_name_cannot_break_the_header():
    assert _attachment('a"b\\c.zip') == {"Content-Disposition": 'attachment; filename="abc.zip"'}


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh._run_remote_check", return_value=(0, "d\n2048\n3\n"))
def test_the_size_route(_check, _conn, authed_client):  # noqa: F811
    d = authed_client.get("/v1/ssh/path_size", params={"path": "/scratch/u/run"}).json()
    assert d["kind"] == "directory" and d["bytes"] == 2048 and d["files"] == 3


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
@patch("bioinformatics_tools.api.routers.ssh._run_remote_check", return_value=(0, ""))
@patch("bioinformatics_tools.api.routers.ssh.ssh_sftp.check_remote_path_kind", return_value="directory")
def test_a_folder_streams_as_a_zip(_kind, _check, conn, authed_client):  # noqa: F811
    stdout = MagicMock()
    stdout.read.side_effect = [b"PK\x03\x04", b"rest", b""]
    conn.return_value.connect.return_value.exec_command.return_value = (None, stdout, None)
    r = authed_client.get("/v1/ssh/download_path", params={"path": "/scratch/u/run"})
    assert r.status_code == 200
    assert r.content == b"PK\x03\x04rest"
    assert r.headers["content-disposition"] == 'attachment; filename="run.zip"'
    assert "zip -r -q - run" in conn.return_value.connect.return_value.exec_command.call_args[0][0]
