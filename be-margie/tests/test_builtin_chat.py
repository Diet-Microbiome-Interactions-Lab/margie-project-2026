"""The built-in genome chat on the cluster (api/services/cluster_llm.py): the model folders beside the
databases, the trained model before the base one, and the chat job on a GPU node with 10 cores and 80%
of the node's memory."""

import json

import pytest

from bioinformatics_tools.api.services import cluster_llm

HOME = '/home/u'
CFG = {'margie_sb': {'db_root': '/data/db', 'sif_path': '/data/sif'},
       'compute': {'cluster_default': {'account': 'lab'}}}


class _Stream:
    def __init__(self, text: str, code: int = 0):
        self._text, self.channel = text, self
        self._code = code

    def recv_exit_status(self):
        return self._code

    def read(self):
        return self._text.encode()

    def write(self, data):
        self.written = data

    def shutdown_write(self):
        pass


class FakeConn:
    """Answers each shell command by the first rule whose text it contains: (fragment, exit code, output)."""

    def __init__(self, rules):
        self.rules, self.commands = rules, []

    def connect(self):
        return self

    def exec_command(self, command, timeout=None):
        self.commands.append(command)
        for fragment, code, out in self.rules:
            if fragment in command:
                return _Stream(''), _Stream(out, code), _Stream('')
        return _Stream(''), _Stream('', 1), _Stream('')


def test_the_folders_default_to_the_databases_folder():
    assert cluster_llm.model_folders(CFG) == {'trained': '/data/db/llm/trained-model', 'base': '/data/db/llm/base-model'}


def test_a_folder_set_in_settings_wins():
    cfg = {**CFG, 'margie_sb': {**CFG['margie_sb'], 'llm': {'base_model': '/my/model/'}}}
    assert cluster_llm.model_folders(cfg)['base'] == '/my/model'


def test_the_trained_model_is_used_when_its_folder_holds_one():
    conn = FakeConn([("test -f /data/db/llm/trained-model/config.json", 0, 'model.safetensors\n')])
    assert cluster_llm.choose_model(conn, CFG)['which'] == 'trained'
    conn = FakeConn([("test -f /data/db/llm/base-model/config.json", 0, 'model.safetensors\n')])
    assert cluster_llm.choose_model(conn, CFG)['which'] == 'base'


def test_without_the_container_it_says_so():
    conn = FakeConn([("test -f /data/db/llm/base-model/config.json", 0, 'model.safetensors\n'),
                     ("test -f /data/sif/llm.sif", 1, '')])
    st = cluster_llm.status(conn, HOME, CFG)
    assert not st['ready'] and 'not ready yet' in st['note']


def test_the_chat_job_takes_a_gpu_ten_cores_and_eighty_percent_of_the_memory():
    conn = FakeConn([("test -f /data/sif/llm.sif", 0, ''), ('sinfo', 0, '515500\n515500\n'), ('sbatch', 0, '12345\n')])
    assert cluster_llm.start(conn, HOME, CFG, '/data/db/llm/base-model') == '12345'
    cmd = next(c for c in conn.commands if 'sbatch' in c)
    for part in ('-p gpu', '--gres=gpu:1', '-c 10', f'--mem={int(515500 * 0.8)}M', '-A lab',
                 'MARGIE_LLM_MODEL=/data/db/llm/base-model', 'MARGIE_LLM_SIF=/data/sif/llm.sif'):
        assert part in cmd, part


def test_an_answer_comes_back_through_the_login_node():
    conn = FakeConn([('curl', 0, json.dumps({'text': ' The gene is dnaA [E1]. '}))])
    assert cluster_llm.generate(conn, 'g001.cluster', 4242, 'sys', 'q', 100) == 'The gene is dnaA [E1].'
    assert 'http://g001.cluster:4242/chat' in conn.commands[0]


def test_no_answer_is_an_error():
    conn = FakeConn([('curl', 0, json.dumps({'error': 'out of memory'}))])
    with pytest.raises(cluster_llm.LlmError, match='out of memory'):
        cluster_llm.generate(conn, 'g001', 1, 's', 'q', 10)
