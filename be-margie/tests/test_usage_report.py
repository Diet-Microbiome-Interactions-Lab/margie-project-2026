"""Each MARGIE run writes its resource use to <working folder>/resource-utilization-statistics when it
ends (workflow_tools/usage_report.py): a landscape Letter PDF of three pages at most and a row of
runs.tsv. The hosting server's use is added for the accounts the server names (hosting_usage.py)."""

import io
import json
import re
import subprocess
import zlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bioinformatics_tools.api.routers.ssh import _with_usage_report
from bioinformatics_tools.api.services import hosting_usage
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.workflow_tools import usage_report as U

RUN = '/scratch/c/u/margie/margie-output/2026-10-26-0130'
JOB = '81f3690b-1c27-4574-be89-783189e539b3'
F = U._FIELDS


def _row(**cells) -> str:
    return '\t'.join(str(cells.get(f, '')) for f in F)


def _sacct_steps(run: str) -> str:
    """Two step jobs in the run folder, one in another folder, with their steps (as sacct prints them)."""
    rows = [
        _row(JobID='501', JobName='uuid', Partition='cpu', Account='lab', AllocCPUS=8,
             AllocTRES='billing=8,cpu=8,mem=8000M,node=1', ElapsedRaw=600, CPUTimeRAW=4800,
             Submit='2026-10-26T01:31:00', Start='2026-10-26T01:32:00', End='2026-10-26T01:42:00',
             State='COMPLETED', NodeList='a1', WorkDir=run, Comment='rule_run_rasttk_wildcards_coli--a1b2c3d4'),
        _row(JobID='501.batch', MaxRSS='160784K', TRESUsageInTot='cpu=00:00:02,fs/disk=34712983,mem=160784K',
             TRESUsageOutTot='fs/disk=84267'),
        _row(JobID='501.0', MaxRSS='269076K', TRESUsageInTot='cpu=00:08:00,fs/disk=803807347,mem=269076K',
             TRESUsageOutTot='fs/disk=194554455'),
        _row(JobID='502', JobName='uuid', Partition='highmem', Account='lab', AllocCPUS=24,
             AllocTRES='billing=48,cpu=24,mem=48000M,node=1,gres/gpu=1', ElapsedRaw=3600, CPUTimeRAW=86400,
             Submit='2026-10-26T01:40:00', Start='2026-10-26T02:40:00', End='2026-10-26T03:40:00',
             State='FAILED', NodeList='b1', WorkDir=run + '/', Comment='rule_run_eggnog_wildcards_coli--a1b2c3d4'),
        _row(JobID='502.batch', MaxRSS='2G', TRESUsageInTot='cpu=10:00:00,fs/disk=2000000000',
             TRESUsageOutTot='fs/disk=1000000000'),
        _row(JobID='999', Partition='cpu', Account='lab', AllocCPUS=1, AllocTRES='cpu=1', ElapsedRaw=5,
             CPUTimeRAW=5, State='COMPLETED', WorkDir='/elsewhere', Comment='rule_other'),
    ]
    return '\n'.join(rows) + '\n'


def _sacct_driver() -> str:
    return '\n'.join([
        _row(JobID='500', JobName=f'margie-{JOB}', Partition='cpu', Account='lab', AllocCPUS=4,
             AllocTRES='billing=4,cpu=4,mem=8000M,node=1', ElapsedRaw=7200, CPUTimeRAW=28800,
             Submit='2026-10-26T01:30:00', Start='2026-10-26T01:30:12', End='Unknown', State='RUNNING',
             NodeList='a2', WorkDir='/home/u'),
        _row(JobID='500.batch', State='RUNNING'),
    ]) + '\n'


def _fake_run(calls: list, run_dir: str):
    def fake(cmd, timeout=300):
        calls.append(cmd)
        if cmd[0] == 'sacct' and '--version' in cmd:
            return 'slurm 26.05.4\n'
        if cmd[0] == 'sacct' and '-j' in cmd:
            return _sacct_driver()
        if cmd[0] == 'sacct':
            return _sacct_steps(run_dir)
        if cmd[0] == 'sstat':
            return '500.batch\tcpu=00:20:00,fs/disk=71000000000,mem=800000K\tfs/disk=17000000000\t800000K\n'
        if cmd[0] == 'scontrol':
            return 'ClusterName             = testcluster\n'
        return ''
    return fake


