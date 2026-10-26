"""
The hosting server's own use while a run goes, added to the run's resource report
(workflow_tools/usage_report.py) for the accounts MARGIE_HOSTING_USAGE_USERS names (site or cluster
user names, comma separated); MARGIE_HOSTING_NAME names the server in the report. Other accounts' reports show their
cluster use alone.

snapshot() reads the server's counters (CPU time, memory, disk and network bytes) from its cgroup
and network interfaces; the run's launch keeps one in the job (hosting_start), and when the run
ends add_to_report() takes the difference, renders the PDF again with it from the run's
usage.json and adds a row to hosting.tsv beside it. A server restarted during the run counts from
its restart. Failures are logged; the run's result stands.
"""

import io
import json
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path

from bioinformatics_tools.api.database import get_db
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.utilities.ssh_slurm import RUN_FILE_DIR, run_file_stem
from bioinformatics_tools.workflow_tools import usage_report

LOGGER = logging.getLogger(__name__)

USERS_ENV = 'MARGIE_HOSTING_USAGE_USERS'
NAME_ENV = 'MARGIE_HOSTING_NAME'
CGROUP = Path('/sys/fs/cgroup')
NET = Path('/sys/class/net')


def enabled(*names: str | None) -> bool:
    """Whether an account, by its site or cluster user name, gets the hosting section."""
    users = {u.strip() for u in os.environ.get(USERS_ENV, '').split(',') if u.strip()}
    return any(n and n in users for n in names)


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ''


def _int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return 0


def _first(*paths: Path) -> str:
    return next((v for v in (_read(p) for p in paths) if v), '')


def snapshot() -> dict:
    """The server's counters now: cgroup v2, else v1; zeros where the host has none."""
    cpu_ns = 0
    stat = _read(CGROUP / 'cpu.stat')
    if stat:
        cpu_ns = 1000 * _int(next((ln.split()[1] for ln in stat.splitlines() if ln.startswith('usage_usec')), '0'))
    else:
        cpu_ns = _int(_first(CGROUP / 'cpu,cpuacct' / 'cpuacct.usage', CGROUP / 'cpuacct' / 'cpuacct.usage'))
    cpu_limit = 0.0
    quota = _read(CGROUP / 'cpu.max').split()
    if len(quota) == 2 and quota[0] != 'max':
        cpu_limit = _int(quota[0]) / max(1, _int(quota[1]))
    elif not quota:
        q = _int(_first(CGROUP / 'cpu,cpuacct' / 'cpu.cfs_quota_us', CGROUP / 'cpu' / 'cpu.cfs_quota_us') or '0')
        p = _int(_first(CGROUP / 'cpu,cpuacct' / 'cpu.cfs_period_us', CGROUP / 'cpu' / 'cpu.cfs_period_us') or '0')
        cpu_limit = q / p if q > 0 and p else 0.0
    mem = CGROUP / 'memory'
    mem_now = _int(_first(CGROUP / 'memory.current', mem / 'memory.usage_in_bytes'))
    mem_peak = _int(_first(CGROUP / 'memory.peak', mem / 'memory.max_usage_in_bytes'))
    mem_limit = _int(_first(CGROUP / 'memory.max', mem / 'memory.limit_in_bytes'))
    # cgroup v1 reports "no limit" as a huge number.
    mem_limit = mem_limit if 0 < mem_limit < 1 << 50 else 0
    io_read = io_write = 0
    for line in _read(CGROUP / 'io.stat').splitlines():
        fields = dict(f.split('=', 1) for f in line.split()[1:] if '=' in f)
        io_read += _int(fields.get('rbytes', '0'))
        io_write += _int(fields.get('wbytes', '0'))
    for line in _read(CGROUP / 'blkio' / 'blkio.throttle.io_service_bytes').splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == 'Read':
            io_read += _int(parts[2])
        elif len(parts) == 3 and parts[1] == 'Write':
            io_write += _int(parts[2])
    rx = tx = 0
    try:
        for dev in NET.iterdir():
            if dev.name != 'lo':
                rx += _int(_read(dev / 'statistics' / 'rx_bytes'))
                tx += _int(_read(dev / 'statistics' / 'tx_bytes'))
    except OSError:
        pass
    return {'at': datetime.now().astimezone().isoformat(timespec='seconds'), 'epoch': time.time(), 'boot': BOOT_EPOCH,
            'host': socket.gethostname(), 'cpu_ns': cpu_ns, 'cpu_limit': cpu_limit, 'mem_now': mem_now,
            'mem_peak': mem_peak, 'mem_limit': mem_limit, 'io_read': io_read, 'io_write': io_write, 'net_rx': rx, 'net_tx': tx}


