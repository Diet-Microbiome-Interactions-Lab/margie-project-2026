"""User profile → Delete account: with the password again, and while no run is going, the MARGIE
account (sign-in, profile, stored cluster key) is deleted and its token signs in no more. The cluster
home stays as it is: other MARGIE accounts, on the website or in the desktop app, can share the cluster
account and its copy of MARGIE. Remove MARGIE from the cluster removes that copy on its own, with the
password, and not while a MARGIE run of the cluster account is in SLURM, the desktop app's server is
running, or the server asked runs from that copy."""

import json
from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.services.job_store import job_store
from tests.test_api import client, test_rsa_key  # noqa: F401 (fixtures)

PASSWORD = 'S3cur3P@ss!'
REMOVE = 'bioinformatics_tools.api.routers.auth.remove_margie_files'
SFTP = 'bioinformatics_tools.utilities.ssh_sftp.write_remote_text_file'


def _signed_in(client, key, name='gone', cluster_user='gone'):  # noqa: F811
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = b'/home/gone\n'
    with patch('bioinformatics_tools.api.routers.auth.make_user_connection') as make_conn:
        make_conn.return_value.connect.return_value.exec_command.return_value = (MagicMock(), stdout, MagicMock())
        client.post('/v1/auth/register', json={'username': name, 'password': PASSWORD, 'cluster_host': 'hpc.purdue.edu',
                                               'cluster_username': cluster_user, 'private_key': key})
    token = client.post('/v1/auth/login', json={'username': name, 'password': PASSWORD}).json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_the_wrong_password_deletes_nothing(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    r = client.post('/v1/auth/delete-account', headers=h, json={'password': 'not it'})
    assert r.status_code == 403
    assert client.get('/v1/auth/me', headers=h).status_code == 200


def test_a_run_going_waits_the_deletion(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    me = client.get('/v1/auth/me', headers=h).json()
    job_store.create('going-1', '/g', user_id=me['user_id'])
    job_store.update('going-1', status='running')
    try:
        r = client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD})
        assert r.status_code == 409 and 'going-1' in r.json()['detail']
    finally:
        job_store.update('going-1', status='completed')


def test_the_account_goes_and_the_cluster_home_stays(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    with patch(REMOVE) as remove:
        r = client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD}).json()
    assert r == {'deleted': True}
    remove.assert_not_called()
    assert client.get('/v1/auth/me', headers=h).status_code == 401
    assert client.post('/v1/auth/login', json={'username': 'gone', 'password': PASSWORD}).status_code == 401


