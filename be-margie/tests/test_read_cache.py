"""Short-lived answers to slow reads: reused while fresh, returned while refreshed, dropped by changes."""

import threading
import time
from unittest.mock import patch

from bioinformatics_tools.api.services import read_cache
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)


def setup_function():
    read_cache._answers.clear()


def test_a_fresh_answer_is_reused():
    calls = []
    ask = lambda: calls.append(1) or len(calls)  # noqa: E731
    assert read_cache.get((1, "jobs"), ask) == 1
    assert read_cache.get((1, "jobs"), ask) == 1
    assert len(calls) == 1


def test_a_stale_answer_comes_back_at_once_and_is_refreshed():
    done = threading.Event()

    def ask():
        done.set()
        return "new"

    read_cache._answers[(1, "jobs")] = (time.monotonic() - 30, "old")
    assert read_cache.get((1, "jobs"), ask, fresh=5, stale=120) == "old"
    assert done.wait(2)
    time.sleep(0.05)
    assert read_cache._answers[(1, "jobs")][1] == "new"


def test_an_old_answer_is_asked_for_again():
    read_cache._answers[(1, "config")] = (time.monotonic() - 500, "old")
    assert read_cache.get((1, "config"), lambda: "new") == "new"


def test_errors_are_not_kept():
    def boom():
        raise RuntimeError("cluster unreachable")

    try:
        read_cache.get((1, "stores"), boom)
    except RuntimeError:
        pass
    assert (1, "stores") not in read_cache._answers


def test_drop_forgets_one_users_answers():
    read_cache._answers.update({(1, "jobs"): (time.monotonic(), 1), (1, "config"): (time.monotonic(), 2), (2, "jobs"): (time.monotonic(), 3)})
    read_cache.drop(1, "jobs")
    assert (1, "jobs") not in read_cache._answers and (1, "config") in read_cache._answers
    read_cache.drop(1)
    assert list(read_cache._answers) == [(2, "jobs")]


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
def test_a_change_through_the_api_drops_the_users_reads(_conn, authed_client):  # noqa: F811
    read_cache._answers[(FAKE_USER["user_id"], "config")] = (time.monotonic(), {"stale": True})
    from bioinformatics_tools.api.auth import create_access_token

    token = create_access_token(FAKE_USER["user_id"], FAKE_USER["username"])
    with patch("bioinformatics_tools.api.routers.ssh.ssh_sftp.write_remote_yaml"):
        authed_client.put("/v1/ssh/config", json={"a": 1}, headers={"Authorization": f"Bearer {token}"})
    assert (FAKE_USER["user_id"], "config") not in read_cache._answers


@patch("bioinformatics_tools.api.routers.ssh._build_connection")
def test_config_reads_are_reused(_conn, authed_client):  # noqa: F811
    with patch("bioinformatics_tools.api.routers.ssh.ssh_sftp.read_remote_yaml", return_value={"a": 1}) as read:
        assert authed_client.get("/v1/ssh/config").json() == {"a": 1}
        assert authed_client.get("/v1/ssh/config").json() == {"a": 1}
    assert read.call_count == 1


def test_readers_meanwhile_wait_for_the_same_answer():
    calls, release = [], threading.Event()

    def ask():
        calls.append(1)
        release.wait(2)
        return "answer"

    got = []
    readers = [threading.Thread(target=lambda: got.append(read_cache.get((1, "jobs"), ask))) for _ in range(5)]
    for t in readers:
        t.start()
    time.sleep(0.1)
    release.set()
    for t in readers:
        t.join(2)
    assert got == ["answer"] * 5 and len(calls) == 1


def test_an_answer_asked_for_before_a_drop_is_not_kept():
    def ask():
        read_cache.drop(1, "config_file")  # a change lands while the cluster answers
        return {"old": True}

    assert read_cache.get((1, "config_file"), ask) == {"old": True}
    assert (1, "config_file") not in read_cache._answers
    assert read_cache.get((1, "config_file"), lambda: {"new": True}) == {"new": True}


@patch("bioinformatics_tools.api.routers.ssh.ssh_sftp.read_remote_yaml", return_value={"margie_sb": {"a": 1}})
def test_the_job_pages_share_one_read_of_config_yaml_and_change_their_own_copy(read):
    from bioinformatics_tools.api.routers import ssh

    first = ssh._read_config(FAKE_USER, conn=None)
    first["margie_sb"]["a"] = 2
    assert ssh._read_config(FAKE_USER, conn=None) == {"margie_sb": {"a": 1}}
    assert read.call_count == 1
    with patch("bioinformatics_tools.api.routers.ssh.ssh_sftp.write_remote_yaml"):
        ssh._write_config(FAKE_USER, first, conn=None)
    ssh._read_config(FAKE_USER, conn=None)
    assert read.call_count == 2
