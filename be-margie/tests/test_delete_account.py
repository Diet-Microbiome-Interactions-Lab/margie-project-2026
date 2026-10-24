"""User profile → Delete account: with the password again, and while no run is going, the MARGIE
account (sign-in, profile, stored cluster key) is deleted and its token signs in no more; in the
cluster home, the stored language-model keys and the copy of MARGIE go too, unless another MARGIE
account uses the same cluster account. When they cannot be removed, nothing is deleted."""

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


def test_the_account_and_its_files_on_the_cluster_are_deleted(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    with patch(REMOVE, return_value='') as remove:
        r = client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD}).json()
    assert r == {'deleted': True, 'cluster_files_removed': True}
    remove.assert_called_once()
    assert client.get('/v1/auth/me', headers=h).status_code == 401
    assert client.post('/v1/auth/login', json={'username': 'gone', 'password': PASSWORD}).status_code == 401


def test_the_files_stay_while_another_account_uses_the_cluster_account(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    _signed_in(client, test_rsa_key, name='gone2')
    with patch(REMOVE) as remove:
        r = client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD}).json()
    assert r == {'deleted': True, 'cluster_files_removed': False}
    remove.assert_not_called()


def test_nothing_is_deleted_when_the_files_cannot_be_removed(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    with patch(REMOVE, return_value='Permission denied'):
        r = client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD})
    assert r.status_code == 502 and 'Permission denied' in r.json()['detail']
    assert client.get('/v1/auth/me', headers=h).status_code == 200


def test_the_removal_takes_the_keys_and_the_copy_and_leaves_the_config():
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
    assert 'rm -rf -- "$HOME/.config/bioinformatics-tools/secrets"' in command
    assert 'repo="$HOME/margie-project-2026"' in command and 'rm -rf -- "$repo"' in command
    # The link goes only when it leads into MARGIE's copy; a folder of the user's own stays.
    assert '[ -L "$link" ]' in command and 'config.yaml' not in command


def test_deleting_the_account_revokes_its_licence_on_record(client, test_rsa_key, monkeypatch):  # noqa: F811
    from bioinformatics_tools.api import licensing
    monkeypatch.setenv('LICENSE_RECORDS_DIR', '/group/margie/licensing-records')
    h = _signed_in(client, test_rsa_key, name='licgone', cluster_user='licgone')
    terms = licensing.load_terms()
    with patch('bioinformatics_tools.api.routers.ssh._build_connection'), patch(SFTP):
        assert client.post('/v1/license/accept', headers=h, json={
            'accepted_items': [a['id'] for a in licensing.catalog.ACK_ITEMS], 'terms_version': terms['version'],
            'terms_sha256': terms['sha256'], 'usage_type': 'academic', 'licensed_tools': []}).status_code == 200
    with patch(REMOVE, return_value=''), patch('bioinformatics_tools.api.routers.ssh._build_connection'), patch(SFTP) as write:
        assert client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD}).json()['deleted'] is True
    revocation = [c for c in write.call_args_list if c[0][0].endswith('/revocation.json')]
    assert len(revocation) == 1 and revocation[0][0][0].startswith('/group/margie/licensing-records/')
    assert json.loads(revocation[0][0][1])['reason'] == 'account deleted'
    # The same name signed up again starts without an acceptance.
    h2 = _signed_in(client, test_rsa_key, name='licgone', cluster_user='licgone')
    assert client.get('/v1/license/status', headers=h2).json()['accepted'] is False
