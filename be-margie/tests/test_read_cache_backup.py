"""An answer with a backup (scratch_cache, a copy kept in the working folder): an API with nothing
in memory answers from the copy at once and asks the cluster again in the background; each fresh
answer is saved to the copy; after drop() (a write) the copy waits for a fresh answer. The
cluster's helper for the job list loads without the API app (it took 2 s and the secret keys)."""

import os
import subprocess
import sys
import threading
import time

from bioinformatics_tools.api.services import read_cache


def _wait(cond, seconds=3.0):
    end = time.time() + seconds
    while time.time() < end and not cond():
        time.sleep(0.02)
    return cond()


def test_a_cold_start_answers_from_the_copy_then_asks_again():
    saved, asked = [], threading.Event()
    key = (901, "jobs", None, 1, 50)
    read_cache.drop(901)
    read_cache._dropped.discard((901, "jobs"))

    def ask():
        asked.set()
        return {"jobs": ["fresh"]}

    got = read_cache.get(key, ask, backup=(lambda: {"jobs": ["kept"]}, saved.append))
    assert got == {"jobs": ["kept"]}
    assert _wait(asked.is_set) and _wait(lambda: saved == [{"jobs": ["fresh"]}])
    assert read_cache.get(key, lambda: {"jobs": ["again"]}) == {"jobs": ["fresh"]}


def test_after_a_write_the_copy_waits_for_a_fresh_answer():
    key = (902, "jobs", None, 1, 50)
    read_cache.get(key, lambda: {"jobs": ["one"]})
    read_cache.drop(902, "jobs")
    got = read_cache.get(key, lambda: {"jobs": []}, backup=(lambda: {"jobs": ["old"]}, lambda v: None))
    assert got == {"jobs": []}


def test_the_job_history_helper_loads_without_the_api_app():
    env = {k: v for k, v in os.environ.items() if k not in ("BSP_SECRET_KEY", "BSP_ENCRYPTION_KEY")}
    code = ("import sys, bioinformatics_tools.api.services.job_history; "
            "sys.exit('bioinformatics_tools.api.main' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code], env=env, timeout=60).returncode == 0


# The real backup, imported before conftest switches it off for the request tests.
from unittest.mock import MagicMock, patch  # noqa: E402

from bioinformatics_tools.api.services import scratch_cache  # noqa: E402
from bioinformatics_tools.api.services.scratch_cache import backup as real_backup  # noqa: E402


def test_the_copy_is_a_json_file_in_the_working_folder():
    user = {"user_id": 903, "home_dir": "/home/u"}
    scratch_cache._folders[903] = "/scratch/c/u/margie/.margie/site-cache"
    conn = MagicMock()
    fh = conn.connect.return_value.open_sftp.return_value.open.return_value.__enter__.return_value
    fh.read.return_value = b'{"jobs": ["kept"]}'
    load, save = real_backup(conn, user, (903, "jobs", None, 1, 50))
    assert load() == {"jobs": ["kept"]}
    opened = conn.connect.return_value.open_sftp.return_value.open.call_args[0][0]
    assert opened.startswith("/scratch/c/u/margie/.margie/site-cache/jobs-") and opened.endswith(".json")
    with patch("bioinformatics_tools.api.services.scratch_cache.ssh_sftp.write_remote_text_file") as write:
        save({"jobs": ["fresh"]})
    assert write.call_args[0][0] == opened and write.call_args[0][1] == '{"jobs": ["fresh"]}'
