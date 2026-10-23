"""Chat with the genome on the website (api/services/genome_chat.py): keys sealed with the server's key
and dated to expire, only their last four characters shown, reads kept inside the genome's folders,
custom services only on the public internet, and Claude's tool loop."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bioinformatics_tools.api.services import genome_chat as gc
from tests.test_api import FAKE_USER, authed_client, client  # noqa: F401 (fixtures)

DAY = 86400


class FakeAccount:
    """A user's cluster files in memory, through the module's own read/write helpers."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def __enter__(self):
        self._patches = [
            patch.object(gc, '_read', side_effect=lambda conn, path, limit=None: self.files.get(path)),
            patch.object(gc, '_write', side_effect=lambda conn, path, text, private=False: self.files.__setitem__(path, text.encode())),
            patch.object(gc, '_run', return_value=(0, '')),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self._patches:
            p.stop()


def test_a_key_is_sealed_and_expires_after_its_days():
    t0 = 1_800_000_000
    token = gc.seal('sk-ant-secret-1234', t0)
    assert 'secret' not in token
    assert gc.unseal(token, 10, t0 + 9 * DAY) == 'sk-ant-secret-1234'
    assert gc.unseal(token, 10, t0 + 11 * DAY) is None


def test_the_page_sees_only_the_last_four_and_the_expiry():
    with FakeAccount() as acct:
        gc.save_key(None, '/home/u', 'anthropic', 'sk-ant-secret-1234', 7)
        stored = acct.files['/home/u/' + gc.KEYS_FILE].decode()
        assert 'sk-ant-secret' not in stored and '"days": 7' in stored
        info = gc.public_settings(None, '/home/u')
    assert info['keys']['anthropic'] == {'saved': True, 'last4': '1234', 'expires': info['keys']['anthropic']['expires'], 'cluster': True}
    assert 'sk-ant' not in str(info)


def test_an_expired_key_is_removed_and_said():
    with FakeAccount() as acct:
        gc.save_key(None, '/home/u', 'openai', 'sk-old-abcd', 1, now=1_800_000_000)
        usable, expired = gc._keys(None, '/home/u', now=1_800_000_000 + 2 * DAY)
        assert usable == {} and expired == ['openai']
        assert 'openai' not in acct.files['/home/u/' + gc.KEYS_FILE].decode()


def test_keys_are_written_privately():
    calls = []
    with patch.object(gc, '_read', return_value=None), \
            patch.object(gc, '_write', side_effect=lambda conn, path, text, private=False: calls.append((path, private))):
        gc.save_key(None, '/home/u', 'gemini', 'k-9999')
    assert calls == [('/home/u/' + gc.KEYS_FILE, True)]


def test_settings_are_kept_in_bounds():
    s = gc._clean_settings(gc.DEFAULTS, {'provider': 'nope', 'budget': 10**9, 'answerTokens': 1, 'consented': ['anthropic', 'x']})
    assert s['provider'] == 'anthropic' and s['budget'] == 400000 and s['answerTokens'] == 500 and s['consented'] == ['anthropic']


def test_the_model_reads_only_inside_the_genomes_folders():
    src = gc.Source(None, 'g1', ['/scratch/c/u/out/run1/g1'], '/scratch/c/u/out/run1/g1/FINAL.tsv')
    assert src.inside('g1/scoring/x.tsv') == '/scratch/c/u/out/run1/g1/scoring/x.tsv'
    assert src.inside('g1/../g2/x.tsv') is None and src.inside('/etc/passwd') is None
    assert src.table == '/scratch/c/u/out/run1/g1/FINAL.tsv'
    with pytest.raises(gc.ChatError):
        gc.Source(None, 'g1', ['relative/path'], None)


def test_a_custom_service_must_be_public_https():
    for url in ('http://example.org/v1', 'https://127.0.0.1/v1', 'https://10.5.1.2/v1', 'https://169.254.169.254/v1'):
        with pytest.raises(gc.ChatError):
            gc.public_https(url)


def _message(stop, *blocks):
    return SimpleNamespace(stop_reason=stop, content=list(blocks))


class _Stream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return SimpleNamespace(get_final_message=lambda: self.message)

    def __exit__(self, *a):
        return False


def test_claude_reads_with_its_tools_then_answers():
    replies = iter([
        _message('tool_use', SimpleNamespace(type='tool_use', id='t1', name='search_table', input={'query': 'dnaA'})),
        _message('end_turn', SimpleNamespace(type='text', text='dnaA is gene 1 [E1].')),
    ])
    sent = []

    def stream(**params):
        sent.append(params)
        return _Stream(next(replies))

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)), messages=SimpleNamespace(stream=stream))
    kit = SimpleNamespace(run=lambda name, args: f'[E1] {name} {args["query"]}: 1 row')
    s = {**gc.DEFAULTS}
    text = gc.ask_claude(kit, s, 'k', 'system', [], 'Where is dnaA?', client=fake)
    assert text == 'dnaA is gene 1 [E1].'
    first = sent[0]
    assert first['model'] == 'claude-opus-5-5' and first['thinking'] == {'type': 'adaptive'}
    assert first['fallbacks'] == 'default' and first['betas'] == [gc.FALLBACK_BETA]
    # The tool turn went back whole, and its result in one user message.
    assert sent[1]['messages'][-2]['role'] == 'assistant'
    assert sent[1]['messages'][-1]['content'][0]['tool_use_id'] == 't1'


def test_a_refusal_is_said_plainly():
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=lambda **p: _Stream(_message('refusal')))))
    assert 'declined' in gc.ask_claude(SimpleNamespace(run=None), {**gc.DEFAULTS}, 'k', 's', [], 'q', client=fake)


def test_asking_needs_the_notice_and_a_key():
    with FakeAccount():
        with pytest.raises(gc.ChatError, match='data notice'):
            gc.ask(None, '/home/u', 'g1', 'hi', '', {'roots': ['/x/g1']})
        gc.update_settings(None, '/home/u', {'consented': ['anthropic']})
        with pytest.raises(gc.ChatError, match='API key'):
            gc.ask(None, '/home/u', 'g1', 'hi', '', {'roots': ['/x/g1']})


def test_the_routes(authed_client):  # noqa: F811
    with patch('bioinformatics_tools.api.routers.chat._build_connection'), \
            patch.object(gc, 'public_settings', return_value={'settings': {}, 'keys': {}}), \
            patch.object(gc, 'read_history', return_value=[{'role': 'user', 'text': 'hi'}]), \
            patch.object(gc, 'ask', side_effect=gc.ChatError('Add your Claude (Anthropic) API key first.', 400)):
        r = authed_client.get('/v1/chat?genome=g1')
        assert r.status_code == 200 and r.json()['history'][0]['text'] == 'hi'
        r = authed_client.post('/v1/chat', json={'genome': 'g1', 'question': 'hi'})
        assert r.status_code == 400 and 'API key' in r.json()['detail']
