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
    assert [s['title'] for s in steps] == ['Consolidation', 'Labeling', 'Operon database', 'Scoring',
                                           'Fingerprinting', 'Fingerprint databases']
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
