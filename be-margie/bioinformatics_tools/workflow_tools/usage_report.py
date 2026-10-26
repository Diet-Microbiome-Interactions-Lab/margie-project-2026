"""
The resource use of one MARGIE run, written when the run ends to
<working folder>/resource-utilization-statistics/<run folder>--<job>.pdf, with a row for the run in
runs.tsv beside it (seconds and bytes, for working out use across runs later).

The run's SLURM driver job calls it twice (api/routers/ssh.py, _with_usage_report): `start`, before
the workflow, measures the run folder and the MARGIE databases; `report`, after it, reads SLURM's
accounting for the driver and each step job (sacct: the steps are the jobs whose working folder is
the run folder; sstat for the driver, still running), walks the run folder and measures the
databases again. The PDF is landscape Letter, 11 pt, three pages at most, its tables bordered and
unshaded. The hosting server's own use is added by the API for the accounts it is set up for
(api/services/hosting_usage.py), which renders the PDF again from <run files>/<job>.usage.json.
A report that cannot be written is logged, and the run's exit code stays as it was.
"""
import argparse
import csv
import getpass
import io
import json
import logging
import os
import re
import socket
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import yaml

from bioinformatics_tools.utilities.ssh_slurm import RUN_FILE_DIR, run_file_stem
from bioinformatics_tools.workflow_tools.cache_report import NOT_GENOMES
from bioinformatics_tools.workflow_tools.workflow_registry import MARGIE_SB_PHASED_TOOLS

LOGGER = logging.getLogger(__name__)

FOLDER = 'resource-utilization-statistics'
LEDGER = 'runs.tsv'
HOSTING_LEDGER = 'hosting.tsv'
# The line the API reads from the run's log for the report's path (job_runner.py).
MARKER = '__USAGE_REPORT__:'
CONFIG = Path.home() / '.config' / 'bioinformatics-tools' / 'config.yaml'
VERSION = 1
GB = 1e9
# Folders in a run folder that are not a genome's.
NOT_GENOME = NOT_GENOMES | {'tmp', 'temp'}

# ---- Phases ----
PHASE_NAMES = {1: 'Quality', 2: 'Taxonomy', 3: 'Gene calling', 4: 'Function', 5: 'Operons',
               6: 'Membrane topology', 7: 'Envelope', 8: 'Localisation', 9: 'Consolidation',
               10: 'Labeling', 11: 'Scoring', 12: 'Fingerprints', 13: 'Fingerprint databases',
               14: 'ANI, AAI and closest genomes', 15: 'Gene report'}
# Rule-name parts beyond the registry's tool keys.
_EXTRA_KEYS = {'prodigal': 3, 'resolve_genome_info': 2, 'scoring': 11, 'c3_occ': 11, 'genome_pool': 14}
_PHASE_OF = {**{t['key']: t['phase'] for t in MARGIE_SB_PHASED_TOOLS}, **_EXTRA_KEYS}
# Longest first, so 'fingerprint_database' is found before 'fingerprint' and 'operon'.
_KEYS = sorted(_PHASE_OF, key=len, reverse=True)
_REPORT_RULES = ('report_figures', 'genome_viewer', 'operon_map', 'annotation_gff', 'final_annotation')
DRIVER = 'Run driver (caches, Snakemake)'
REPORTS = 'Reports and figures'
OTHER = 'Other steps'


def phase_of(rule: str) -> str:
    """The phase a Snakemake rule belongs to, as "4 Function", or the reports or other group."""
    grouped = re.search(r'phase(\d+)_(\d+)', rule)
    if grouped:
        return f'{grouped.group(1)}-{grouped.group(2)} Grouped steps'
    for key in _KEYS:
        if re.search(rf'(^|_){re.escape(key)}(_|$)', rule):
            n = _PHASE_OF[key]
            return f'{n} {PHASE_NAMES[n]}'
    if any(part in rule for part in _REPORT_RULES):
        return REPORTS
    return OTHER


# ---- Reading SLURM ----
_FIELDS = ['JobID', 'JobName', 'Partition', 'Account', 'AllocCPUS', 'AllocTRES', 'ElapsedRaw',
           'TotalCPU', 'CPUTimeRAW', 'MaxRSS', 'Submit', 'Start', 'End', 'State', 'NodeList',
           'TRESUsageInTot', 'TRESUsageOutTot', 'WorkDir', 'Comment']
_SSTAT = ['JobID', 'TRESUsageInTot', 'TRESUsageOutTot', 'MaxRSS']


