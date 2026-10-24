"""The website's look kept with the account: what one browser saves, another signed in to the same
account reads, so each shows the same look; other accounts keep their own."""

from tests.test_api import client, test_rsa_key  # noqa: F401 (fixtures)
from tests.test_delete_account import _signed_in


def test_a_new_account_has_no_look_yet(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key, name='looknew', cluster_user='looknew')
    assert client.get('/v1/auth/look', headers=h).json() == {}


def test_the_saved_look_is_read_back_and_parts_replace_their_own(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key, name='lookone', cluster_user='lookone')
    assert client.put('/v1/auth/look', headers=h, json={'prefs': {'theme': 'dark', 'palette': ''}}).json() == {'saved': True}
    client.put('/v1/auth/look', headers=h, json={'default': {'accent': 'blue'}, 'other': {'x': 1}})
    assert client.get('/v1/auth/look', headers=h).json() == {'prefs': {'theme': 'dark', 'palette': ''}, 'default': {'accent': 'blue'}}


def test_each_account_keeps_its_own_look(client, test_rsa_key):  # noqa: F811
    a = _signed_in(client, test_rsa_key, name='looka', cluster_user='looka')
    b = _signed_in(client, test_rsa_key, name='lookb', cluster_user='lookb')
    client.put('/v1/auth/look', headers=a, json={'prefs': {'theme': 'light'}})
    assert client.get('/v1/auth/look', headers=b).json() == {}


def test_a_look_must_be_objects_and_small(client, test_rsa_key):  # noqa: F811
    h = _signed_in(client, test_rsa_key, name='lookbad', cluster_user='lookbad')
    assert client.put('/v1/auth/look', headers=h, json={'prefs': 'dark'}).status_code == 400
    assert client.put('/v1/auth/look', headers=h, json={'theme': 'dark'}).status_code == 400
    assert client.put('/v1/auth/look', headers=h, json={'prefs': {'x': 'y' * 70000}}).status_code == 413


def test_signing_in_is_needed(client):  # noqa: F811
    assert client.get('/v1/auth/look').status_code in (401, 403)
