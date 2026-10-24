"""A run's owner gets an email when the run completes, fails, or waits in SLURM's queue for more than
an hour: at the account's Purdue address and the User profile's email, once per event, sent with the
cluster's mail command over the user's SSH connection."""

from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.services import job_runner, run_mail
from bioinformatics_tools.api.services.job_store import job_store
from tests.test_api import client, test_rsa_key  # noqa: F401 (fixtures)

OWNER = {'cluster_host': 'hpc.purdue.edu', 'cluster_username': 'u1', 'email': 'me@lab.org', 'notify_runs': 1}


def _connection(code: int = 0):
    """A connection whose commands exit with `code`; .sent lists them."""
    conn = MagicMock()
    conn.sent = []

    def run(command, timeout=None):
        conn.sent.append(command)
        out = MagicMock()
        out.channel.recv_exit_status.return_value = code
        out.read.return_value = b''
        return MagicMock(), out, MagicMock()

    conn.connect.return_value.exec_command.side_effect = run
    return conn


def test_the_purdue_address_and_the_profile_email():
    assert run_mail.recipients(OWNER) == ['u1@purdue.edu', 'me@lab.org']
    assert run_mail.recipients({**OWNER, 'email': 'U1@purdue.edu'}) == ['u1@purdue.edu']
    assert run_mail.recipients({**OWNER, 'cluster_host': 'hpc.other.edu'}) == ['me@lab.org']


def test_the_three_messages():
    _, done = run_mail.compose('completed', 'j1', 3)
    _, failed = run_mail.compose('failed', 'j1', 115, phase=6)
    _, pending = run_mail.compose('pending', 'j1', 3, link='https://site/jobs?job=j1')
    assert done.startswith('The job j1 has completed annotating 3 genomes successfully.')
    assert failed.startswith('The job j1 annotating 115 genomes has failed in phase 6.')
    assert pending.startswith('The job j1 has been pending for more than an hour.') and 'https://site/jobs?job=j1' in pending


def test_the_phase_comes_from_the_failed_rule():
    report = lambda *rules: {'report': {'data': {'rules_summary': {'failed_rules': list(rules)}}}}  # noqa: E731
    assert run_mail.failed_phase(report('load_signalp6_to_db')) == 6
    assert run_mail.failed_phase(report('update_fingerprint_database')) == 13
    assert run_mail.failed_phase(report('run_consolidation')) == 9
    assert run_mail.failed_phase(report('resolve_genome_info')) is None and run_mail.failed_phase({}) is None


def test_one_email_per_event_and_run():
    job_store.create('mail-1', '/g', user_id=7)
    job_store.update('mail-1', genome_total=3)
    conn = _connection()
    with patch.object(run_mail, '_owner', return_value=OWNER):
        assert run_mail.notify('mail-1', 'completed', conn) is True
        assert run_mail.notify('mail-1', 'completed', conn) is False
    (command,) = conn.sent
    assert "mail -s 'MARGIE: job mail-1 completed' u1@purdue.edu me@lab.org" in command
    assert 'completed annotating 3 genomes successfully' in command


def test_no_email_when_the_owner_turned_them_off():
    job_store.create('mail-2', '/g', user_id=7)
    conn = _connection()
    with patch.object(run_mail, '_owner', return_value={**OWNER, 'notify_runs': 0}):
        assert run_mail.notify('mail-2', 'failed', conn) is False
    assert conn.sent == []


def test_a_run_that_ends_emails_its_owner():
    job_store.create('mail-3', '/g', user_id=7)
    lines = iter(['__LAUNCHED__', '__EXIT_CODE__:1'])
    with patch.object(job_runner.ssh_slurm, 'submit_ssh_job', return_value=lines), \
            patch.object(job_runner, '_slurm_status_checker'), patch.object(run_mail, 'notify') as notify:
        job_runner.run_ssh_task('mail-3', 'dane_wf margie sb', MagicMock())
    assert job_store.get_status('mail-3') == 'failed'
    notify.assert_called_once()
    assert notify.call_args[0][:2] == ('mail-3', 'failed')


def test_a_step_pending_for_over_an_hour_is_emailed_about():
    job_store.create('mail-4', '/g', user_id=7)
    job_store.update('mail-4', status='running')
    job_store.add_slurm_job('mail-4', '991', 'run_gtdbtk_batch')
    job_store.get_slurm_jobs('mail-4')[0]['pending_since'] = 0  # first seen pending long ago
    stop = lambda *_: job_store.update('mail-4', status='completed')  # noqa: E731
    with patch.object(job_runner.ssh_slurm, 'check_multiple_slurm_jobs', return_value={'991': {'state': 'PENDING', 'time': '0:00'}}), \
            patch.object(job_runner.time, 'sleep', side_effect=stop), patch.object(run_mail, 'notify') as notify:
        job_runner._slurm_status_checker('mail-4', MagicMock())
    notify.assert_called_once()
    assert notify.call_args[0][:2] == ('mail-4', 'pending')



@patch('bioinformatics_tools.api.routers.auth.make_user_connection')
def test_the_profile_turns_the_emails_off_and_on(make_conn, client, test_rsa_key):  # noqa: F811
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = b'/home/mailtest\n'
    make_conn.return_value.connect.return_value.exec_command.return_value = (MagicMock(), stdout, MagicMock())
    client.post('/v1/auth/register', json={'username': 'mailtest', 'password': 'S3cur3P@ss!', 'cluster_host': 'hpc.purdue.edu',
                                           'cluster_username': 'mailtest', 'private_key': test_rsa_key})
    token = client.post('/v1/auth/login', json={'username': 'mailtest', 'password': 'S3cur3P@ss!'}).json()['access_token']
    h = {'Authorization': f'Bearer {token}'}
    assert client.get('/v1/auth/me', headers=h).json()['notify_runs'] is True
    off = client.put('/v1/auth/profile', headers=h, json={'notify_runs': False, 'email': ' me@lab.org '}).json()
    assert off['notify_runs'] is False and off['email'] == 'me@lab.org'
    assert client.put('/v1/auth/profile', headers=h, json={'notify_runs': True}).json()['notify_runs'] is True