def _run(cmd: list[str], timeout: int = 300) -> str:
    """A command's output, '' when it fails."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning('%s failed: %s', cmd[0], exc)
        return ''


def _table(text: str, fields: list[str]) -> list[dict]:
    rows = []
    for line in text.splitlines():
        cells = line.split('\t')
        if len(cells) == len(fields):
            rows.append(dict(zip(fields, cells)))
    return rows


def sacct(*args: str) -> list[dict]:
    return _table(_run(['sacct', '-n', '-P', '--noconvert', '--delimiter=\t', '-o', ','.join(_FIELDS), *args]), _FIELDS)


def sstat(step: str) -> list[dict]:
    return _table(_run(['sstat', '-n', '-P', '--noconvert', '--delimiter=\t', '-o', ','.join(_SSTAT), '-j', step]), _SSTAT)


def duration(text: str) -> float:
    """Seconds in a SLURM time: [D-]HH:MM:SS[.mmm] or MM:SS.mmm."""
    text = (text or '').strip()
    if not text or text in ('Unknown', 'INVALID'):
        return 0.0
    days = 0
    if '-' in text:
        d, text = text.split('-', 1)
        days = int(d)
    parts = [float(p) for p in text.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3:]
    return days * 86400 + h * 3600 + m * 60 + s


def memory(text: str) -> int:
    """Bytes in a SLURM size such as 160784K, 8000M or 1234 (--noconvert)."""
    m = re.fullmatch(r'([\d.]+)([KMGTP]?)', (text or '').strip())
    if not m:
        return 0
    return int(float(m.group(1)) * 1024 ** ' KMGTP'.index(m.group(2) or ' '))


def tres(text: str) -> dict[str, str]:
    """A TRES list (cpu=4,mem=8000M,fs/disk=123) as a dict."""
    out = {}
    for part in (text or '').split(','):
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def _when(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def job_record(alloc: dict, steps: list[dict]) -> dict:
    """One SLURM job: its allocation with its steps' use summed (CPU time, disk) or maxed (memory)."""
    alloc_tres = tres(alloc['AllocTRES'])
    cpus = int(alloc['AllocCPUS'] or 0)
    elapsed = int(alloc['ElapsedRaw'] or 0)
    gpus = int(re.match(r'\d*', alloc_tres.get('gres/gpu', '')).group() or 0)
    billing = int(re.match(r'\d*', alloc_tres.get('billing', '')).group() or cpus)
    cpu_s = sum(duration(tres(s['TRESUsageInTot']).get('cpu', '')) for s in steps)
    if not cpu_s:
        cpu_s = sum(duration(s['TotalCPU']) for s in steps) or duration(alloc['TotalCPU'])
    submit, start = _when(alloc['Submit']), _when(alloc['Start'])
    comment = alloc.get('Comment', '')
    m = re.match(r'rule_(.+?)_wildcards_(.*)$', comment) or re.match(r'rule_(.+)$', comment)
    rule = m.group(1) if m else (comment or alloc['JobName'])
    return {
        'id': alloc['JobID'], 'rule': rule, 'genome': m.group(2) if m and m.lastindex == 2 else '',
        'partition': alloc['Partition'], 'account': alloc['Account'], 'cpus': cpus, 'gpus': gpus,
        'memory_requested': memory(alloc_tres.get('mem', '')), 'state': (alloc['State'].split() or [''])[0],
        'node': alloc['NodeList'], 'submit': alloc['Submit'], 'start': alloc['Start'], 'end': alloc['End'],
        'wall_s': elapsed, 'core_s': int(alloc['CPUTimeRAW'] or cpus * elapsed), 'cpu_s': round(cpu_s, 3),
        'gpu_s': gpus * elapsed, 'billing_s': billing * elapsed,
        'wait_s': max(0, int((start - submit).total_seconds())) if submit and start else 0,
        'peak_memory': max([memory(s['MaxRSS']) for s in steps] + [0]),
        'read': sum(memory(tres(s['TRESUsageInTot']).get('fs/disk', '')) for s in steps),
        'written': sum(memory(tres(s['TRESUsageOutTot']).get('fs/disk', '')) for s in steps),
    }


def slurm_jobs(driver: str, run_dir: str, since: str = '') -> tuple[dict | None, list[dict]]:
    """The driver's record and each step job's: the jobs since `since` (else the driver's submission)
    whose working folder is the run folder."""
    folders = {run_dir.rstrip('/'), os.path.realpath(run_dir)}

    def grouped(rows: list[dict]) -> dict[str, tuple[dict, list[dict]]]:
        out: dict[str, tuple[dict, list[dict]]] = {}
        for r in rows:
            if '.' not in r['JobID']:
                out[r['JobID']] = (r, [])
        for r in rows:
            head = r['JobID'].split('.', 1)[0]
            if '.' in r['JobID'] and head in out:
                out[head][1].append(r)
        return out

    driver_job = None
    if driver:
        found = grouped(sacct('-j', driver)).get(driver)
        if found:
            alloc, parts = found
            # A running step's use comes from sstat; sacct fills it in once the step ends.
            live = {r['JobID']: r for r in sstat(f'{driver}.batch')}
            parts = [{**p, **live[p['JobID']]} if p['JobID'] in live else p for p in parts]
            driver_job = {**job_record(alloc, parts), 'rule': DRIVER}
    since = since or (driver_job or {}).get('submit', '') or 'now-7days'
    steps = []
    for alloc, parts in grouped(sacct('-u', getpass.getuser(), '-S', since[:19], '-E', 'now')).values():
        if alloc['WorkDir'].rstrip('/') in folders and alloc['JobID'] != driver:
            steps.append(job_record(alloc, parts))
    steps.sort(key=lambda j: (j['submit'], j['id']))
    return driver_job, steps


