"""User profile → Delete account: with the password again, and while no run is going, the MARGIE
account (sign-in, profile, stored cluster key) is deleted and its token signs in no more. The
files on the cluster are left as they are."""

from unittest.mock import MagicMock, patch

from bioinformatics_tools.api.services.job_store import job_store
from tests.test_api import client, test_rsa_key  # noqa: F401 (fixtures)

PASSWORD = 'S3cur3P@ss!'


def _signed_in(client, key):  # noqa: F811
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = b'/home/gone\n'
    with patch('bioinformatics_tools.api.routers.auth.make_user_connection') as make_conn:
        make_conn.return_value.connect.return_value.exec_command.return_value = (MagicMock(), stdout, MagicMock())
        client.post('/v1/auth/register', json={'username': 'gone', 'password': PASSWORD, 'cluster_host': 'hpc.purdue.edu',
                                               'cluster_username': 'gone', 'private_key': key})
    token = client.post('/v1/auth/login', json={'username': 'gone', 'password': PASSWORD}).json()['access_token']
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


def test_the_account_is_deleted_and_signs_in_no_more(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key)
    assert client.post('/v1/auth/delete-account', headers=h, json={'password': PASSWORD}).json() == {'deleted': True}
    assert client.get('/v1/auth/me', headers=h).status_code == 401
    assert client.post('/v1/auth/login', json={'username': 'gone', 'password': PASSWORD}).status_code == 401