def test_the_copy_is_removed_on_its_own_with_the_password(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    assert client.post('/v1/auth/remove-cluster-copy', headers=h, json={'password': 'not it'}).status_code == 403
    with patch(REMOVE, return_value='') as remove, patch('bioinformatics_tools.api.routers.auth.runs_here', return_value=False):
        r = client.post('/v1/auth/remove-cluster-copy', headers=h, json={'password': PASSWORD})
    assert r.json() == {'removed': True}
    remove.assert_called_once()
    assert client.get('/v1/auth/me', headers=h).status_code == 200


def test_the_copy_stays_while_it_is_in_use(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    busy = 'A MARGIE run of this cluster account is in SLURM; stop it, or wait for it to end, first.'
    with patch(REMOVE, return_value=busy), patch('bioinformatics_tools.api.routers.auth.runs_here', return_value=False):
        r = client.post('/v1/auth/remove-cluster-copy', headers=h, json={'password': PASSWORD})
    assert r.status_code == 409 and 'in SLURM' in r.json()['detail']
    # A server that runs from the copy (the desktop app's, on a login node) leaves it alone.
    with patch(REMOVE) as remove, patch('bioinformatics_tools.api.routers.auth.runs_here', return_value=True):
        r = client.post('/v1/auth/remove-cluster-copy', headers=h, json={'password': PASSWORD})
    assert r.status_code == 409 and 'runs from that copy' in r.json()['detail']
    remove.assert_not_called()


def test_the_removal_checks_for_users_then_renames_the_copy_aside():
    from bioinformatics_tools.utilities.ssh_connection import remove_margie_files
    conn = MagicMock()
    out = MagicMock()
    out.channel.recv_exit_status.return_value = 0
    out.read.return_value = b'REMOVED\n'
    err = MagicMock()
    err.read.return_value = b''
    conn.connect.return_value.exec_command.return_value = (MagicMock(), out, err)
    assert remove_margie_files(conn) == ''
    command = conn.connect.return_value.exec_command.call_args[0][0]
    assert "grep -q '^margie-'" in command and 'api-endpoint.json' in command
    assert command.index('squeue') < command.index('rm -rf -- "$HOME/.config/bioinformatics-tools/secrets"')
    assert 'mv -- "$repo" "$gone"' in command and 'nohup rm -rf -- "$gone"' in command
    # The link goes only when it leads into MARGIE's copy; a folder of the user's own stays.
    assert '[ -L "$link" ]' in command and 'config.yaml' not in command


def test_the_removal_script_leaves_a_busy_account_alone(tmp_path):
    """The script itself, run in a shell with a fake squeue that lists a MARGIE driver."""
    import subprocess
    from bioinformatics_tools.utilities import ssh_connection
    home, bin_ = tmp_path / 'home', tmp_path / 'bin'
    (home / 'margie-project-2026' / 'be-margie').mkdir(parents=True)
    bin_.mkdir()
    (bin_ / 'squeue').write_text('#!/bin/sh\necho margie-1234\n')
    (bin_ / 'squeue').chmod(0o755)
    captured = {}
    conn = MagicMock()
    def run(command, timeout=None):
        captured['command'] = command
        r = subprocess.run(['bash', '-c', command], capture_output=True, text=True,
                           env={'HOME': str(home), 'USER': 'x', 'PATH': f'{bin_}:/usr/bin:/bin'})
        out, err = MagicMock(), MagicMock()
        out.channel.recv_exit_status.return_value = r.returncode
        out.read.return_value = r.stdout.encode()
        err.read.return_value = r.stderr.encode()
        return MagicMock(), out, err
    conn.connect.return_value.exec_command.side_effect = run
    assert 'in SLURM' in ssh_connection.remove_margie_files(conn)
    assert (home / 'margie-project-2026' / 'be-margie').is_dir()
    (bin_ / 'squeue').write_text('#!/bin/sh\necho 9876\n')
    assert ssh_connection.remove_margie_files(conn) == ''
    assert not (home / 'margie-project-2026').exists()


def test_deleting_the_account_revokes_its_licence_on_record(client, test_rsa_key, monkeypatch):  # noqa: F811
    from bioinformatics_tools.api import licensing
    monkeypatch.setenv('LICENSE_RECORDS_DIR', '/group/margie/licensing-records')
    h = _signed_in(client, test_rsa_key, name='licgone', cluster_user='licgone')
    terms = licensing.load_terms()
    with patch('bioinformatics_tools.api.routers.ssh._build_connection'), patch(SFTP):
        assert client.post('/v1/license/accept', headers=h, json={
            'accepted_items': [a['id'] for a in licensing.catalog.ACK_ITEMS], 'terms_version': terms['version'],
            'terms_sha256': terms['sha256'], 'usage_type': 'academic', 'licensed_tools': []}).status_code == 200
    with patch('bioinformatics_tools.api.routers.ssh._build_connection'), patch(SFTP) as write:
        assert client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD}).json()['deleted'] is True
    revocation = [c for c in write.call_args_list if c[0][0].endswith('/revocation.json')]
    assert len(revocation) == 1 and revocation[0][0][0].startswith('/group/margie/licensing-records/')
    assert json.loads(revocation[0][0][1])['reason'] == 'account deleted'
    # The same name signed up again starts without an acceptance.
    h2 = _signed_in(client, test_rsa_key, name='licgone', cluster_user='licgone')
    assert client.get('/v1/license/status', headers=h2).json()['accepted'] is False


# ---- a new account with an old name starts without its acceptances ----

def _leftover_acceptance(username: str, when: str = '2026-01-01T00:00:00Z'):
    """An acceptance held under a name, as an earlier account of that name left it."""
    from bioinformatics_tools.api import licensing
    from bioinformatics_tools.api.database import get_db
    with get_db() as db:
        db.execute('INSERT INTO license_acceptances (username, terms_version, terms_sha256, accepted_items, usage_type, '
                   'licensed_tools, ip_address, user_agent, accepted_at, depot_record_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (username, licensing.load_terms()['version'], 'x', '[]', 'academic', '[]', None, None, when, None))


def test_an_acceptance_older_than_the_account_does_not_count(client, test_rsa_key):  # noqa: F811
    from bioinformatics_tools.api import licensing
    with patch('bioinformatics_tools.api.routers.auth._drop_leftover_acceptances'):
        h = _signed_in(client, test_rsa_key, name='reused')
    _leftover_acceptance('reused')
    assert not licensing.has_accepted_current_terms('reused')
    assert licensing.get_entitlement('reused')['usage_type'] is None
    assert client.get('/v1/license/status', headers=h).json()['accepted'] is False
    # One made since the account was counts.
    _leftover_acceptance('reused', when='2999-01-01T00:00:00Z')
    assert licensing.has_accepted_current_terms('reused')


def test_signing_up_with_an_old_name_revokes_what_it_left(client, test_rsa_key):  # noqa: F811
    from bioinformatics_tools.api.database import get_db
    _leftover_acceptance('again')
    with patch('bioinformatics_tools.api.routers.license._save_on_cluster', return_value=lambda **kw: '/records/x/revocation.json'):
        _signed_in(client, test_rsa_key, name='again')
    with get_db() as db:
        left = db.execute('SELECT count(*) FROM license_acceptances WHERE username = ?', ('again',)).fetchone()[0]
    assert left == 0
