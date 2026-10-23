"""A run's watcher ends with its run (ssh_slurm.submit_ssh_job): when MARGIE cancels it, and when its
SLURM driver job has gone without writing an exit code. A watcher that outlived its run held one of
the API's few threads for good, so later runs waited in "initialising" for a thread that never came."""

import socket
from unittest.mock import MagicMock

from bioinformatics_tools.utilities import ssh_slurm


def _connection(driver_listed: bool):
    """A connection whose launch prints driver job 4242, whose log tail stays silent, which has no
    exit code file, and whose squeue lists the driver or not."""
    launch_out = MagicMock()
    launch_out.readline.return_value = "4242\n"
    tail_out = MagicMock()
    tail_out.channel.recv.side_effect = socket.timeout("quiet")
    squeue_out = MagicMock()
    squeue_out.read.return_value = (b"4242\n" if driver_listed else b"") + b"__END__\n"

    def exec_command(cmd, *a, **k):
        if cmd.startswith("tail "):
            return None, tail_out, MagicMock()
        if cmd.startswith("squeue "):
            return None, squeue_out, MagicMock()
        return None, launch_out, MagicMock()

    sftp = MagicMock()

    def sftp_open(path, mode="r"):
        if path.endswith(".jobid"):
            fh = MagicMock()
            fh.__enter__.return_value.read.return_value = b"4242\n"
            return fh
        raise IOError("no exit code yet")

    sftp.open.side_effect = sftp_open
    ssh = MagicMock()
    ssh.exec_command.side_effect = exec_command
    ssh.open_sftp.return_value = sftp
    conn = MagicMock()
    conn.connect.return_value = ssh
    return conn


def _clock(monkeypatch):
    """Time that moves a minute and a half on each look, so the minute-apart driver checks run at once."""
    now = [1_000_000.0]

    def tick():
        now[0] += 90.0
        return now[0]

    monkeypatch.setattr(ssh_slurm.time, "time", tick)


def test_a_cancelled_run_stops_being_watched():
    gen = ssh_slurm.submit_ssh_job(cmd="dane_wf margie sb", connection=_connection(True), job_id="j1",
                                   in_slurm=True, stop=lambda: True)
    assert list(gen)[-1] == "__DETACHED__"


def test_a_driver_gone_without_an_exit_code_ends_the_watch(monkeypatch):
    _clock(monkeypatch)
    gen = ssh_slurm.submit_ssh_job(cmd="dane_wf margie sb", connection=_connection(False), job_id="j2",
                                   in_slurm=True, stop=lambda: False)
    assert list(gen)[-1] == "__ENDED_UNFINISHED__"


def test_a_driver_still_queued_keeps_being_watched(monkeypatch):
    _clock(monkeypatch)
    looks = [0]

    def stop():
        looks[0] += 1
        return looks[0] > 6          # a few checks, then the test lets it go

    gen = ssh_slurm.submit_ssh_job(cmd="dane_wf margie sb", connection=_connection(True), job_id="j3",
                                   in_slurm=True, stop=stop)
    assert list(gen)[-1] == "__DETACHED__"
    assert looks[0] > 6