@pytest.fixture
def cluster(tmp_path, monkeypatch):
    """A home with the run's files and config, a working folder, a run folder and a fake SLURM."""
    home, work = tmp_path / 'home', tmp_path / 'work'
    run = work / 'margie-output' / '2026-10-26-0130'
    files = home / '.local/share/bsp/jobs'
    files.mkdir(parents=True)
    (files / f'{JOB}.jobid').write_text('500\n')
    (files / f'{JOB}.log').write_text('x' * 1000)
    db = work / 'margie-databases' / 'main.db'
    db.parent.mkdir(parents=True)
    db.write_bytes(b'd' * 5000)
    config = home / 'config.yaml'
    config.write_text(f'main_database: {db}\nmargie_sb:\n  working_folder: {work}\n')
    genomes = tmp_path / 'genomes'
    genomes.mkdir()
    (genomes / 'coli.fna').write_bytes(b'A' * 3000)
    (run / '.margie-input').mkdir(parents=True)
    (run / '.margie-input' / 'coli--a1b2c3d4.fna').symlink_to(genomes / 'coli.fna')
    monkeypatch.setattr(U, 'CONFIG', config)
    monkeypatch.setattr(U.Path, 'home', classmethod(lambda cls: home))
    calls: list = []
    monkeypatch.setattr(U, '_run', _fake_run(calls, str(run)))
    monkeypatch.setattr(U.getpass, 'getuser', lambda: 'u')
    return {'home': home, 'work': work, 'run': run, 'db': db, 'calls': calls, 'files': files}


def _pages(pdf: bytes) -> int:
    return pdf.count(b'/Type /Page ')


def _text(pdf: bytes) -> str:
    """The text the PDF's content streams show."""
    out = []
    for m in re.finditer(rb'stream\n(.*?)\nendstream', pdf, re.S):
        out.append(zlib.decompress(m.group(1)).decode('latin-1'))
    return re.sub(r'\\([()\\])', r'\1', '\n'.join(out))


def test_phase_of_names_each_rule_by_its_phase():
    assert U.phase_of('run_rasttk') == '3 Gene calling'
    assert U.phase_of('load_interpro_perdb_to_db') == '4 Function'
    assert U.phase_of('run_operon') == '5 Operons'
    assert U.phase_of('run_operon_fingerprint') == '12 Fingerprints'
    assert U.phase_of('update_operon_fingerprint_database') == '13 Fingerprint databases'
    assert U.phase_of('update_c3_occ_reference_depot') == '11 Scoring'
    assert U.phase_of('phase4_8_one_genome') == '4-8 Grouped steps'
    assert U.phase_of('run_genome_viewer_one_genome') == U.REPORTS
    assert U.phase_of('queue_sqlite_backup_snapshot') == U.OTHER


def test_slurm_values_are_read():
    assert U.duration('1-02:03:04') == 93784
    assert U.duration('05:30.5') == 330.5
    assert U.duration('Unknown') == 0
    assert U.memory('160784K') == 160784 * 1024
    assert U.memory('8000M') == 8000 * 1024 ** 2
    assert U.tres('cpu=4,fs/disk=12,gres/gpu=1') == {'cpu': '4', 'fs/disk': '12', 'gres/gpu': '1'}


