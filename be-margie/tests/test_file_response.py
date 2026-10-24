"""Cluster files for the Results page (api/routers/ssh.py, _file_response): text gzipped when the browser
takes it, an ETag from size and modification time so a repeat visit is a 304, and each job's folder
looked up once."""

import asyncio
import gzip
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.routers import ssh

SSH = "bioinformatics_tools.api.routers.ssh"


def _conn(size=8_000_000, mtime=1_760_000_000):
    conn = MagicMock()
    conn.connect.return_value.open_sftp.return_value.stat.return_value = SimpleNamespace(st_size=size, st_mtime=mtime)
    return conn


def _request(**headers):
    return SimpleNamespace(headers={k.replace('_', '-'): v for k, v in headers.items()})


async def _collect(response) -> bytes:
    return b"".join([c async for c in response.body_iterator])


def test_a_map_goes_gzipped():
    body = b"<html>" + b"gene " * 20000 + b"</html>"
    with patch(f"{SSH}.ssh_sftp.stream_remote_file", return_value=iter([body[:50000], body[50000:]])):
        r = ssh._file_response(_request(accept_encoding="gzip, br"), _conn(len(body)), "/r/FINAL_GENOME_VIEWER.html", "FINAL_GENOME_VIEWER.html")
        sent = asyncio.run(_collect(r))
    assert r.headers["content-encoding"] == "gzip"
    assert gzip.decompress(sent) == body
    assert len(sent) < len(body) // 5


def test_an_unchanged_file_is_a_304():
    conn = _conn()
    with patch(f"{SSH}.ssh_sftp.stream_remote_file") as stream:
        first = ssh._file_response(_request(accept_encoding="gzip"), conn, "/r/fig.png", "fig.png")
        again = ssh._file_response(_request(accept_encoding="gzip", if_none_match=first.headers["etag"]), conn, "/r/fig.png", "fig.png")
    assert again.status_code == 304
    assert stream.call_count == 1  # the second visit reads nothing


def test_a_figure_goes_as_it_is_with_its_length():
    with patch(f"{SSH}.ssh_sftp.stream_remote_file", return_value=iter([b"png"])):
        r = ssh._file_response(_request(accept_encoding="gzip"), _conn(size=3), "/r/fig.png", "fig.png")
    assert "content-encoding" not in r.headers
    assert r.headers["content-length"] == "3"
    assert r.headers["cache-control"] == "private, no-cache"


def test_a_jobs_folder_is_looked_up_once():
    user = {"user_id": 7, "home_dir": "/home/u", "username": "u", "cluster_username": "u"}
    ssh._history_work_dirs.clear()
    with patch(f"{SSH}.job_store.get", return_value=None), \
            patch(f"{SSH}.ssh_sftp.read_remote_yaml", return_value={"main_database": "/db.sqlite"}) as cfg, \
            patch(f"{SSH}.job_history_client.get_job", return_value={"work_dir": "/scratch/run"}) as hist:
        assert ssh._resolve_job_work_dir("job-1", user, MagicMock()) == "/scratch/run"
        assert ssh._resolve_job_work_dir("job-1", user, MagicMock()) == "/scratch/run"
    assert cfg.call_count == 1 and hist.call_count == 1