# ---- Measuring files ----
def size_of(path: str) -> tuple[int, int]:
    """Files and bytes at a path: a file, or each file under a folder (links not followed)."""
    try:
        if os.path.isfile(path):
            return 1, os.path.getsize(path)
        files = total = 0
        for root, _dirs, names in os.walk(path):
            for name in names:
                try:
                    total += os.lstat(os.path.join(root, name)).st_size
                    files += 1
                except OSError:
                    pass
        return files, total
    except OSError:
        return 0, 0


def read_config() -> dict:
    try:
        return yaml.safe_load(CONFIG.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


def stores(cfg: dict) -> list[dict]:
    """The MARGIE databases a run reads and grows (user_stores.STORES), and the output folders beside them."""
    from bioinformatics_tools.api.services.user_stores import OUTPUT_DIRS, STORES, _cfg_get
    out = []
    for s in STORES:
        key, file_name = next(iter(s['config'].items()))
        value = _cfg_get(cfg, key)
        if not isinstance(value, str) or not value.strip():
            continue
        path = value.strip()
        if s['kind'] == 'file':
            stem = path[:-len(s['ext'])] if path.endswith(s['ext']) else path
            paths = [path] + [stem + c for c in s.get('companions', [])]
        else:
            folder = os.path.dirname(path) if file_name else path
            paths = [os.path.join(folder, f) for f in s.get('base_files', [])] or [folder]
        sizes = [size_of(p) for p in paths]
        out.append({'label': s['label'], 'path': path, 'files': sum(f for f, _ in sizes), 'bytes': sum(b for _, b in sizes)})
    labels = {'scoring-archive': 'Scoring archive', 'final-tables': 'Final tables', 'sqlite/snapshots': 'Database snapshots'}
    for key, name in OUTPUT_DIRS.items():
        value = _cfg_get(cfg, key)
        if isinstance(value, str) and value.strip():
            files, total = size_of(value.strip())
            out.append({'label': labels.get(name, name), 'path': value.strip(), 'files': files, 'bytes': total})
    return out


def _type_of(name: str) -> str:
    parts = name.lower().split('.')
    if len(parts) < 2:
        return '(none)'
    if parts[-1].isdigit():
        return '(numbered)'
    return '.'.join(parts[-2:]) if parts[-1] in ('gz', 'bz2', 'xz', 'zst') and len(parts) > 2 else parts[-1]


def run_folder(run_dir: str) -> dict:
    """The run folder's files and bytes by part (genome folders, container outputs, Snakemake's state,
    top-level files) and by file type; the genomes it read come from .margie-input's links (a run from
    before those counts its genome folders, sizes unknown)."""
    groups: dict[str, list[int]] = {}
    types: dict[str, list[int]] = {}
    inputs = [0, 0]
    try:
        entries = list(os.scandir(run_dir))
    except OSError:
        entries = []
    for entry in entries:
        if entry.name == '.margie-input':
            for link in os.scandir(entry.path):
                try:
                    inputs[0] += 1
                    inputs[1] += os.stat(link.path).st_size
                except OSError:
                    pass
            continue
        if entry.is_dir(follow_symlinks=False):
            group = ('genome folders' if not entry.name.startswith('.') and entry.name not in NOT_GENOME
                     else entry.name)
            walk = os.walk(entry.path)
        else:
            group = 'top-level files'
            walk = [(run_dir, [], [entry.name])]
        for root, _dirs, names in walk:
            for name in names:
                try:
                    size = os.lstat(os.path.join(root, name)).st_size
                except OSError:
                    continue
                for table, key in ((groups, group), (types, _type_of(name))):
                    cell = table.setdefault(key, [0, 0])
                    cell[0] += 1
                    cell[1] += size
    if not inputs[0]:
        inputs = [sum(1 for e in entries if e.is_dir(follow_symlinks=False) and not e.name.startswith('.')
                      and e.name not in NOT_GENOME), None]
    return {
        'groups': [{'name': k, 'files': v[0], 'bytes': v[1]} for k, v in sorted(groups.items(), key=lambda kv: -kv[1][1])],
        'types': [{'type': k, 'files': v[0], 'bytes': v[1]} for k, v in sorted(types.items(), key=lambda kv: -kv[1][1])],
        'files': sum(v[0] for v in groups.values()), 'bytes': sum(v[1] for v in groups.values()),
        'inputs': {'files': inputs[0], 'bytes': inputs[1]},
    }


# ---- The two calls ----
def _run_files(job: str) -> Path:
    return Path.home() / RUN_FILE_DIR / run_file_stem(job)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def start(job: str, run_dir: str) -> None:
    """Notes when the run starts and the sizes of its folder and the MARGIE databases."""
    folder = run_folder(run_dir)
    snapshot = {'at': _now(), 'run_folder': {'files': folder['files'], 'bytes': folder['bytes']},
                'stores': stores(read_config())}
    Path(f'{_run_files(job)}.usage-start.json').write_text(json.dumps(snapshot))


def working_folder(cfg: dict, run_dir: str) -> str:
    chosen = ((cfg.get('margie_sb') or {}).get('working_folder') or '').strip()
    return chosen.rstrip('/') if chosen else os.path.dirname(os.path.dirname(run_dir.rstrip('/')))


def collect(job: str, run_dir: str, exit_code: int, workflow: str) -> dict:
    """Everything the report shows, as JSON-ready data."""
    base = _run_files(job)
    try:
        began = json.loads(Path(f'{base}.usage-start.json').read_text())
    except (OSError, ValueError):
        began = {}
    try:
        driver_id = Path(f'{base}.jobid').read_text().split()[0]
    except (OSError, IndexError):
        driver_id = ''
    cfg = read_config()
    driver, steps = slurm_jobs(driver_id, run_dir, (began.get('at') or '')[:19])
    started = (driver or {}).get('start') or began.get('at', '')
    # The driver is still running as it writes this; a finished one (a report written again) has its end.
    last = _when((driver or {}).get('end', ''))
    ended = last.astimezone().isoformat(timespec='seconds') if last else _now()
    first = _when(started)
    wall = ((last or datetime.now()).astimezone(timezone.utc) - first.astimezone(timezone.utc)).total_seconds() if first else 0.0
    before = {s['label']: s for s in began.get('stores', [])}
    after = stores(cfg)
    for s in after:
        s['before'] = before.get(s['label'], {}).get('bytes')
    folder = run_folder(run_dir)
    folder['before'] = (began.get('run_folder') or {}).get('bytes')
    log = Path(f'{base}.log')
    version = _run(['sacct', '--version'], 30).strip()
    cluster = next((ln.split('=', 1)[1].strip() for ln in _run(['scontrol', 'show', 'config'], 60).splitlines()
                    if ln.startswith('ClusterName')), '') or socket.gethostname()
    return {
        'version': VERSION, 'job': job, 'workflow': workflow, 'run_dir': run_dir.rstrip('/'),
        'run_name': os.path.basename(run_dir.rstrip('/')), 'working_folder': working_folder(cfg, run_dir),
        'exit_code': exit_code, 'started': started, 'ended': ended, 'wall_s': round(wall),
        'user': getpass.getuser(), 'cluster': cluster, 'slurm': version, 'driver': driver, 'jobs': steps,
        'folder': folder, 'stores': after, 'log_bytes': log.stat().st_size if log.exists() else 0,
        'written_at': ended,
    }


def report_name(stats: dict) -> str:
    return f"{stats['run_name']}--{stats['job'][:8]}.pdf"


def report(job: str, run_dir: str, exit_code: int = 0, workflow: str = 'margie_sb') -> str:
    """Writes the run's PDF and its runs.tsv row in the working folder; returns the PDF's path."""
    stats = collect(job, run_dir, exit_code, workflow)
    out = Path(stats['working_folder']) / FOLDER
    out.mkdir(parents=True, exist_ok=True)
    path = out / report_name(stats)
    stats['report'] = str(path)
    path.write_bytes(render(stats))
    Path(f'{_run_files(job)}.usage.json').write_text(json.dumps(stats))
    append_row(out / LEDGER, ledger_row(stats))
    return str(path)


# ---- Totals ----
def totals(jobs: list[dict]) -> dict:
    keys = ('wall_s', 'core_s', 'cpu_s', 'gpu_s', 'billing_s', 'wait_s', 'read', 'written')
    out = {k: sum(j[k] for j in jobs) for k in keys}
    out['jobs'] = len(jobs)
    out['failed'] = sum(1 for j in jobs if j['state'] not in ('COMPLETED', 'RUNNING', 'PENDING'))
    out['peak_memory'] = max([j['peak_memory'] for j in jobs] + [0])
    return out


def _each_job(stats: dict) -> list[dict]:
    return ([stats['driver']] if stats.get('driver') else []) + stats.get('jobs', [])


def space(stats: dict) -> dict:
    """What the run added on disk: its folder (beyond what it held at the start), the databases' growth
    and its log."""
    folder = stats['folder']
    grown = sum(s['bytes'] - s['before'] for s in stats['stores'] if s.get('before') is not None)
    made = folder['bytes'] - (folder.get('before') or 0)
    return {'folder': made, 'databases': grown, 'log': stats['log_bytes'], 'total': made + grown + stats['log_bytes']}


def ledger_row(stats: dict) -> dict:
    t = totals(_each_job(stats))
    sp = space(stats)
    jobs = _each_job(stats)
    return {
        'report_written': stats['written_at'], 'run_folder': stats['run_dir'], 'job': stats['job'],
        'workflow': stats['workflow'], 'exit_code': stats['exit_code'], 'started': stats['started'],
        'ended': stats['ended'], 'wall_s': stats['wall_s'], 'genomes': stats['folder']['inputs']['files'],
        'cluster': stats['cluster'], 'partitions': ' | '.join(sorted({j['partition'] for j in jobs})),
        'accounts': ' | '.join(sorted({j['account'] for j in jobs})),
        'driver_job': (stats.get('driver') or {}).get('id', ''), 'step_jobs': len(stats['jobs']),
        'failed_jobs': t['failed'], 'job_wall_s': t['wall_s'], 'core_s': t['core_s'], 'cpu_s': round(t['cpu_s']),
        'gpu_s': t['gpu_s'], 'billing_s': t['billing_s'], 'queue_wait_s': t['wait_s'],
        'peak_memory_bytes': t['peak_memory'], 'disk_read_bytes': t['read'], 'disk_written_bytes': t['written'],
        'input_files': stats['folder']['inputs']['files'], 'input_bytes': stats['folder']['inputs']['bytes'],
        'files_generated': stats['folder']['files'], 'bytes_generated': sp['folder'],
        'database_change_bytes': sp['databases'], 'log_bytes': sp['log'], 'space_consumed_bytes': sp['total'],
        'report': stats.get('report', ''),
    }


def write_row(fh, row: dict, header: bool) -> None:
    writer = csv.DictWriter(fh, fieldnames=list(row), delimiter='\t', lineterminator='\n')
    if header:
        writer.writeheader()
    writer.writerow(row)


def append_row(path: Path, row: dict) -> None:
    """Adds a row to a TSV ledger, with the header when the file is new."""
    new = not path.exists() or path.stat().st_size == 0
    with path.open('a', newline='') as fh:
        write_row(fh, row, new)


# ---- The PDF ----
# Helvetica and Helvetica-Bold widths for ASCII 32-126, in 1/1000 em (the standard Type 1 metrics).
_HELVETICA = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556,
              556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778,
              722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
              278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
              556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HELVETICA_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556,
                   556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667,
                   611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667,
                   667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556,
                   278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]