BOOT_EPOCH = time.time()
# What the server had used when it started, for a run it did not see begin.
BOOT = snapshot()


def difference(start: dict | None, end: dict) -> dict:
    """The server's use between two snapshots, the report's hosting section."""
    restarted = not start or start.get('boot') != end.get('boot')
    start = BOOT if restarted else start
    used = lambda key: max(0, end[key] - start[key])  # noqa: E731
    return {
        'name': os.environ.get(NAME_ENV, '').strip() or 'hosting server', 'host': end['host'],
        'start': start['at'], 'end': end['at'], 'window_s': round(end['epoch'] - start['epoch']),
        'restarted': restarted, 'cpu_s': used('cpu_ns') / 1e9, 'cpu_limit': end['cpu_limit'],
        'mem_now': end['mem_now'], 'mem_peak': end['mem_peak'], 'mem_limit': end['mem_limit'],
        'io_read': used('io_read'), 'io_write': used('io_write'), 'net_rx': used('net_rx'), 'net_tx': used('net_tx'),
    }


def _names(user_id: int | None) -> tuple[str, ...]:
    """The account's site and cluster user names."""
    if user_id is None:
        return ()
    with get_db() as db:
        row = db.execute('SELECT username, cluster_username FROM users WHERE id = ?', (user_id,)).fetchone()
    return (row['username'], row['cluster_username']) if row else ()


def add_to_report(job_id: str, connection) -> bool:
    """Adds the hosting server's use to a finished run's report, for the accounts it is set up for."""
    job = job_store.get(job_id)
    if not job or not job.get('usage_report') or not enabled(*_names(job.get('user_id'))):
        return False
    try:
        hosting = difference(job.get('hosting_start'), snapshot())
        hosting['log_bytes'] = job.get('log_bytes', 0)
        sftp = connection.connect().open_sftp()
        try:
            data = f'{RUN_FILE_DIR}/{run_file_stem(job_id)}.usage.json'
            with sftp.open(data, 'r') as fh:
                stats = json.loads(fh.read().decode())
            stats['hosting'] = hosting
            with sftp.open(stats['report'], 'wb') as fh:
                fh.write(usage_report.render(stats))
            with sftp.open(data, 'w') as fh:
                fh.write(json.dumps(stats))
            ledger = f"{os.path.dirname(stats['report'])}/{usage_report.HOSTING_LEDGER}"
            try:
                new = sftp.stat(ledger).st_size == 0
            except OSError:
                new = True
            row = io.StringIO()
            usage_report.write_row(row, ledger_row(stats), header=new)
            with sftp.open(ledger, 'a') as fh:
                fh.write(row.getvalue())
        finally:
            sftp.close()
        LOGGER.info('Added the hosting server\'s use to the report of %s', job_id)
        return True
    except Exception as exc:
        LOGGER.warning('Could not add the hosting server\'s use to the report of %s: %s', job_id, exc)
        return False


def ledger_row(stats: dict) -> dict:
    h = stats['hosting']
    return {
        'report_written': h['end'], 'run_folder': stats['run_dir'], 'job': stats['job'], 'server': h['name'],
        'host': h['host'], 'window_start': h['start'], 'window_end': h['end'], 'window_s': h['window_s'],
        'server_restarted': int(h['restarted']), 'cpu_used_s': round(h['cpu_s'], 3), 'cpu_limit': h['cpu_limit'],
        'memory_limit_bytes': h['mem_limit'], 'memory_peak_bytes': h['mem_peak'], 'net_received_bytes': h['net_rx'],
        'net_sent_bytes': h['net_tx'], 'disk_read_bytes': h['io_read'], 'disk_written_bytes': h['io_write'],
        'run_log_bytes': h['log_bytes'], 'report': stats['report'],
    }
