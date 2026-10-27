"""
Copies of the slow cluster answers (the job list, the Results folders) kept in the user's working
folder, <working folder>/.margie/site-cache/<name>-<key>.json, as read_cache's backup: an API that
has just started (a deploy, a restart) answers from them at once and asks the cluster again in
the background. Read and written over the user's own connection.
"""

from __future__ import annotations

import hashlib
import json
import logging

from bioinformatics_tools.api.services import user_stores
from bioinformatics_tools.utilities import ssh_sftp

LOGGER = logging.getLogger(__name__)

# The working folder of each user, found once per API process (config.yaml, else scratch).
_folders: dict = {}


def folder(conn, user: dict) -> str:
    """The user's site-cache folder in the working folder."""
    if user["user_id"] not in _folders:
        cfg = ssh_sftp.read_remote_yaml(f"{user['home_dir']}/.config/bioinformatics-tools/config.yaml", connection=conn)
        _folders[user["user_id"]] = f"{user_stores.working_folder(conn, cfg)}/.margie/site-cache"
    return _folders[user["user_id"]]


def backup(conn, user: dict, key: tuple) -> tuple:
    """read_cache's (load, save) for key: the copy kept under the working folder."""
    digest = hashlib.sha256(repr(key[1:]).encode()).hexdigest()
    name = f"{key[1]}-{digest}.json"

    def load():
        path = f"{folder(conn, user)}/{name}"
        sftp = conn.connect().open_sftp()
        try:
            with sftp.open(path, "rb") as fh:
                fh.prefetch(max_concurrent_requests=ssh_sftp.PREFETCH_BLOCKS)
                return json.loads(fh.read().decode())
        except FileNotFoundError:
            return None
        finally:
            sftp.close()

    def save(value) -> None:
        ssh_sftp.write_remote_text_file(f"{folder(conn, user)}/{name}", json.dumps(value), connection=conn)

    return load, save