def test_a_run_writes_its_report_and_ledger_row(cluster, capsys):
    U.start(JOB, str(cluster['run']))
    # The run writes its results and grows the database.
    (cluster['run'] / 'coli--a1b2c3d4').mkdir()
    (cluster['run'] / 'coli--a1b2c3d4' / 'final.tsv').write_bytes(b't' * 7000)
    (cluster['run'] / 'original_container_outputs').mkdir()
    (cluster['run'] / 'original_container_outputs' / 'cog.out').write_bytes(b'c' * 2000)
    cluster['db'].write_bytes(b'd' * 8000)
    assert U.main(['report', '--job', JOB, '--run-dir', str(cluster['run']), '--exit-code', '0']) == 0
    out = capsys.readouterr().out
    path = Path(out.split(U.MARKER)[1].strip())
    assert path == cluster['work'] / U.FOLDER / f'2026-10-26-0130--{JOB[:8]}.pdf'
    pdf = path.read_bytes()
    assert pdf.startswith(b'%PDF-1.4') and pdf.rstrip().endswith(b'%%EOF')
    assert 1 <= _pages(pdf) <= 3
    assert b'/MediaBox [0 0 792 612]' in pdf
    text = _text(pdf)
    for shown in ('Cluster use by partition', 'Cluster use by phase', '3 Gene calling', '4 Function', 'highmem',
                  'Files and space', 'Rates', 'Run driver'):
        assert shown in text
    assert 'Hosting server' not in text

    rows = (cluster['work'] / U.FOLDER / U.LEDGER).read_text().splitlines()
    assert len(rows) == 2
    row = dict(zip(rows[0].split('\t'), rows[1].split('\t')))
    # The step in another folder is not this run's.
    assert row['step_jobs'] == '2' and row['driver_job'] == '500' and row['failed_jobs'] == '1'
    assert row['core_s'] == str(4800 + 86400 + 28800)
    assert row['disk_read_bytes'] == str(34712983 + 803807347 + 2000000000 + 71000000000)
    assert row['disk_written_bytes'] == str(84267 + 194554455 + 1000000000 + 17000000000)
    assert row['gpu_s'] == '3600' and row['billing_s'] == str(8 * 600 + 48 * 3600 + 4 * 7200)
    assert row['queue_wait_s'] == str(60 + 3600 + 12)
    assert row['partitions'] == 'cpu | highmem'
    assert row['genomes'] == '1' and row['input_bytes'] == '3000'
    assert row['files_generated'] == '2' and row['bytes_generated'] == '9000'
    assert row['database_change_bytes'] == '3000'
    assert row['space_consumed_bytes'] == str(9000 + 3000 + 1000)
    stats = json.loads((cluster['files'] / f'{JOB}.usage.json').read_text())
    assert stats['report'] == str(path)

    # A second report adds a row under the same header.
    U.report(JOB, str(cluster['run']))
    assert len((cluster['work'] / U.FOLDER / U.LEDGER).read_text().splitlines()) == 3


def test_steps_are_looked_for_from_the_run_start(cluster):
    U.start(JOB, str(cluster['run']))
    U.report(JOB, str(cluster['run']))
    steps = next(c for c in cluster['calls'] if c[0] == 'sacct' and '-S' in c)
    started = json.loads((cluster['files'] / f'{JOB}.usage-start.json').read_text())['at']
    assert steps[steps.index('-S') + 1] == started[:19]


def test_without_a_start_note_steps_are_looked_for_from_the_driver(cluster):
    U.report(JOB, str(cluster['run']))
    steps = next(c for c in cluster['calls'] if c[0] == 'sacct' and '-S' in c)
    assert steps[steps.index('-S') + 1] == '2026-10-26T01:30:00'


def test_a_failing_report_leaves_the_run_as_it_was(monkeypatch, capsys):
    monkeypatch.setattr(U, 'report', MagicMock(side_effect=OSError('disk full')))
    assert U.main(['report', '--job', JOB, '--run-dir', RUN, '--exit-code', '3']) == 0
    captured = capsys.readouterr()
    assert U.MARKER not in captured.out and 'disk full' in captured.err


def _stats(jobs: int, hosting: bool) -> dict:
    job = {'id': '1', 'rule': 'run_cog', 'genome': 'g' * 60, 'partition': 'cpu', 'account': 'lab', 'cpus': 4,
           'gpus': 0, 'memory_requested': 8e9, 'state': 'COMPLETED', 'node': 'a', 'submit': '', 'start': '',
           'end': '', 'wall_s': 100, 'core_s': 400, 'cpu_s': 300.0, 'gpu_s': 0, 'billing_s': 400, 'wait_s': 5,
           'peak_memory': 1e9, 'read': 1e9, 'written': 1e8}
    rules = ['run_quast', 'run_gtdbtk_batch', 'run_rasttk', 'run_cog', 'run_operon', 'run_tmbed', 'run_envelope',
             'run_psortb', 'run_consolidation', 'run_labeling', 'run_scoring', 'run_fingerprint',
             'update_fingerprint_database', 'run_ani_batch', 'build_gene_evidence_report', 'make_annotation_gff',
             'queue_sqlite_backup_snapshot', 'phase4_8_one_genome']
    stats = {
        'version': 1, 'job': JOB, 'workflow': 'margie_sb', 'run_dir': RUN, 'run_name': '2026-10-26-0130',
        'working_folder': '/scratch/c/u/margie', 'exit_code': 0, 'started': '2026-10-26T01:30:12',
        'ended': '2026-10-26T03:30:12', 'wall_s': 7200, 'user': 'u', 'cluster': 'c', 'slurm': 'slurm 26',
        'driver': dict(job, rule=U.DRIVER), 'jobs': [dict(job, id=str(i), rule=rules[i % len(rules)]) for i in range(jobs)],
        'folder': {'groups': [{'name': 'genome folders', 'files': 10, 'bytes': 5e8}],
                   'types': [{'type': f't{i}', 'files': i, 'bytes': 1e7 * i} for i in range(14)],
                   'files': 10, 'bytes': 5e8, 'before': 0, 'inputs': {'files': 3, 'bytes': 1e7}},
        'stores': [{'label': f'Store {i}', 'path': '/p', 'files': 1, 'bytes': 2e9, 'before': 1.9e9} for i in range(7)],
        'log_bytes': 1e6, 'written_at': '2026-10-26T03:30:12', 'report': '/w/r.pdf',
    }
    if hosting:
        stats['hosting'] = {'name': 'Test host', 'host': 'pod-1', 'start': '2026-10-26T01:30:00',
                            'end': '2026-10-26T03:31:00', 'window_s': 7260, 'restarted': False, 'cpu_s': 300.0,
                            'cpu_limit': 2.0, 'mem_now': 4e8, 'mem_peak': 1e9, 'mem_limit': 6e9, 'io_read': 1e6,
                            'io_write': 2e6, 'net_rx': 3e8, 'net_tx': 1e8, 'log_bytes': 3e6}
    return stats


