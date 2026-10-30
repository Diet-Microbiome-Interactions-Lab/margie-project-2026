"""
Unit tests for bioinformatics_tools.utilities.ssh_sftp, with the SSHConnection's
paramiko client mocked (no network).
"""
import shlex
import stat as stat_module
from unittest.mock import MagicMock

import pytest

from bioinformatics_tools.utilities import ssh_sftp


def _mock_connection_for_exec(exec_stdout: bytes, exec_stderr: bytes = b""):
    """Builds an SSHConnection mock whose SFTP stat() reports a regular file and
    whose exec_command() returns the given output."""
    mock_ssh = MagicMock()

    mock_sftp_client = MagicMock()
    mock_stat_result = MagicMock()
    mock_stat_result.st_mode = stat_module.S_IFREG | 0o644  # regular file
    mock_sftp_client.stat.return_value = mock_stat_result
    mock_ssh.open_sftp.return_value = mock_sftp_client

    mock_stdout = MagicMock()
    mock_stdout.read.return_value = exec_stdout
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = exec_stderr
    mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)

    mock_connection = MagicMock()
    mock_connection.connect.return_value = mock_ssh
    return mock_connection, mock_ssh


class TestReadRemoteFilePage:
    def test_escapes_path_with_shell_metacharacters(self):
        """Checks that a path with spaces and parentheses is shell-quoted in the remote command."""
        sentinel = ssh_sftp._PAGE_SENTINEL
        stdout = (
            f"3\n{sentinel}\ncol_a\tcol_b\n{sentinel}\nval1\tval2\n"
        ).encode()
        dangerous_path = "/work/dir/interpro results (final).tsv"
        mock_connection, mock_ssh = _mock_connection_for_exec(stdout)

        result = ssh_sftp.read_remote_file_page(
            dangerous_path, start_row=2, end_row=2, connection=mock_connection,
        )

        command = mock_ssh.exec_command.call_args[0][0]
        quoted = shlex.quote(dangerous_path)
        # One quoted use each for wc, the header sed and the range sed.
        assert command.count(quoted) == 3

        assert result == {
            "total_lines": 3,
            "header": "col_a\tcol_b",
            "lines": ["val1\tval2"],
        }

    def test_skips_wc_when_total_lines_known(self):
        """Checks that known_total_lines skips the wc -l pass."""
        sentinel = ssh_sftp._PAGE_SENTINEL
        stdout = f"col_a\tcol_b\n{sentinel}\nval1\tval2\n".encode()
        mock_connection, mock_ssh = _mock_connection_for_exec(stdout)

        result = ssh_sftp.read_remote_file_page(
            "/work/dir/results.tsv", start_row=2, end_row=2,
            connection=mock_connection, known_total_lines=42,
        )

        command = mock_ssh.exec_command.call_args[0][0]
        assert "wc -l" not in command
        assert result["total_lines"] == 42
        assert result["header"] == "col_a\tcol_b"
        assert result["lines"] == ["val1\tval2"]

    def test_print_before_quit_keeps_last_row_of_page(self):
        """Checks the sed range is `START,ENDp;ENDq`, so the last row prints before sed quits."""
        sentinel = ssh_sftp._PAGE_SENTINEL
        stdout = f"42\n{sentinel}\nh\n{sentinel}\nrow2\trow2b\nrow3\trow3b\n".encode()
        mock_connection, mock_ssh = _mock_connection_for_exec(stdout)

        ssh_sftp.read_remote_file_page(
            "/work/dir/results.tsv", start_row=2, end_row=3, connection=mock_connection,
        )

        command = mock_ssh.exec_command.call_args[0][0]
        assert "2,3p;3q" in command

    def test_empty_page_past_end_of_file(self):
        """Checks that a page beyond EOF returns an empty page."""
        sentinel = ssh_sftp._PAGE_SENTINEL
        stdout = f"3\n{sentinel}\ncol_a\n{sentinel}\n".encode()
        mock_connection, _ = _mock_connection_for_exec(stdout)

        result = ssh_sftp.read_remote_file_page(
            "/work/dir/results.tsv", start_row=100, end_row=199, connection=mock_connection,
        )

        assert result["total_lines"] == 3
        assert result["lines"] == []
