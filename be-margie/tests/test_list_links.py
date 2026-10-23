"""The file browser's listing: a link takes its target's kind, so a linked folder opens as a folder."""

import stat
from types import SimpleNamespace
from unittest.mock import MagicMock

from bioinformatics_tools.utilities.ssh_sftp import list_remote_dir_checked


def _attr(name, mode, size=0):
    return SimpleNamespace(filename=name, st_mode=mode, st_size=size, st_mtime=0)


def test_links_take_their_targets_kind():
    sftp = MagicMock()
    targets = {"/home/u/tools": _attr("tools", stat.S_IFDIR | 0o755, 4096), "/home/u/data.tsv": _attr("data.tsv", stat.S_IFREG | 0o644, 99)}

    def fake_stat(path):
        if path == "/home/u":
            return _attr("u", stat.S_IFDIR | 0o755)
        if path in targets:
            return targets[path]
        raise FileNotFoundError(path)

    sftp.stat.side_effect = fake_stat
    sftp.listdir_attr.return_value = [
        _attr("tools", stat.S_IFLNK | 0o777),
        _attr("data.tsv", stat.S_IFLNK | 0o777),
        _attr("broken", stat.S_IFLNK | 0o777),
        _attr("plain", stat.S_IFDIR | 0o755),
    ]
    conn = MagicMock()
    conn.connect.return_value.open_sftp.return_value = sftp
    got = {e["name"]: (e["type"], e["size"]) for e in list_remote_dir_checked("/home/u", conn)}
    assert got == {"tools": ("directory", 4096), "data.tsv": ("file", 99), "broken": ("file", 0), "plain": ("directory", 0)}
