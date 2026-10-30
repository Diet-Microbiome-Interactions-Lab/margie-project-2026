"""A remote command's output is read before its exit status: over SSH, a command with more to say
than the channel's window (about 2 MB, as Results' listing of a dozen runs) waits for it to be read
before it ends, so asking for the exit status first waits for good."""
from unittest.mock import MagicMock

import pytest

from bioinformatics_tools.api.routers import ssh
from bioinformatics_tools.api.services import cluster_llm, genome_chat, user_stores


class _Out:
    """A command's stdout whose exit status is only told once its output has been read."""

    def __init__(self):
        self.was_read = False
        self.channel = MagicMock()
        self.channel.recv_exit_status.side_effect = self._status

    def _status(self):
        assert self.was_read, 'the exit status was asked for before the output was read'
        return 0

    def read(self):
        self.was_read = True
        return b'x' * 3_000_000


def _conn():
    conn = MagicMock()
    conn.connect.return_value.exec_command.return_value = (MagicMock(), _Out(), MagicMock(read=lambda: b''))
    return conn


@pytest.mark.parametrize('run', [ssh._run_remote_check, user_stores._run, genome_chat._run, cluster_llm._run])
def test_the_output_is_read_first(run):
    code, out = run(_conn(), 'find big')
    assert code == 0 and len(out) == 3_000_000
