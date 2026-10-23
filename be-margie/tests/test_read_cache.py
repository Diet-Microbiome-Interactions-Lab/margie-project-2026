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