@pytest.mark.parametrize('hosting', [False, True])
def test_a_large_run_fits_three_landscape_pages(hosting):
    pdf = U.render(_stats(400, hosting))
    assert 1 <= _pages(pdf) <= 3
    text = _text(pdf)
    assert ('Hosting server (Test host)' in text) is hosting
    # 11 pt text, bordered cells, no fills.
    assert ' 11 Tf ' in text and ' l S' in text and ' re f' not in text and ' rg' not in text


def test_long_cells_are_shortened_to_their_column():
    doc = U.Document('t')
    doc.table('T', ['Path', 'Size GB'], [['/a/' + 'b' * 400, '1.000']], right={1})
    assert '...' in '\n'.join(doc.ops)
    assert len(doc.pages) == 1


def test_the_driver_ends_with_the_workflows_exit_code(tmp_path):
    script = _with_usage_report('(exit 3)', JOB, str(tmp_path))
    lines = script.splitlines()
    assert lines[0].startswith('timeout 600 ') and '.usage_report start ' in lines[0]
    assert lines[1] == '(exit 3)' and lines[2] == 'rc=$?'
    assert '.usage_report report ' in lines[3] and '--exit-code $rc' in lines[3]
    # Without MARGIE's python here, both calls fail and the run's exit code still comes through.
    done = subprocess.run(['bash', '-c', script.replace('~/bioinformatics-tools', str(tmp_path / 'none'))])
    assert done.returncode == 3


def test_hosting_is_added_for_the_accounts_named(monkeypatch):
    monkeypatch.setenv(hosting_usage.USERS_ENV, 'owner, clusteruser')
    assert hosting_usage.enabled('owner', 'x') and hosting_usage.enabled('site-name', 'clusteruser')
    assert not hosting_usage.enabled('someone', 'else') and not hosting_usage.enabled(None, None)
    monkeypatch.delenv(hosting_usage.USERS_ENV)
    assert not hosting_usage.enabled('owner')


def test_hosting_counters_from_cgroup_v1(tmp_path, monkeypatch):
    cg, net = tmp_path / 'cgroup', tmp_path / 'net'
    for rel, value in {'cpu,cpuacct/cpuacct.usage': '2500000000', 'cpu,cpuacct/cpu.cfs_quota_us': '200000',
                       'cpu,cpuacct/cpu.cfs_period_us': '100000', 'memory/memory.usage_in_bytes': '100',
                       'memory/memory.max_usage_in_bytes': '300', 'memory/memory.limit_in_bytes': '6442450944',
                       'blkio/blkio.throttle.io_service_bytes': '253:64 Read 10\n253:64 Write 20\n253:64 Total 30\nTotal 30'}.items():
        (cg / rel).parent.mkdir(parents=True, exist_ok=True)
        (cg / rel).write_text(value)
    for dev, rx, tx in (('eth0', 1000, 500), ('lo', 99, 99)):
        (net / dev / 'statistics').mkdir(parents=True)
        (net / dev / 'statistics' / 'rx_bytes').write_text(str(rx))
        (net / dev / 'statistics' / 'tx_bytes').write_text(str(tx))
    monkeypatch.setattr(hosting_usage, 'CGROUP', cg)
    monkeypatch.setattr(hosting_usage, 'NET', net)
    s = hosting_usage.snapshot()
    assert (s['cpu_ns'], s['cpu_limit'], s['mem_now'], s['mem_peak'], s['mem_limit']) == (2500000000, 2.0, 100, 300, 6442450944)
    assert (s['io_read'], s['io_write'], s['net_rx'], s['net_tx']) == (10, 20, 1000, 500)


