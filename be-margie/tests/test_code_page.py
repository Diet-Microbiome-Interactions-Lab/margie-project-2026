"""The Code page's API (routers/code.py): the steps' scripts as installed, and nothing outside the list."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from bioinformatics_tools.api.auth import get_current_user
from bioinformatics_tools.api.main import app
from bioinformatics_tools.api.routers import code


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {'user_id': 1, 'username': 'u'}
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_each_listed_script_is_installed():
    for step in code.STEPS:
        for path in step['files']:
            assert (code.WORKFLOW_TOOLS / path).is_file(), path


def test_the_steps_list_their_files_with_summaries(client):
    steps = client.get('/v1/code').json()['steps']
    assert [s['title'] for s in steps] == ['The workflow', 'Genome, protein and gene hashes', 'Loading into the MARGIE database',
                                           'Envelope and localisation', 'Consolidation', 'Labeling', 'Operon database', 'Scoring',
                                           'Fingerprinting', 'Fingerprint databases', 'Genome map and diagrams', 'Reports',
                                           "A run's folders and records"]
    smk = next(f for s in steps for f in s['files'] if f['name'] == 'margie_sb.smk')
    assert smk['summary'].startswith("MARGIE's rules")
    merge = next(f for s in steps for f in s['files'] if f['name'] == 'merge-all-columns.py')
    assert merge['summary'] == 'Stage 2 of consolidation.'
    assert merge['lines'] > 100


def test_a_file_is_its_source_byte_for_byte(client):
    path = 'scoring/score-c1-tool-coverage.py'
    got = client.get('/v1/code/file', params={'path': path}).json()
    disk = (code.WORKFLOW_TOOLS / path).read_text(encoding='utf-8')
    assert got['text'] == disk
    assert got['sha256'] == hashlib.sha256(disk.encode('utf-8')).hexdigest()


@pytest.mark.parametrize('path', ['../api/auth.py', 'workflow.py', 'scoring/../workflow.py', '/etc/passwd'])
def test_only_listed_files_are_read(client, path):
    assert client.get('/v1/code/file', params={'path': path}).status_code == 404


def test_signing_in_is_needed():
    assert TestClient(app).get('/v1/code').status_code == 401


def test_a_snippet_is_the_file_s_own_lines(client):
    got = client.get('/v1/code/snippet', params={'path': 'genome_identity.py', 'symbol': 'genome_hash'}).json()
    lines = (code.WORKFLOW_TOOLS / 'genome_identity.py').read_text(encoding='utf-8').splitlines()
    assert got['text'] == '\n'.join(lines[got['start'] - 1:got['end']]) + '\n'
    assert got['text'].lstrip().startswith(('def genome_hash', '#'))


def test_a_rule_runs_to_the_next_rule(client):
    got = client.get('/v1/code/snippet', params={'path': 'margie_sb.smk', 'symbol': 'rule:load_scoring_to_db'}).json()
    assert got['text'].startswith('rule load_scoring_to_db:') or got['text'].startswith('#')
    assert 'rule ' not in got['text'].split('\n', 1)[1]
    assert 'runtime=load_minutes' in got['text']


@pytest.mark.parametrize('path,symbol', [('workflow.py', 'WorkflowRunner'), ('../api/auth.py', 'get_current_user'),
                                         ('genome_identity.py', 'no_such_name')])
def test_a_snippet_comes_only_from_quoted_files(client, path, symbol):
    assert client.get('/v1/code/snippet', params={'path': path, 'symbol': symbol}).status_code == 404


# ---- the code password: the text comes only with it, where the server sets one ----

def test_with_a_code_password_the_text_needs_it(client, monkeypatch):
    import hashlib

    from bioinformatics_tools.api.routers import code
    monkeypatch.setenv(code.CODE_ENV, hashlib.sha256(b"open sesame").hexdigest())
    monkeypatch.setattr(code.time, "sleep", lambda s: None)
    path = 'genome_identity.py'
    assert client.get('/v1/code/file', params={'path': path}).status_code == 403
    assert client.post('/v1/code/file', json={'path': path, 'password': 'wrong'}).json()['detail'].startswith('code-locked')
    assert client.post('/v1/code/file', json={'path': path, 'password': 'open sesame'}).json()['path'] == path
    assert client.post('/v1/code/snippet', json={'path': path, 'symbol': 'genome_hash'}).status_code == 403
    assert client.post('/v1/code/snippet', json={'path': path, 'symbol': 'genome_hash', 'password': 'open sesame'}).status_code == 200
    assert client.post('/v1/code/unlock', json={'password': 'open sesame'}).json() == {'open': True}
    assert client.post('/v1/code/unlock', json={'password': 'nope'}).status_code == 403
    # The list of steps stays open: it names the scripts, not their text.
    assert client.get('/v1/code').status_code == 200


def test_without_a_code_password_the_code_is_open(client, monkeypatch):
    from bioinformatics_tools.api.routers import code
    monkeypatch.delenv(code.CODE_ENV, raising=False)
    assert client.post('/v1/code/file', json={'path': 'genome_identity.py'}).status_code == 200
