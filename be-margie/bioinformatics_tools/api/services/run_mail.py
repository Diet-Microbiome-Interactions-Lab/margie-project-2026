"""Emails a run's owner when the run completes, fails, or waits in SLURM's queue for more than an hour.

The cluster sends them with its mail command, over the user's own SSH connection, as it sends
SLURM's own messages. They go to the account's Purdue address (on a Purdue cluster) and the email
on the User profile, once per event and run, while the profile's "Email me about my runs" is on.
"""

import logging
import os
import re
import shlex

from bioinformatics_tools.api.database import get_db
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.utilities.ssh_slurm import run_file_stem
from bioinformatics_tools.workflow_tools.workflow_registry import MARGIE_SB_PHASED_TOOLS

LOGGER = logging.getLogger(__name__)

# A run, or one of its steps, waiting in the queue this long is worth an email.
PENDING_SECONDS = 3600

# Tool keys, longest first, so 'fingerprint_database' is found before 'fingerprint'.
_PHASE_OF = {t['key']: t['phase'] for t in MARGIE_SB_PHASED_TOOLS}
_KEYS = sorted(_PHASE_OF, key=len, reverse=True)


def recipients(user: dict) -> list[str]:
    """The account's Purdue address (on a Purdue cluster), then the profile's email."""
    to: list[str] = []
    host = (user.get('cluster_host') or '').lower()
    name = (user.get('cluster_username') or '').strip()
    if name and (host == 'purdue.edu' or host.endswith('.purdue.edu')):
        to.append(f'{name}@purdue.edu')
    email = (user.get('email') or '').strip()
    if email and email.lower() not in {a.lower() for a in to}:
        to.append(email)
    return to


def failed_phase(job: dict) -> int | None:
    """The phase of the first failed rule in the run's report (load_signalp6_to_db: 6)."""
    rules = (((job.get('report') or {}).get('data') or {}).get('rules_summary') or {}).get('failed_rules') or []
    for rule in rules:
        for key in _KEYS:
            if re.search(rf'(^|_){re.escape(key)}(_|$)', rule):
                return _PHASE_OF[key]
    return None


def compose(kind: str, job_id: str, genomes: int | None, phase: int | None = None, link: str = '') -> tuple[str, str]:
    """The subject and body for 'completed', 'failed' or 'pending'."""
    n = f"{genomes} genome{'' if genomes == 1 else 's'}" if genomes else 'its genomes'
    if kind == 'completed':
        subject = f'MARGIE: job {job_id} completed'
        line = f'The job {job_id} has completed annotating {n} successfully.'
    elif kind == 'failed':
        subject = f'MARGIE: job {job_id} failed'
        line = f'The job {job_id} annotating {n} has failed' + (f' in phase {phase}.' if phase else '.')
    else:
        subject = f'MARGIE: job {job_id} is pending'
        line = f'The job {job_id} has been pending for more than an hour.'
    body = line + (f'\n\nIts details and log: {link}' if link else '') + '\n\nThis is an automatic message from MARGIE.'
    return subject, body


def send(connection, to: list[str], subject: str, body: str) -> bool:
    """Sends one email with the cluster's mail command; True when it took the message."""
    if not to:
        return False
    command = f"printf '%s\\n' {shlex.quote(body)} | mail -s {shlex.quote(subject)} {' '.join(shlex.quote(a) for a in to)}"
    try:
        ssh = connection.connect()
        _, out, err = ssh.exec_command(command, timeout=60)
        code = out.channel.recv_exit_status()
        if code != 0:
            LOGGER.warning('mail exited %s: %s', code, err.read().decode(errors='replace').strip())
        return code == 0
    except Exception as exc:
        LOGGER.warning('Could not send a run email: %s', exc)
        return False


def driver_pending(job_id: str, connection) -> bool:
    """Whether the run's own SLURM job (margie-<job>) is still waiting in the queue."""
    name = f'margie-{run_file_stem(job_id)}'
    try:
        ssh = connection.connect()
        _, out, _ = ssh.exec_command(f'squeue -h -u "$USER" -n {shlex.quote(name)} -o %T', timeout=60)
        return 'PENDING' in out.read().decode(errors='replace')
    except Exception as exc:
        LOGGER.warning('Could not ask SLURM about the run %s: %s', job_id, exc)
        return False


def _owner(user_id: int | None) -> dict | None:
    if user_id is None:
        return None
    with get_db() as db:
        row = db.execute('SELECT cluster_host, cluster_username, email, notify_runs FROM users WHERE id = ?',
                         (user_id,)).fetchone()
    return dict(row) if row else None


def _link(job_id: str) -> str:
    """The job on the site, whose address is the API's allowed origin (BSP_CORS_ALLOWED_ORIGINS)."""
    origins = [o.strip() for o in os.environ.get('BSP_CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()]
    site = next((o for o in origins if o.startswith('http')), '')
    return f'{site.rstrip("/")}/jobs?job={job_id}' if site else ''


def notify(job_id: str, kind: str, connection) -> bool:
    """Emails the run's owner about `kind` once per run; True when an email went out."""
    job = job_store.get(job_id)
    if not job:
        return False
    mailed = job.setdefault('mailed', [])
    if kind in mailed:
        return False
    mailed.append(kind)
    owner = _owner(job.get('user_id'))
    if not owner or not owner.get('notify_runs', 1):
        return False
    to = recipients(owner)
    subject, body = compose(kind, job_id, job.get('genome_total'), failed_phase(job) if kind == 'failed' else None, _link(job_id))
    sent = send(connection, to, subject, body)
    LOGGER.info('Run email %s for %s to %s: %s', kind, job_id, ', '.join(to) or 'nobody', 'sent' if sent else 'not sent')
    return sent