def test_hosting_counters_from_cgroup_v2(tmp_path, monkeypatch):
    cg = tmp_path / 'cgroup'
    cg.mkdir()
    (cg / 'cpu.stat').write_text('usage_usec 1500000\nuser_usec 1\n')
    (cg / 'cpu.max').write_text('150000 100000')
    (cg / 'memory.current').write_text('50')
    (cg / 'memory.peak').write_text('70')
    (cg / 'memory.max').write_text('max')
    (cg / 'io.stat').write_text('8:0 rbytes=5 wbytes=6 rios=1\n8:16 rbytes=1 wbytes=1\n')
    monkeypatch.setattr(hosting_usage, 'CGROUP', cg)
    monkeypatch.setattr(hosting_usage, 'NET', tmp_path / 'none')
    s = hosting_usage.snapshot()
    assert (s['cpu_ns'], s['cpu_limit'], s['mem_now'], s['mem_peak'], s['mem_limit']) == (1500000000, 1.5, 50, 70, 0)
    assert (s['io_read'], s['io_write'], s['net_rx']) == (6, 7, 0)


def test_the_difference_counts_from_the_runs_start_or_the_servers_restart():
    start = dict(hosting_usage.BOOT, at='2026-10-26T01:00:00', epoch=1000.0, cpu_ns=1e9, net_rx=100, net_tx=10,
                 io_read=0, io_write=0)
    end = dict(start, at='2026-10-26T02:00:00', epoch=4600.0, cpu_ns=4e9, net_rx=600, net_tx=60)
    d = hosting_usage.difference(start, end)
    assert (d['window_s'], d['cpu_s'], d['net_rx'], d['net_tx'], d['restarted']) == (3600, 3.0, 500, 50, False)
    assert hosting_usage.difference(None, end)['restarted'] is True


class _Sftp:
    """An SFTP session over a dict of paths."""
    def __init__(self, files):
        self.files = files

    def open(self, path, mode='r'):
        files = self.files

        class Handle(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                data = self.getvalue()
                if 'a' in mode:
                    files[path] = files.get(path, b'') + data
                elif 'w' in mode:
                    files[path] = data

            def write(self, data):
                return super().write(data.encode() if isinstance(data, str) else data)

        if 'r' in mode:
            if path not in files:
                raise IOError(path)
            return Handle(files[path])
        return Handle()

    def stat(self, path):
        if path not in self.files:
            raise IOError(path)
        return MagicMock(st_size=len(self.files[path]))

    def close(self):
        pass


def test_the_owner_gets_the_hosting_section(monkeypatch):
    stats = _stats(5, False)
    stats['report'] = '/w/resource-utilization-statistics/r.pdf'
    files = {f'{U.RUN_FILE_DIR}/{JOB}.usage.json': json.dumps(stats).encode()}
    conn = MagicMock()
    conn.connect.return_value.open_sftp.return_value = _Sftp(files)
    monkeypatch.setenv(hosting_usage.USERS_ENV, 'owner')
    monkeypatch.setattr(hosting_usage, '_names', lambda uid: {1: ('site', 'owner'), 2: ('guest', 'g')}.get(uid, ()))
    job_store._jobs[JOB] = {'user_id': 1, 'usage_report': stats['report'], 'log_bytes': 1234,
                            'hosting_start': hosting_usage.snapshot()}
    try:
        assert hosting_usage.add_to_report(JOB, conn)
        pdf = files[stats['report']]
        assert 'Hosting server' in _text(pdf) and _pages(pdf) <= 3
        rows = files['/w/resource-utilization-statistics/hosting.tsv'].decode().splitlines()
        assert rows[0].startswith('report_written\t') and len(rows) == 2
        assert json.loads(files[f'{U.RUN_FILE_DIR}/{JOB}.usage.json'])['hosting']['log_bytes'] == 1234
        # Another account's report stays cluster-only.
        job_store._jobs[JOB]['user_id'] = 2
        assert not hosting_usage.add_to_report(JOB, conn)
    finally:
        job_store._jobs.pop(JOB, None)
