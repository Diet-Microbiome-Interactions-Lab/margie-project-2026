"""Files come from the cluster with every block asked for at once (SFTPFile.prefetch) and read in
256 KB pieces: read one 8 KB block at a time, an 880 KB figure took 6.3 s, prefetched 0.5 s."""

from unittest.mock import MagicMock

from bioinformatics_tools.utilities.ssh_sftp import stream_remote_file


def test_a_file_streams_prefetched_in_large_pieces():
    f = MagicMock()
    f.read.side_effect = [b'a' * 262144, b'b' * 10, b'']
    conn = MagicMock()
    conn.connect.return_value.open_sftp.return_value.open.return_value = f
    assert b''.join(stream_remote_file('/x/fig.png', connection=conn)) == b'a' * 262144 + b'b' * 10
    f.prefetch.assert_called_once_with(max_concurrent_requests=64)
    assert {c.args[0] for c in f.read.call_args_list} == {262144}