def text_width(text: str, size: float, bold: bool = False) -> float:
    widths = _HELVETICA_BOLD if bold else _HELVETICA
    return sum(widths[ord(c) - 32] if 32 <= ord(c) < 127 else 556 for c in text) * size / 1000


def _fit(text: str, width: float, size: float, bold: bool = False) -> str:
    """The text, shortened in the middle with '...' to fit the width."""
    if text_width(text, size, bold) <= width:
        return text
    keep = len(text)
    while keep > 4 and text_width(text[:keep // 2] + '...' + text[len(text) - keep // 2:], size, bold) > width:
        keep -= 1
    return text[:keep // 2] + '...' + text[len(text) - keep // 2:]


class Document:
    """Landscape Letter pages of text and bordered tables, written as a PDF with the base Helvetica fonts."""
    WIDTH, HEIGHT, MARGIN = 792.0, 612.0, 36.0
    SIZE = 11.0
    ROW = 14.0
    PAD = 4.0

    def __init__(self, title: str):
        self.title = title
        self.pages: list[list[str]] = []
        self.new_page()

    def new_page(self) -> None:
        self.ops: list[str] = ['0.5 w']
        self.pages.append(self.ops)
        self.y = self.HEIGHT - self.MARGIN

    def room(self, height: float) -> None:
        if self.y - height < self.MARGIN:
            self.new_page()

    def text(self, x: float, y: float, text: str, size: float = SIZE, bold: bool = False) -> None:
        raw = text.encode('cp1252', 'replace').decode('latin-1')
        raw = raw.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        self.ops.append(f"BT /{'F2' if bold else 'F1'} {size:g} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({raw}) Tj ET")

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.ops.append(f'{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S')

    def heading(self, text: str, size: float = SIZE) -> None:
        self.room(size + 6 + self.ROW * 2)
        self.text(self.MARGIN, self.y - size, text, size, bold=True)
        self.y -= size + 6

    def paragraph(self, text: str) -> None:
        """Wrapped lines at the page's width."""
        words, line = text.split(), ''
        width = self.WIDTH - 2 * self.MARGIN
        for word in words + ['']:
            trial = f'{line} {word}'.strip()
            if word and text_width(trial, self.SIZE) <= width:
                line = trial
                continue
            self.room(self.ROW)
            self.text(self.MARGIN, self.y - self.SIZE, line)
            self.y -= self.ROW
            line = word

    def table(self, title: str, head: list[str] | None, rows: list[list[str]], right: set[int] = frozenset(),
              bold: set[int] = frozenset(), last_bold: bool = False) -> None:
        """A table with a border around each cell: numbers right-aligned in the `right` columns, the
        `bold` columns and the header in bold; it goes on over the page with its header again."""
        n = len(head or rows[0])
        cells = ([head] if head else []) + rows
        strong = [r is head or (last_bold and r is rows[-1]) for r in cells]
        widths = [max(text_width(r[i], self.SIZE, bold=(i in bold or s)) for r, s in zip(cells, strong))
                  + 2 * self.PAD for i in range(n)]
        room = self.WIDTH - 2 * self.MARGIN
        # Too wide: the widest text column narrows a point at a time, down to its header's width.
        least = [max(40.0, text_width(head[i], self.SIZE, True) + 2 * self.PAD) if head else 40.0 for i in range(n)]
        over = sum(widths) - room
        while over > 0:
            texts = [i for i in range(n) if i not in right and widths[i] > least[i]]
            if not texts:
                break
            widest = max(texts, key=lambda i: widths[i])
            cut = min(1.0, over, widths[widest] - least[widest])
            widths[widest] -= cut
            over -= cut
        xs = [self.MARGIN]
        for w in widths:
            xs.append(xs[-1] + w)
        # A short table starts on the next page rather than split.
        if len(cells) <= 12:
            self.room(self.SIZE + 6 + self.ROW * len(cells))
        self.heading(title)
        top = self.y

        def close(bottom: float) -> None:
            self.line(xs[0], bottom, xs[-1], bottom)
            for x in xs:
                self.line(x, top, x, bottom)

        def draw(row: list[str], strong: bool) -> None:
            self.line(xs[0], self.y, xs[-1], self.y)
            base = self.y - self.ROW + 4.2
            for i, cell in enumerate(row):
                b = strong or i in bold
                cell = _fit(cell, widths[i] - 2 * self.PAD, self.SIZE, b)
                x = xs[i + 1] - self.PAD - text_width(cell, self.SIZE, b) if i in right else xs[i] + self.PAD
                self.text(x, base, cell, bold=b)
            self.y -= self.ROW

        if head:
            draw(head, True)
        for k, row in enumerate(rows):
            if self.y - self.ROW < self.MARGIN:
                close(self.y)
                self.new_page()
                self.heading(f'{title} (continued)')
                top = self.y
                if head:
                    draw(head, True)
            draw(row, last_bold and k == len(rows) - 1)
        close(self.y)
        self.y -= 10

    def pdf(self) -> bytes:
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'',
                   b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
                   b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>']
        kids = []
        for k, ops in enumerate(self.pages, 1):
            ops = ops + []
            footer = f'Page {k} of {len(self.pages)}'
            raw = f"BT /F1 9 Tf 1 0 0 1 {self.WIDTH - self.MARGIN - text_width(footer, 9):.2f} 20 Tm ({footer}) Tj ET"
            data = zlib.compress('\n'.join(ops + [raw]).encode('latin-1'))
            objects.append(b'<< /Length %d /Filter /FlateDecode >>\nstream\n' % len(data) + data + b'\nendstream')
            objects.append(('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R '
                            '/F2 4 0 R >> >> /Contents %d 0 R >>' % (self.WIDTH, self.HEIGHT, len(objects))).encode())
            kids.append(len(objects))
        objects[1] = ('<< /Type /Pages /Kids [%s] /Count %d >>' % (' '.join(f'{k} 0 R' for k in kids), len(kids))).encode()
        title = self.title.encode('cp1252', 'replace').decode('latin-1').replace('\\', '').replace('(', '[').replace(')', ']')
        objects.append(f'<< /Title ({title}) /Producer (MARGIE) >>'.encode('latin-1'))
        out = io.BytesIO()
        out.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = []
        for n, body in enumerate(objects, 1):
            offsets.append(out.tell())
            out.write(b'%d 0 obj\n' % n + body + b'\nendobj\n')
        xref = out.tell()
        out.write(b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1))
        for off in offsets:
            out.write(b'%010d 00000 n \n' % off)
        out.write(b'trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n'
                  % (len(objects) + 1, len(objects), xref))
        return out.getvalue()


# ---- What the PDF says ----
def _h(seconds: float) -> str:
    return f'{seconds / 3600:,.3f}'


def _gb(nbytes: float | None) -> str:
    return '' if nbytes is None else f'{nbytes / GB:,.3f}'


def _signed_gb(nbytes: float | None) -> str:
    return '' if nbytes is None else f'{nbytes / GB:+,.3f}'


def _pct(part: float, whole: float) -> str:
    return f'{100 * part / whole:.1f}' if whole else ''


def _per(value: float, by: float, fmt: str = '{:,.3f}') -> str:
    return fmt.format(value / by) if by else ''


_USE_HEAD = ['Jobs', 'Failed', 'Job h', 'Core h', 'CPU h', 'CPU %', 'Peak mem GB', 'Read GB', 'Written GB', 'Wait h']


def _use(t: dict) -> list[str]:
    return [f"{t['jobs']:,}", f"{t['failed']:,}", _h(t['wall_s']), _h(t['core_s']), _h(t['cpu_s']),
            _pct(t['cpu_s'], t['core_s']), _gb(t['peak_memory']), _gb(t['read']), _gb(t['written']), _h(t['wait_s'])]


def _by(jobs: list[dict], key) -> list[tuple[str, dict]]:
    groups: dict[str, list[dict]] = {}
    for j in jobs:
        groups.setdefault(key(j), []).append(j)
    return [(k, totals(v)) for k, v in groups.items()]


def _phase_order(label: str) -> tuple:
    first = re.match(r'(\d+)', label)
    return (0, 0) if label == DRIVER else (1, int(first.group(1)), label) if first else (2, label == OTHER)


def _blocks(stats: dict, optional: tuple[str, ...]) -> list:
    jobs = _each_job(stats)
    t = totals(jobs)
    sp = space(stats)
    folder = stats['folder']
    genomes = folder['inputs']['files']
    states: dict[str, int] = {}
    for j in stats['jobs']:
        states[j['state'].lower()] = states.get(j['state'].lower(), 0) + 1
    d = stats.get('driver') or {}
    status = 'completed' if stats['exit_code'] == 0 else f"failed (exit code {stats['exit_code']})"
    gpu = any(j['gpus'] for j in jobs)
    run = [
        ['Run folder', stats['run_dir'], 'Status', status],
        ['Working folder', stats['working_folder'], 'Workflow', stats['workflow']],
        ['Job', stats['job'], 'Genomes', f'{genomes:,}'],
        ['Started', stats['started'][:19].replace('T', ' '), 'Ended', stats['ended'][:19].replace('T', ' ')],
        ['Wall time', f"{_h(stats['wall_s'])} h", 'Cluster', f"{stats['cluster']} ({stats['slurm']})".replace(' ()', '')],
        ['User', stats['user'], 'Accounts', ' | '.join(sorted({j['account'] for j in jobs})) or '-'],
        ['Driver job', f"{d.get('id', '-')} ({d.get('partition', '')}, {d.get('cpus', 0)} CPUs, {_gb(d.get('memory_requested', 0))} GB)" if d else '-',
         'Step jobs', f"{len(stats['jobs']):,}" + (f" ({', '.join(f'{n:,} {s}' for s, n in sorted(states.items()))})" if states else '')],
        ['Partitions', ' | '.join(sorted({j['partition'] for j in jobs})) or '-', 'Billing h', _h(t['billing_s'])],
    ]
    head = ['Partition'] + _USE_HEAD + (['GPU h'] if gpu else [])
    parts = [[p] + _use(v) + ([_h(v['gpu_s'])] if gpu else []) for p, v in sorted(_by(jobs, lambda j: j['partition']))]
    parts.append(['Total'] + _use(t) + ([_h(t['gpu_s'])] if gpu else []))
    phases = [[p] + _use(v) for p, v in sorted(_by(jobs, lambda j: DRIVER if j['rule'] == DRIVER else phase_of(j['rule'])),
                                               key=lambda kv: _phase_order(kv[0]))]
    phases.append(['Total'] + _use(t))
    files = [['Genomes read (input)', f"{folder['inputs']['files']:,}", '', _gb(folder['inputs']['bytes']), '', 'read']]
    for g in folder['groups']:
        files.append([f"Run folder: {g['name']}", f"{g['files']:,}", '', _gb(g['bytes']), '', 'written'])
    files.append(['Run folder, in all', f"{folder['files']:,}", _gb(folder.get('before')), _gb(folder['bytes']),
                  _signed_gb(sp['folder']), 'generated by the run'])
    files.append(['Run log', '1', '', _gb(stats['log_bytes']), _signed_gb(stats['log_bytes']), 'beside the run files'])
    for s in stats['stores']:
        change = None if s.get('before') is None else s['bytes'] - s['before']
        files.append([s['label'], f"{s['files']:,}", _gb(s.get('before')), _gb(s['bytes']), _signed_gb(change),
                      'read and grown' if change else 'read'])
    files.append(['Space consumed', '', '', '', _signed_gb(sp['total']), 'run folder, log and databases'])
    wall, core = stats['wall_s'], t['core_s']
    rate_rows = [
        ('Space consumed (GB)', sp['total'] / GB, '{:,.3f}'),
        ('Data read from disk (GB)', t['read'] / GB, '{:,.3f}'),
        ('Data written to disk (GB)', t['written'] / GB, '{:,.3f}'),
        ('Files generated', folder['files'], '{:,.0f}'),
        ('Core hours allocated', core / 3600, '{:,.3f}'),
        ('CPU hours used', t['cpu_s'] / 3600, '{:,.3f}'),
        ('Queue wait hours', t['wait_s'] / 3600, '{:,.3f}'),
    ]
    rates = [[name, fmt.format(v), _per(v, wall / 3600), _per(v, core / 3600), _per(v, genomes)]
             for name, v, fmt in rate_rows]
    blocks = [
        ('table', 'Run', None, run, set(), {0, 2}, False),
        ('table', 'Cluster use by partition (SLURM accounting)', head, parts, set(range(1, len(head))), set(), True),
        ('table', 'Cluster use by phase', ['Phase'] + _USE_HEAD, phases, set(range(1, 11)), set(), True),
        ('table', 'Rates', ['Measure', 'Total', 'Per wall hour', 'Per core hour', 'Per genome'], rates, {1, 2, 3, 4}, set(), False),
        ('table', 'Files and space', ['Item', 'Files', 'Before GB', 'After GB', 'Change GB', 'Note'], files, {1, 2, 3, 4}, set(), True),
    ]
    if 'types' in optional:
        types = folder['types'][:8]
        rest = folder['types'][8:]
        if rest:
            types = types + [{'type': f'{len(rest)} other types', 'files': sum(x['files'] for x in rest),
                              'bytes': sum(x['bytes'] for x in rest)}]
        blocks.append(('table', 'Run folder by file type', ['Type', 'Files', 'Size GB', 'Share %'],
                       [[x['type'], f"{x['files']:,}", _gb(x['bytes']), _pct(x['bytes'], folder['bytes'])] for x in types],
                       {1, 2, 3}, set(), False))
    if 'largest' in optional:
        biggest = sorted(stats['jobs'], key=lambda j: -j['core_s'])[:8]
        if biggest:
            blocks.append(('table', 'Largest step jobs', ['Job', 'Step', 'Genome', 'CPUs', 'Core h', 'CPU h',
                                                          'Peak mem GB', 'Read GB', 'Written GB', 'State'],
                           [[j['id'], j['rule'], j['genome'] or '-', str(j['cpus']), _h(j['core_s']), _h(j['cpu_s']),
                             _gb(j['peak_memory']), _gb(j['read']), _gb(j['written']), j['state'].lower()]
                            for j in biggest], set(range(3, 9)), set(), False))
    hosting = stats.get('hosting')
    if hosting:
        hw = hosting['window_s'] / 3600
        rows = [
            ['Server', hosting['name'], '', hosting.get('host', '')],
            ['Window', f"{_h(hosting['window_s'])} h", '',
             f"{hosting['start'][:19].replace('T', ' ')} to {hosting['end'][:19].replace('T', ' ')}"
             + (', from the server\'s restart' if hosting.get('restarted') else '')],
            ['CPU hours used', _h(hosting['cpu_s']), _per(hosting['cpu_s'] / 3600, hw),
             f"of {hosting['cpu_limit']:g} CPUs allowed ({_h(hosting['cpu_limit'] * hosting['window_s'])} CPU h)" if hosting.get('cpu_limit') else ''],
            ['Memory (GB)', _gb(hosting['mem_now']), '',
             f"peak {_gb(hosting['mem_peak'])} since the server started" + (f", limit {_gb(hosting['mem_limit'])}" if hosting.get('mem_limit') else '')],
            ['Network received (GB)', _gb(hosting['net_rx']), _per(hosting['net_rx'] / GB, hw), 'by the server, from each client and cluster'],
            ['Network sent (GB)', _gb(hosting['net_tx']), _per(hosting['net_tx'] / GB, hw), 'by the server, to each client and cluster'],
            ['Disk read (GB)', _gb(hosting['io_read']), _per(hosting['io_read'] / GB, hw), ''],
            ['Disk written (GB)', _gb(hosting['io_write']), _per(hosting['io_write'] / GB, hw), ''],
            ["This run's log received (GB)", _gb(hosting['log_bytes']), _per(hosting['log_bytes'] / GB, hw), 'streamed to the site as the run went'],
        ]
        blocks.append(('table', f"Hosting server ({hosting['name']}) while the run went", ['Measure', 'Value', 'Per wall hour', 'Note'],
                       rows, {1, 2}, set(), False))
    blocks.append(('notes', [
        'Job h: the jobs\' wall-clock hours added up. Core h: CPUs allocated x wall time (what SLURM charges). CPU h: the CPU '
        'time the jobs\' processes used; CPU % = CPU h / Core h. Read and Written: bytes the jobs\' processes read from and '
        'wrote to disk (SLURM fs/disk). Wait h: hours in the queue before starting. GB = 10^9 bytes.',
        'Network transfers from the cluster, such as RASTtk\'s calls to its online service, are outside SLURM\'s accounting. '
        'Space consumed is the run folder\'s growth, the run log and the change in the MARGIE databases and output folders. '
        + ('The hosting server\'s counters cover each user\'s activity during the window.' if hosting else ''),
        f"Each run adds a row of these figures, in seconds and bytes, to {FOLDER}/{LEDGER}"
        + (f' (and the hosting server\'s to {HOSTING_LEDGER})' if hosting else '') + '.',
    ]))
    return blocks


def render(stats: dict, max_pages: int = 3) -> bytes:
    """The report as a PDF of three pages at most: the largest jobs, then the file types, drop out if it runs over."""
    for optional in (('types', 'largest'), ('types',), ()):
        doc = Document(f"MARGIE resource use: {stats['run_name']}")
        doc.heading(f"MARGIE resource use | run {stats['run_name']} | job {stats['job'][:8]}", 14)
        doc.paragraph(f"Written {stats['written_at'][:19].replace('T', ' ')}, when the run ended. Times are in hours, sizes in GB (10^9 bytes).")
        for block in _blocks(stats, optional):
            if block[0] == 'table':
                _, title, head, rows, right, bold, last_bold = block
                doc.table(title, head, rows, right, bold, last_bold)
            else:
                for text in block[1]:
                    doc.paragraph(text)
        if len(doc.pages) <= max_pages:
            break
    return doc.pdf()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('action', choices=('start', 'report'))
    parser.add_argument('--job', required=True)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--exit-code', type=int, default=0)
    parser.add_argument('--workflow', default='margie_sb')
    args = parser.parse_args(argv)
    try:
        if args.action == 'start':
            start(args.job, args.run_dir)
        else:
            path = report(args.job, args.run_dir, args.exit_code, args.workflow)
            print(f'Resource use for this run: {path}', flush=True)
            print(f'{MARKER}{path}', flush=True)
    except Exception as exc:  # the run's own result stands
        print(f'The resource report could not be written: {exc}', file=sys.stderr, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
