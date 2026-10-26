'''
Workflow tools generate
Invoked: $ dane_wf wf: example <params/options/io>
'''
import hashlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import yaml

from bioinformatics_tools.file_classes.base_classes import command
from bioinformatics_tools.workflow_tools.bapptainer import (
    CacheSifError, cache_sif_files, locate_local_sif_files)
from bioinformatics_tools.workflow_tools.models import WorkflowKey
from bioinformatics_tools.workflow_tools.output_cache import (
    cached_tools, cached_when, current_rast_genome_id, gene_calls_match, gene_hashes, log_workflow_run, rast_genome_ids,
    realign_rast_genome_id, restore, restore_all, store, store_all,
)
from bioinformatics_tools.workflow_tools.load_to_db import is_already_processed, PIPELINE_VERSION, fasta_hashes
from bioinformatics_tools.workflow_tools import cache_report, protein_cache
from bioinformatics_tools.workflow_tools.programs import ProgramBase
from bioinformatics_tools.workflow_tools.workflow_helpers import (
    discover_genomes, genome_stem, get_workflow_prefix_for, WORKFLOW_PATH_DEFAULTS, genome_calls, gene_call_files)
from bioinformatics_tools.workflow_tools.workflow_registry import (
    MARGIE_SB_PHASED_TOOLS,
    MARGIE_SB_REQUIRED_TOOLS,
    QUAST_AT_ONCE,
    STAGE2_AT_ONCE,
    WORKFLOWS,
    margie_sb_sif_files,
)

LOGGER = logging.getLogger(__name__)


# Consolidation merges every tool table in a genome's folder, and labeling reads only what it
# merged: their cache entries are keyed by those tables too, so a different tool set, or a
# tool's changed output, reruns them instead of bringing back a merge of other tables.
INPUT_KEYED_STEPS = ('consolidation', 'labeling')
_CONSOLIDATION_SHARED = None


def _consolidation_shared():
    '''Returns consolidation/_shared.py (a folder of scripts, not a package), loaded once.'''
    global _CONSOLIDATION_SHARED
    if _CONSOLIDATION_SHARED is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_margie_consolidation_shared', Path(__file__).parent / 'consolidation' / '_shared.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CONSOLIDATION_SHARED = module
    return _CONSOLIDATION_SHARED


def name_clashes(db_path: str, genome_files: dict[str, str]) -> list[str]:
    """Genome names this run shares with another genome (other DNA) in the database. A name counts
    when none of the genomes recorded under it (run_log, genome_proteomes) has this genome's hash."""
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True, timeout=60)
    known: dict[str, set[str]] = {}
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if 'run_log' in tables and {'organism_name', 'fasta_hash'} <= {r[1] for r in conn.execute('PRAGMA table_info(run_log)')}:
            for name, h in conn.execute("SELECT DISTINCT organism_name, fasta_hash FROM run_log "
                                        "WHERE organism_name IS NOT NULL AND organism_name != '' AND fasta_hash IS NOT NULL AND fasta_hash != ''"):
                known.setdefault(name, set()).add(h)
        if 'genome_proteomes' in tables:
            for h, names in conn.execute('SELECT genome_hash, names FROM genome_proteomes'):
                for name in json.loads(names or '[]'):
                    known.setdefault(name, set()).add(h)
    finally:
        conn.close()
    return [name for name, path in sorted(genome_files.items())
            if name in known and not known[name] & set(fasta_hashes(path))]


# A genome's name in a run and its results: its file's name, two dashes and the first 8 characters
# of its genome hash (coli--a1b2c3d4), so genomes that share a file name stay apart everywhere.
NAMED_WITH_HASH = re.compile(r'--[0-9a-f]{8}$')


def name_with_hash(name: str, path: str) -> str:
    """<name>--<the first 8 characters of the genome's hash>; a name that already ends in its own is kept."""
    short = fasta_hashes(path)[0][:8]
    return name if name.endswith(f'--{short}') else f'{NAMED_WITH_HASH.sub("", name)}--{short}'


def named_with_hash(genome_files: dict[str, str], folder: str) -> str:
    """A folder of links, one a genome, named <name>--<its hash>: the run reads its genomes from it,
    so Snakemake and the run's own steps see the same names. The files stay as they are. Returns
    the folder."""
    links = Path(folder)
    links.mkdir(parents=True, exist_ok=True)
    for old in links.iterdir():
        if old.is_symlink():
            old.unlink()
    for name, path in genome_files.items():
        source = Path(path).resolve()
        suffix = source.name[len(genome_stem(source.name)):]
        (links / f'{name_with_hash(name, path)}{suffix}').symlink_to(source)
    return str(links)


def merged_inputs_fingerprint(genome_dir: str) -> str:
    '''Returns a hash of what consolidation reads in a genome's folder: each tool table that
    consolidation/_shared.discover_tool_tables finds, and genome_info/genome_info.tsv.'''
    root = Path(genome_dir)
    digest = hashlib.sha256()
    for name, path in [*_consolidation_shared().discover_tool_tables(root, set()),
                       ('genome_info', root / 'genome_info' / 'genome_info.tsv')]:
        if not Path(path).is_file():
            continue
        digest.update(f'{name}\0{Path(path).name}\0'.encode())
        with open(path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                digest.update(chunk)
        digest.update(b'\0')
    return digest.hexdigest()[:16]


def input_keyed(key: str) -> bool:
    return key.split('@')[0] in INPUT_KEYED_STEPS


def cache_name(key: str, fingerprint: str) -> str:
    '''The output-cache name a step is stored under: its cache-map key, plus the merged tables'
    fingerprint for consolidation and labeling.'''
    return f'{key}#{fingerprint}' if input_keyed(key) else key


# Mirrors margie_sb.smk's INTERPRO_ANALYSIS_TO_BASENAME; the .smk is not importable.
INTERPRO_DB_BASENAMES = [
    "antifam", "cdd", "coils", "funfam", "gene3d", "hamap", "mobidb", "ncbifam",
    "panther", "pfam", "pirsf", "pirsr", "prints", "prosite_patterns",
    "prosite_profiles", "sfld", "smart", "superfamily",
]
WORKFLOW_DIR = Path(__file__).parent

# Not 'all': it would clamp every rule's threads to the small driver allocation.
SLURM_MODE_CORES = 256


# Snakemake's scheduler repeats these each cycle with --verbose: they name no step, and over a long
# run they made most of a 1.3 GB job log (and of the driver's memory). Job blocks, "N of M steps",
# SLURM job ids and errors still go through.
_SNAKEMAKE_CHATTER = re.compile(
    r'^\s*(Status query timing|Resources (before|after) job selection|Ready jobs:|Selected jobs:|'
    r'Select jobs to execute|Solving job selection|Waiting for running jobs to complete|Execute \d+ jobs)')


def _chatter(line: str) -> bool:
    return bool(_SNAKEMAKE_CHATTER.match(line))


# A cache read or write that failed (_safely), told apart from a None result.
_FAILED = object()


def _safely(what: str, fn, *args, **kwargs):
    """Runs one read or write of the MARGIE database for the run's caches: a busy or failing
    database is logged and the run goes on (the step is not cached this time). Returns fn's result,
    or _FAILED."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        LOGGER.warning('%s failed (the run goes on without it): %s', what, exc)
        return _FAILED


def _subprocess_env() -> dict:
    '''Returns the env for every snakemake subprocess, with BASH_ENV set to Lmod's
    init script so the envmodules rules (signalp4/signalp6) find `module`.'''
    env = os.environ.copy()
    env['BASH_ENV'] = '/etc/profile.d/modules.sh'
    return env


def _snakemake_executable() -> str:
    '''Returns the snakemake binary beside the running interpreter, since dane_wf
    may run from a venv whose bin/ is not on PATH.
    '''
    candidate = Path(sys.executable).parent / 'snakemake'
    return str(candidate) if candidate.exists() else 'snakemake'


class _BackgroundProcess:
    '''Handle returned by WorkflowBase._start_background_subprocess(): a Popen
    whose output is drained on background threads, so .poll()/.wait() never block.'''

    def __init__(self, proc: subprocess.Popen, stdout_lines: list[str], stderr_lines: list[str]):
        self.proc = proc
        self.stdout_lines = stdout_lines
        self.stderr_lines = stderr_lines

    def poll(self):
        '''Returns None while running, else the process's exit code.'''
        return self.proc.poll()

    def wait(self) -> int:
        return self.proc.wait()


class _Stage1Waves:
    '''Stage 1 as up to three Snakemake invocations behind one
    _BackgroundProcess-shaped handle.

    GTDB-Tk runs as one batch while output_cache restores it per genome, so:

      batch    GTDB-Tk, only when some genome still needs it
      ready    RASTtk for genomes whose GTDB-Tk outputs are already on disk
      pending  RASTtk for the rest, started once the batch has landed

    "ready" runs alongside "batch"; the RASTtk waves never overlap, since
    BV-BRC must see one submission at a time.
    '''

    def __init__(self, launch, batch_targets, ready_targets, pending_targets):
        self._launch = launch          # (targets, label) -> _BackgroundProcess | None
        self._lock = threading.Lock()
        self._procs: list = []
        self._launch_failed = False
        self._done = threading.Event()
        self._thread = threading.Thread(
            target=self._drive, args=(batch_targets, ready_targets, pending_targets), daemon=True)
        self._thread.start()

    def _start(self, targets, label):
        if not targets:
            return None
        proc = self._launch(targets, label)
        if proc is None:
            self._launch_failed = True
            return None
        with self._lock:
            self._procs.append(proc)
        return proc

    def _drive(self, batch_targets, ready_targets, pending_targets):
        try:
            batch = self._start(batch_targets, 'GTDB-Tk batch')
            ready = self._start(ready_targets, 'RASTtk, GTDB-Tk already available')
            for proc in (batch, ready):
                if proc is not None:
                    proc.wait()
            # Starts only after the batch lands and the first RASTtk wave exits.
            rest = self._start(pending_targets, 'RASTtk, after GTDB-Tk batch')
            if rest is not None:
                rest.wait()
        finally:
            self._done.set()

    def poll(self):
        '''Returns None until every wave has finished, then the first non-zero exit code.'''
        if not self._done.is_set():
            return None
        if self._launch_failed:
            return 1
        with self._lock:
            return next((rc for p in self._procs if (rc := p.poll())), 0)

    def wait(self) -> int:
        self._done.wait()
        return self.poll()


class WorkflowBase(ProgramBase):
    '''Snakemake workflow execution. Inherits single-program commands from ProgramBase.
    '''

    def __init__(self, workflow_id=None):
        LOGGER.debug('Starting __init__ of WorkflowBase')
        self.workflow_id = workflow_id
        self.timestamp = datetime.now().strftime("%d%m%y-%H%M")

        LOGGER.debug('Using the workflow id of %s', self.workflow_id)

        super().__init__()

    def build_executable(self, key: WorkflowKey, config_overrides: dict = None, mode='slurm', compute_config: dict = None,
                          extra_resources: dict = None, rerun_triggers: str = None, target: str = None,
                          max_jobs_override: int = None) -> list[str]:
        '''
        Build snakemake command from workflow key and config.

        Args:
            key: WorkflowKey defining the workflow
            config_overrides: Only workflow-specific overrides (input_fasta, output_dir, main_database)
            mode: Execution mode ('dev' for local-only; anything else uses slurm executor)
            compute_config: Compute cluster config (account, partition, resources)
            extra_resources: Optional named Snakemake resources (--resources k=v ...)
                capping a group of rules independently of --jobs, e.g.
                {'margie_sb_phase4_slot': 4}.
            rerun_triggers: Optional --rerun-triggers value; resume uses 'mtime'
                because a resumed run's output_dir has a new timestamp.
            target: Optional Snakemake target rule (e.g. 'rasttk_all') or list of
                file targets, placed before --config. Adds --nolock, since Stage 1
                and Stage 2 run concurrently on disjoint rules in one directory.
            max_jobs_override: --jobs value that wins over compute_config's
                max_jobs (QUAST's own run uses it).
        '''
        smk_path = WORKFLOW_DIR / key.snakemake_file

        # Use compute config to determine max_jobs (default to 5)
        max_jobs = 5
        if compute_config:
            max_jobs = compute_config.get('max_jobs', 5)
        if max_jobs_override is not None:
            max_jobs = max_jobs_override

        # 'all' only in dev mode, where every rule runs locally (see SLURM_MODE_CORES).
        cores = 'all' if mode == 'dev' else SLURM_MODE_CORES

        # apptainer_binds: a list, or one string split on commas or spaces.
        # The config's get(key) raises for a missing key, so a default is always given.
        raw_binds = (getattr(self, 'conf', None) or {}).get('apptainer_binds', None) or []
        binds = [str(b).strip() for b in (raw_binds.replace(',', ' ').split() if isinstance(raw_binds, str) else raw_binds)
                 if str(b).strip()]

        core_command = [
            _snakemake_executable(),
            '-s', str(smk_path),
            f'--cores={cores}',
            '--keep-going',
            '--use-apptainer',
            '--sdm=apptainer',
            # Extra folders the containers see (apptainer_binds in config.yaml); most clusters
            # already bind home, scratch and group storage themselves.
            *(['--apptainer-args', ' '.join(f'-B {b}' for b in binds)] if binds else []),
            # Needed by signalp4/signalp6, the only envmodules: rules.
            '--use-envmodules',
            # Prints each job's rule/wildcards/jobid block, which run_ssh_task reads.
            '--verbose',
            f'--jobs={max_jobs}',
            '--latency-wait=60',
            '--scheduler=greedy',
        ]

        if target:
            core_command.append('--nolock')
            # A list means explicit file targets (Stage 1 subsets, see _Stage1Waves).
            core_command.extend([target] if isinstance(target, str) else list(target))

        # Check for dry-run/test mode (from config or command line)
        if self.conf.get('dry_run', False) or self.conf.get('test_only', False):
            core_command.append('--dry-run')
            LOGGER.info("Running in DRY-RUN mode - no actual execution")

        if mode != 'dev':
            core_command.append('--executor=slurm')

        # Add default SLURM resources from compute config
        if mode != 'dev' and compute_config:
            default_resources = ['--default-resources']
            min_runtime_minutes = 240

            # Required: account
            account = compute_config.get('account', '').strip()
            if account:
                default_resources.append(f'slurm_account={account}')

            # Optional: partition
            partition = compute_config.get('partition', '').strip()
            if partition:
                default_resources.append(f'slurm_partition={partition}')

            # Default runtime (at least 4 hours) and memory. The runtime carries its unit: Snakemake
            # reads a bare number on the command line as seconds, so runtime=240 gave 4-minute jobs.
            try:
                runtime_minutes = int(compute_config.get('default_runtime', min_runtime_minutes))
            except (TypeError, ValueError):
                runtime_minutes = min_runtime_minutes
            runtime_minutes = max(min_runtime_minutes, runtime_minutes)
            default_resources.append(f'runtime={runtime_minutes}m')

            if 'default_mem_mb' in compute_config:
                default_resources.append(f'mem_mb={compute_config["default_mem_mb"]}')

            # Only add if we have at least the account
            if len(default_resources) > 1:
                core_command.extend(default_resources)

        # Pass original config file(s) to Snakemake to preserve types
        # This loads the full user config with proper int/bool/nested dict types
        if hasattr(self, 'config_paths') and self.config_paths:
            for config_path in self.config_paths:
                core_command.extend(['--configfile', str(config_path)])

        # Override only workflow-specific values (all strings, so no type issues)
        if config_overrides:
            config_pairs = [f'{k}={v}' for k, v in config_overrides.items()]
            core_command.append('--config')
            core_command.extend(config_pairs)

        # Named resources cap a group of rules independently of --jobs.
        if extra_resources:
            core_command.append('--resources')
            core_command.extend(f'{k}={v}' for k, v in extra_resources.items())

        if rerun_triggers:
            core_command.extend(['--rerun-triggers', rerun_triggers])

        return core_command

    @staticmethod
    def _parse_snakemake_output(stderr: str) -> dict:
        '''Best-effort parse of snakemake stderr for structured reporting.'''
        result = {'total': 0, 'completed': 0, 'failed': 0, 'failed_rules': []}

        # Extract "X of Y steps (Z%) done"
        steps_match = re.search(r'(\d+) of (\d+) steps \(\d+%\) done', stderr)
        if steps_match:
            result['completed'] = int(steps_match.group(1))
            result['total'] = int(steps_match.group(2))

        # Extract failed rule names from "Error in rule <name>:"
        failed_rules = re.findall(r'Error in rule (\w+):', stderr)
        result['failed_rules'] = failed_rules
        result['failed'] = len(failed_rules)

        # If we found failed rules but no total, estimate total from completed + failed
        if result['failed'] and not result['total']:
            result['total'] = result['completed'] + result['failed']

        return result

    def _run_subprocess(self, wf_command):
        '''Wrapper for subprocess.run(). Returns CompletedProcess on any exit
        code (even non-zero), or None on launch failure (e.g. snakemake not installed).'''
        LOGGER.debug('Received command and running: %s', wf_command)

        # Pin snakemake's working directory to output_dir so that .snakemake/
        # and any relative rule paths resolve there, regardless of the SSH
        # session's CWD on the cluster.
        output_dir = self.conf.get('output_dir', '')
        cwd = output_dir or None
        if cwd:
            Path(cwd).mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.Popen(
                wf_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=cwd, env=_subprocess_env(),
            )

            # Collect stderr on a background thread so it doesn't block stdout reads.
            stderr_lines: list[str] = []

            def _read_stderr():
                for line in proc.stderr:
                    line = line.rstrip()
                    if _chatter(line):
                        continue
                    LOGGER.info('[snakemake] %s', line)
                    stderr_lines.append(line)

            stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
            stderr_thread.start()

            stdout_lines: list[str] = []
            for line in proc.stdout:
                line = line.rstrip()
                if _chatter(line):
                    continue
                LOGGER.info('[snakemake] %s', line)
                stdout_lines.append(line)

            stderr_thread.join()
            proc.wait()

            return subprocess.CompletedProcess(
                args=wf_command,
                returncode=proc.returncode,
                stdout='\n'.join(stdout_lines),
                stderr='\n'.join(stderr_lines),
            )
        except Exception as e:
            LOGGER.error('Failed to launch subprocess %s: %s', wf_command[0], e)
            self.failed(f'Failed to launch subprocess: {e}')
            return None

    def _start_background_subprocess(self, wf_command) -> '_BackgroundProcess | None':
        '''Starts wf_command like _run_subprocess() (cwd output_dir, output logged
        as "[snakemake] ...") but returns at once, so Stage 1 can run in the
        background. Returns None on launch failure.'''
        LOGGER.debug('Received command and running in background: %s', wf_command)

        output_dir = self.conf.get('output_dir', '')
        cwd = output_dir or None
        if cwd:
            Path(cwd).mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.Popen(
                wf_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=cwd, env=_subprocess_env(),
            )
        except Exception as e:
            LOGGER.error('Failed to launch background subprocess %s: %s', wf_command[0], e)
            return None

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        def _read_stdout():
            for line in proc.stdout:
                line = line.rstrip()
                if _chatter(line):
                    continue
                LOGGER.info('[snakemake] %s', line)
                stdout_lines.append(line)

        def _read_stderr():
            for line in proc.stderr:
                line = line.rstrip()
                if _chatter(line):
                    continue
                LOGGER.info('[snakemake] %s', line)
                stderr_lines.append(line)

        threading.Thread(target=_read_stdout, daemon=True).start()
        threading.Thread(target=_read_stderr, daemon=True).start()

        return _BackgroundProcess(proc, stdout_lines, stderr_lines)

    def _build_result(self, key_name, proc):
        '''Build a structured result dict from a completed snakemake process.'''
        rules_summary = self._parse_snakemake_output(proc.stderr)
        return {
            'workflow': key_name,
            'returncode': proc.returncode,
            'rules_summary': rules_summary,
            'stdout_tail': proc.stdout[-2000:] if proc.stdout else '',
            'stderr_tail': proc.stderr[-2000:] if proc.stderr else '',
        }

    def _output_prefix(self) -> str:
        """Return the filesystem prefix to prepend to all output paths for this run.

        Reads ``output_dir`` from the caragols config (set via CLI arg or passed
        from the API). If present, returns ``'{output_dir}/'``; otherwise returns
        ``''`` so that output paths remain relative to the SSH working directory.

        Every ``do_*`` workflow method should call this instead of reading
        ``output_dir`` directly, so the logic stays in one place.
        """
        output_dir = self.conf.get('output_dir', '')
        return f"{output_dir.rstrip('/')}/" if output_dir else ''

    def _run_pipeline(self, key_name: str, smk_config: dict, cache_map: dict = None, mode='slurm', compute_config: dict = None):
        '''Shared pipeline execution: cache containers, restore outputs, run snakemake, store outputs.'''
        run_id = str(uuid.uuid4())
        LOGGER.info('Starting workflow "%s" run_id=%s', key_name, run_id)

        selected_wf = WORKFLOWS.get(key_name)
        if not selected_wf:
            self.failed(f'No workflow key found for "{key_name}"')
            return 1

        # Download / ensure .sif files are cached (skip if none needed, e.g. selftest)
        if selected_wf.sif_files:
            if selected_wf.local_sif_only:
                # Never contacts the registry; reports what is already on disk.
                locate_local_sif_files(selected_wf.sif_files, local_sif_dir=self.conf.get('sif_path', None))
            else:
                try:
                    cache_sif_files(selected_wf.sif_files, local_sif_dir=self.conf.get('sif_path', None))
                except CacheSifError as e:
                    LOGGER.critical('Error with cache_sif_files: %s', e)
                    self.failed(f'Error with cache_sif_files: {e}')
                    return 1

        # Restore cached outputs from DB so snakemake skips completed rules
        db_path = smk_config.get('main_database')
        input_file = smk_config.get('input_fasta') or smk_config.get('input_file')
        restored = {}
        if cache_map and db_path and input_file:
            restored = restore_all(db_path, input_file, cache_map)
            LOGGER.info('Cache restore results: %s', restored)

        # Build and run snakemake
        wf_command = self.build_executable(selected_wf, config_overrides=smk_config, mode=mode, compute_config=compute_config)
        LOGGER.info('Running snakemake command: %s', ' '.join(wf_command))
        proc = self._run_subprocess(wf_command)

        # Launch failure (e.g. snakemake not installed) — already called self.failed()
        if proc is None:
            return 1

        result = self._build_result(key_name, proc)

        if proc.returncode != 0:
            LOGGER.error('Snakemake failed (rc=%d): %s', proc.returncode, result['rules_summary'])
            if cache_map and db_path and input_file:
                log_workflow_run(db_path, run_id, input_file, key_name,
                                 result['rules_summary'].get('completed', 0), status='failed')
            self.failed(msg=f'Workflow "{key_name}" failed', dex=result)
            return proc.returncode

        # Success — store outputs and log the run
        if cache_map and db_path and input_file:
            # Only store outputs that were cache misses (newly computed)
            tools_to_store = {tool: paths for tool, paths in cache_map.items()
                            if not restored.get(tool, False)}
            if tools_to_store:
                store_all(db_path, input_file, tools_to_store)
            else:
                LOGGER.info('All outputs were cache hits — skipping redundant storage')
            log_workflow_run(db_path, run_id, input_file, key_name,
                             result['rules_summary'].get('completed', 0), status='success')

        self.succeeded(msg=f'Workflow "{key_name}" completed successfully', dex=result)

    def _run_pipeline_batch(self, key_name: str, smk_config: dict, genome_files: dict[str, str],
                             cache_tool: str, cache_paths_fn, mode='slurm', compute_config: dict = None,
                             extra_resources: dict = None, sif_files_override: list[tuple] = None,
                             rerun_triggers: str = None):
        '''Batch sibling of _run_pipeline() for workflows that accept a folder of
        genomes: one snakemake subprocess over the {genome} wildcard, with the
        output cache checked and updated per genome.

        cache_paths_fn(stem) returns that genome's output files to cache.
        sif_files_override replaces selected_wf.sif_files for this call only.
        '''
        run_id = str(uuid.uuid4())
        LOGGER.info('Starting batch workflow "%s" run_id=%s genomes=%d', key_name, run_id, len(genome_files))

        selected_wf = WORKFLOWS.get(key_name)
        if not selected_wf:
            self.failed(f'No workflow key found for "{key_name}"')
            return 1

        sif_files = selected_wf.sif_files if sif_files_override is None else sif_files_override
        if sif_files:
            local_sif_dir = (self.conf.get(key_name, {}).get('sif_path', None)
                            or WORKFLOW_PATH_DEFAULTS.get(key_name, {}).get('sif_path'))
            if selected_wf.local_sif_only:
                locate_local_sif_files(sif_files, local_sif_dir=local_sif_dir)
            else:
                try:
                    cache_sif_files(sif_files, local_sif_dir=local_sif_dir)
                except CacheSifError as e:
                    LOGGER.critical('Error with cache_sif_files: %s', e)
                    self.failed(f'Error with cache_sif_files: {e}')
                    return 1

        db_path = smk_config.get('main_database')

        # Per-genome cache restore (SQLite check, before Snakemake runs)
        restored: dict[str, bool] = {}
        if db_path:
            for stem, genome_file in genome_files.items():
                cache_map = {cache_tool: cache_paths_fn(stem)}
                restored[stem] = restore_all(db_path, genome_file, cache_map).get(cache_tool, False)
            LOGGER.info('Cache restore results: %s', restored)

        # One snakemake subprocess for the whole batch.
        wf_command = self.build_executable(selected_wf, config_overrides=smk_config, mode=mode, compute_config=compute_config,
                                           extra_resources=extra_resources, rerun_triggers=rerun_triggers)
        LOGGER.info('Running snakemake command: %s', ' '.join(wf_command))
        proc = self._run_subprocess(wf_command)

        if proc is None:
            return 1

        result = self._build_result(key_name, proc)

        if proc.returncode != 0:
            LOGGER.error('Snakemake failed (rc=%d): %s', proc.returncode, result['rules_summary'])
            if db_path:
                for stem, genome_file in genome_files.items():
                    log_workflow_run(db_path, run_id, genome_file, key_name,
                                     result['rules_summary'].get('completed', 0), status='failed')
            self.failed(msg=f'Workflow "{key_name}" failed', dex=result)
            return proc.returncode

        # Success: stores outputs for cache misses and logs every genome's run.
        if db_path:
            for stem, genome_file in genome_files.items():
                if not restored.get(stem, False):
                    store_all(db_path, genome_file, {cache_tool: cache_paths_fn(stem)})
                log_workflow_run(db_path, run_id, genome_file, key_name,
                                 result['rules_summary'].get('completed', 0), status='success')

        self.succeeded(msg=f'Workflow "{key_name}" completed successfully ({len(genome_files)} genome(s))', dex=result)

    @staticmethod
    def _gtdbtk_split_paths(genome: str, smk_config: dict) -> list[str]:
        prefix = get_workflow_prefix_for(genome, smk_config)
        return [f"{prefix}gtdbtk/gtdbtk_results.tsv", f"{prefix}gtdbtk/translation_table.tsv",
                f"{prefix}gtdbtk/gtdbtk_db.tkn"]

    @staticmethod
    def _rasttk_paths(genome: str, smk_config: dict) -> list[str]:
        prefix = get_workflow_prefix_for(genome, smk_config)
        return [f"{prefix}rasttk/rast.tsv", f"{prefix}rasttk/rast.faa", f"{prefix}rasttk/rast.gff",
                f"{prefix}rasttk/rasttk_db.tkn"]

    def _margie_sb_dict(self) -> dict:
        '''The account's margie_sb settings as plain nested dicts, read from the config files
        themselves (later ones over earlier ones, as caragols loads them), as margie_sb.smk reads
        them. self.conf, a caragols Condex, splits keys at dots, so margie_sb.genome_info's file
        names (g1.fna) do not come through it whole: genome_calls found no domain or genetic code
        there and sent such genomes to Prodigal.'''
        def merge(into: dict, more: dict) -> None:
            for k, v in more.items():
                if isinstance(v, dict) and isinstance(into.get(k), dict):
                    merge(into[k], v)
                else:
                    into[k] = v
        paths = getattr(self, 'config_paths', None) or []
        if not paths:
            # No files to read (a config given as a plain dict): its own margie_sb.
            node = self.conf.get('margie_sb', {}) if self.conf else {}
            return node if isinstance(node, dict) else {}
        settings: dict = {}
        for path in paths:
            try:
                data = yaml.safe_load(Path(path).read_text()) or {}
            except Exception as exc:
                LOGGER.warning('Could not read %s for margie_sb settings: %s', path, exc)
                continue
            if isinstance(data, dict) and isinstance(data.get('margie_sb'), dict):
                merge(settings, data['margie_sb'])
        return settings

    def _quast_at_once(self, smk_config: dict) -> int:
        '''How many genomes QUAST checks at a time: margie_sb.quast.at_once from the run or the
        account's config (Settings), else QUAST_AT_ONCE; at least 1.'''
        value = smk_config.get('margie_sb.quast.at_once')
        if value in (None, ''):
            try:
                value = ((self.conf.get('margie_sb', {}) if self.conf else {}) or {}).get('quast', {}).get('at_once')
            except Exception:
                value = None
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return QUAST_AT_ONCE

    def _stage2_at_once(self, smk_config: dict) -> int:
        '''How many genomes go through Stage 2 at a time: margie_sb.stage2.at_once from the run or the
        account's config (Settings), else STAGE2_AT_ONCE; at least 1.'''
        value = smk_config.get('margie_sb.stage2.at_once')
        if value in (None, ''):
            try:
                value = ((self.conf.get('margie_sb', {}) if self.conf else {}) or {}).get('stage2', {}).get('at_once')
            except Exception:
                value = None
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return STAGE2_AT_ONCE

    def _restore_gene_calls(self, db_path: str, genome_files: dict[str, str], smk_config: dict,
                            prodigal_genomes: set[str]) -> tuple[dict[str, bool], dict[str, bool]]:
        '''Takes each genome's GTDB-Tk and RASTtk outputs from the MARGIE database, genome by genome.

        GTDB-Tk for every genome cached; RASTtk where GTDB-Tk came back too, so its domain and
        genetic code are the ones the cached gene calls were made with, and the config names
        neither. GTDB-Tk's database token comes back when it was stored with the results, and
        load_gtdbtk_to_db makes it otherwise; results that name only the domain (an older
        format, without the classification) are run again. Each restore also writes the step's
        compute token, so margie_sb.smk's gtdbtk_from_cache and rasttk_from_cache rules (told
        about these genomes through cached_gtdbtk and cached_rasttk) have nothing to do, and only
        the other genomes go into the GTDB-Tk batch. Returns ({genome: gtdbtk restored},
        {genome: rasttk restored}).
        '''
        # As do_margie_sb: a domain or genetic code the config names is the config's.
        calls = genome_calls(genome_files, {'run_gtdbtk': True, 'margie_sb': self._margie_sb_dict()})
        gtdbtk, rasttk = {}, {}
        for genome, fasta_path in genome_files.items():
            prefix = get_workflow_prefix_for(genome, smk_config)
            results, table, token = WorkflowBase._gtdbtk_split_paths(genome, smk_config)
            gtdbtk[genome] = restore(db_path, fasta_path, 'gtdbtk', [results, table], optional=[token])
            if gtdbtk[genome] and not WorkflowBase._names_classification(results):
                LOGGER.info("Cached GTDB-Tk results for %s name only the domain -- GTDB-Tk runs again", genome)
                for path in (results, table, token):
                    Path(path).unlink(missing_ok=True)
                gtdbtk[genome] = False
            if not gtdbtk[genome]:
                continue
            WorkflowBase._mark_restored([results, table, token, f"{prefix}gtdbtk/gtdbtk_compute.tkn"])
            LOGGER.info("Cache HIT for gtdbtk (genome=%s) — skipping recomputation", genome)
            if genome in prodigal_genomes or calls.get(genome, {}).get('source') == 'metadata':
                continue  # Prodigal's genes, or a domain/code from the config: RASTtk runs fresh
            rasttk[genome] = restore(db_path, fasta_path, 'rasttk', WorkflowBase._rasttk_paths(genome, smk_config))
            if rasttk[genome]:
                WorkflowBase._mark_restored([*WorkflowBase._rasttk_paths(genome, smk_config),
                                             f"{prefix}rasttk/rasttk_compute.tkn"])
                LOGGER.info("Cache HIT for rasttk (genome=%s) — skipping recomputation", genome)
        return gtdbtk, rasttk

    @staticmethod
    def _names_classification(results: str) -> bool:
        '''Whether a gtdbtk_results.tsv has the GTDBTK_classification column.'''
        try:
            with open(results) as fh:
                return 'GTDBTK_classification' in fh.readline().rstrip('\n').split('\t')
        except OSError:
            return False

    @staticmethod
    def _mark_restored(paths: list[str]) -> None:
        '''Writes the compute tokens among *paths* and gives every file one common time, so no
        restored input is newer than a restored output.'''
        stamp = time.time()
        for path in paths:
            if path.endswith('_compute.tkn'):
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text('restored from the MARGIE database\n')
            try:
                os.utime(path, (stamp, stamp))
            except OSError:
                pass

    def _genome_stage2_progress(self, genome: str, genome_file: str, smk_config: dict) -> tuple[int, int]:
        '''Returns (max_phase_reached, n_phases_done) for a genome, used to run the
        most complete genomes first in Stage 2.

        A phase counts as done if its output cache row exists or its output
        folder is populated. Never raises; an unreadable genome scores (0, 0).'''
        done: set = set()
        # (1) phases already in the output cache (completed in a prior run)
        db_path = smk_config.get('main_database')
        if db_path:
            done |= cached_tools(db_path, genome_file)
        # (2) phases already materialised on disk this run
        try:
            prefix = Path(get_workflow_prefix_for(genome, smk_config))
            for tool in MARGIE_SB_PHASED_TOOLS:
                key = tool.get('key')
                if not key or key in done:
                    continue
                d = prefix / key
                try:
                    if d.is_dir() and any(d.iterdir()):
                        done.add(key)
                except OSError:
                    continue
        except Exception:
            pass
        phase_of = {t.get('key'): t.get('phase', 0) for t in MARGIE_SB_PHASED_TOOLS}
        max_phase = max((phase_of.get(t, 0) for t in done), default=0)
        return (max_phase, len(done))

    def _run_pipeline_batch_sequential(self, key_name: str, smk_config: dict, genome_files: dict[str, str],
                                        cache_map_fn, mode='slurm', compute_config: dict = None,
                                        extra_resources: dict = None, sif_files_override: list[tuple] = None,
                                        rerun_triggers: str = None, prodigal_genomes: set[str] = frozenset()):
        '''Sequential-per-organism sibling of _run_pipeline_batch() for margie_sb.

        Stage 1 (rule rasttk_all) runs GTDB-Tk/RASTtk breadth-first in the
        background with --jobs=1, since BV-BRC takes one submission at a time.
        Stage 2 (rule phase4_12_one_genome) runs phases 4-11 for one genome at a
        time, in RASTtk-ready order, choosing the most complete ready genome
        first (see _genome_stage2_progress). A Stage 2 failure halts the queue.
        '''
        run_id = str(uuid.uuid4())
        LOGGER.info('Starting sequential batch workflow "%s" run_id=%s genomes=%d', key_name, run_id, len(genome_files))

        selected_wf = WORKFLOWS.get(key_name)
        if not selected_wf:
            self.failed(f'No workflow key found for "{key_name}"')
            return 1

        sif_files = selected_wf.sif_files if sif_files_override is None else sif_files_override
        if sif_files:
            local_sif_dir = (self.conf.get(key_name, {}).get('sif_path', None)
                            or WORKFLOW_PATH_DEFAULTS.get(key_name, {}).get('sif_path'))
            if selected_wf.local_sif_only:
                locate_local_sif_files(sif_files, local_sif_dir=local_sif_dir)
            else:
                try:
                    cache_sif_files(sif_files, local_sif_dir=local_sif_dir)
                except CacheSifError as e:
                    LOGGER.critical('Error with cache_sif_files: %s', e)
                    self.failed(f'Error with cache_sif_files: {e}')
                    return 1

        db_path = smk_config.get('main_database')
        # A name another genome (other DNA) has in the database would mix the two in its tables, and a
        # reload would replace the other genome's rows: the run stops before anything is loaded.
        if db_path:
            clashes = _safely('Checking the genome names against the database', name_clashes, db_path, genome_files)
            if isinstance(clashes, list) and clashes:
                msg = ('Your MARGIE database already has a different genome (other DNA) under '
                       + ('this name' if len(clashes) == 1 else 'these names') + ': ' + ', '.join(clashes)
                       + '. Rename the file (for example coli_strainB.fna) and start the run again.')
                LOGGER.error(msg)
                self.failed(msg)
                return 1
        # Off: nothing reads GTDB-Tk, so its batch is neither restored nor run.
        run_gtdbtk_enabled = smk_config.get('run_gtdbtk', True) not in (False, 'false', '0', 'no')
        # QUAST runs beside Stage 1 and 2 when picked (run_quast, off by default).
        run_quast_enabled = smk_config.get('run_quast', False) not in (False, 'false', '0', 'no', None)

        restored: dict[str, dict[str, bool]] = {}
        gtdbtk_restored: dict[str, bool] = {}
        rasttk_restored: dict[str, bool] = {}
        # Genomes whose GTDB-Tk outputs are cached as soon as they exist, and those cached
        # with their database token too.
        gtdbtk_stored: set[str] = set()
        gtdbtk_loaded: set[str] = set()
        if db_path:
            # Deferred so restored files are newer than Stage 1's rast.faa.
            LOGGER.info('Phase4+ cache restore deferred to per-genome pre-Stage-2 (after rasttk outputs are fresh)')
            # gtdbtk/rasttk are not in cache_map_fn: genome by genome here, before Stage 1.
            if run_gtdbtk_enabled:
                gtdbtk_restored, rasttk_restored = self._restore_gene_calls(db_path, genome_files, smk_config, prodigal_genomes)
                gtdbtk_stored |= {g for g, hit in gtdbtk_restored.items() if hit}
                gtdbtk_loaded |= {g for g in gtdbtk_stored if Path(self._gtdbtk_split_paths(g, smk_config)[2]).exists()}
            # A genome bound for Prodigal takes RASTtk's gene calls when its sequence has them in the
            # database, and with them its RASTtk-based results: Prodigal annotates novel genomes only.
            for g in sorted(prodigal_genomes):
                paths = self._rasttk_paths(g, smk_config)
                if _safely(f'Restoring the RASTtk gene calls of {g}', restore, db_path, genome_files[g], 'rasttk', paths) is True:
                    self._mark_restored([*paths, f"{get_workflow_prefix_for(g, smk_config)}rasttk/rasttk_compute.tkn"])
                    rasttk_restored[g] = True
                    LOGGER.info('RASTtk gene calls for %s came from the MARGIE database: they stand in for Prodigal', g)
            prodigal_genomes = frozenset(g for g in prodigal_genomes if not rasttk_restored.get(g))
            LOGGER.info('From the MARGIE database: GTDB-Tk for %d of %d genome(s), RASTtk for %d',
                        sum(gtdbtk_restored.values()), len(genome_files), sum(rasttk_restored.values()))
        # margie_sb.smk takes these genomes' GTDB-Tk and RASTtk outputs as they are (rules
        # gtdbtk_from_cache, rasttk_from_cache), and leaves them out of the GTDB-Tk batch.
        smk_config['cached_gtdbtk'] = ','.join(sorted(g for g, hit in gtdbtk_restored.items() if hit))
        smk_config['cached_rasttk'] = ','.join(sorted(g for g, hit in rasttk_restored.items() if hit))

        # Genome-level results are RASTtk-based: a Prodigal genome neither restores nor stores them.
        if cache_map_fn is not None:
            genome_cache_map = cache_map_fn
            cache_map_fn = lambda genome: {} if genome in prodigal_genomes else genome_cache_map(genome)

        def _gene_calls(genome: str) -> dict[str, str]:
            '''The genome's gene-call files: Prodigal's for a Prodigal genome, else RASTtk's.'''
            return gene_call_files(get_workflow_prefix_for(genome, smk_config),
                                   'prodigal' if genome in prodigal_genomes else 'rasttk')

        # Where each step's results come from (cache_report.py), written as the run goes.
        provenance = cache_report.CacheReport(smk_config.get('output_dir') or '', db_path or '')
        when = {g: cached_when(db_path, f) for g, f in genome_files.items()} if db_path else {}
        # A genome-level hit: the same genome sequence was run before, and its whole output comes back.
        SAME_GENOME = 'whole output from a run on the same genome sequence'
        for g in genome_files:
            prefix = get_workflow_prefix_for(g, smk_config)
            on_disk = lambda paths: all(Path(p).exists() for p in paths)
            if not run_gtdbtk_enabled:
                provenance.set(g, 'gtdbtk', cache_report.NOT_RUN, 'switched off')
            elif gtdbtk_restored.get(g):
                provenance.set(g, 'gtdbtk', cache_report.RESTORED, SAME_GENOME, when.get(g, {}).get('gtdbtk', ''), cache_report.GENOME_LEVEL)
            elif on_disk(self._gtdbtk_split_paths(g, smk_config)):
                provenance.set(g, 'gtdbtk', cache_report.KEPT, "already in this run's folder (an earlier attempt)")
            else:
                provenance.set(g, 'gtdbtk', cache_report.FRESH, 'run with this batch' if db_path else 'no MARGIE database set')
            if run_quast_enabled:
                provenance.set(g, 'quast', cache_report.FRESH, "measured fresh on this run's assembly")
            if g in prodigal_genomes:
                provenance.set(g, 'prodigal', cache_report.FRESH,
                               'genes called fresh by Prodigal: no RASTtk gene calls for this genome in the MARGIE database'
                               if db_path else 'genes called fresh by Prodigal')
            elif rasttk_restored.get(g):
                provenance.set(g, 'rasttk', cache_report.RESTORED, SAME_GENOME, when.get(g, {}).get('rasttk', ''), cache_report.GENOME_LEVEL)
            elif Path(f"{prefix}rasttk/rasttk_db.tkn").exists():
                provenance.set(g, 'rasttk', cache_report.KEPT, "already in this run's folder (an earlier attempt)")
            else:
                provenance.set(g, 'rasttk', cache_report.FRESH, '' if db_path else 'no MARGIE database set')
        provenance.write()

        # Stage 1: phases 1-3 in waves with --jobs=1, one BV-BRC submission at a time.
        def _stage1_targets(genome: str) -> list[str]:
            '''Returns Stage 1's files for one genome: its genome_info.tsv and its gene calls' DB
            token, plus GTDB-Tk's when it is selected. QUAST is not here: it runs on its own.'''
            prefix = get_workflow_prefix_for(genome, smk_config)
            # genome_info.tsv too: for a genome whose gene calls came from the database it is
            # not made on the way to RASTtk, and Stage 2's restored tool outputs must be newer.
            targets = [f"{prefix}genome_info/genome_info.tsv", _gene_calls(genome)['loaded']]
            if run_gtdbtk_enabled:
                targets.append(f"{prefix}gtdbtk/gtdbtk_db.tkn")
            return targets

        # "Ready": per-genome GTDB-Tk outputs on disk, or always when GTDB-Tk is off.
        gtdbtk_ready = [g for g in genome_files
                        if not run_gtdbtk_enabled
                        or all(Path(p).exists() for p in self._gtdbtk_split_paths(g, smk_config))]
        gtdbtk_pending = [g for g in genome_files if g not in set(gtdbtk_ready)]
        LOGGER.info('Stage 1 waves: %d genome(s) have GTDB-Tk outputs already, %d still need the batch',
                    len(gtdbtk_ready), len(gtdbtk_pending))

        output_dir_for_batch = (smk_config.get('output_dir') or '').rstrip('/')
        batch_targets = ([f"{output_dir_for_batch}/original_container_outputs/gtdbtk/gtdbtk_batch.done"]
                         if gtdbtk_pending and output_dir_for_batch else [])

        # Stage 1 runs at the account's job limit; RASTtk alone goes one at a time (the
        # margie_sb_bvbrc slot, and the rule's own lock across runs), so BV-BRC sees one submission.
        def _launch_wave(targets: list[str], label: str):
            command = self.build_executable(selected_wf, config_overrides=smk_config, mode=mode,
                                            compute_config=compute_config, extra_resources=extra_resources,
                                            rerun_triggers=rerun_triggers, target=targets)
            LOGGER.info('Starting Stage 1 wave [%s] over %d target(s): %s',
                        label, len(targets), ' '.join(command))
            proc = self._start_background_subprocess(command)
            if proc is None:
                LOGGER.error('Stage 1 wave [%s] failed to launch', label)
            return proc

        stage1 = _Stage1Waves(
            _launch_wave,
            batch_targets,
            [t for g in gtdbtk_ready for t in _stage1_targets(g)],
            [t for g in gtdbtk_pending for t in _stage1_targets(g)],
        )

        # QUAST reads only the genomes and no step reads its results: its own Snakemake, beside
        # Stage 1 and 2, three genomes at a time (two cores each, rule run_quast). The run waits
        # for it at the end; a QUAST failure leaves the annotations as they are.
        quast_proc = None
        if run_quast_enabled and genome_files:
            quast_targets = [f"{get_workflow_prefix_for(g, smk_config)}quast/quast_db.tkn" for g in genome_files]
            at_once = self._quast_at_once(smk_config)
            quast_command = self.build_executable(selected_wf, config_overrides=smk_config, mode=mode,
                                                  compute_config=compute_config, extra_resources=extra_resources,
                                                  rerun_triggers=rerun_triggers, target=quast_targets,
                                                  max_jobs_override=at_once)
            LOGGER.info('Starting QUAST on its own over %d genome(s), %d at a time: %s',
                        len(quast_targets), at_once, ' '.join(quast_command))
            quast_proc = self._start_background_subprocess(quast_command)
            if quast_proc is None:
                LOGGER.warning('QUAST could not be started; the annotation goes on without it')

        # With LLM on, Stage 2 stops before the GPU step; Stage 3 runs the LLM jobs.
        _run_llm_val = smk_config.get('run_llm', False)
        run_llm_enabled = _run_llm_val not in (False, 'false', '0', 'no')
        stage2_target = 'phase4_12_one_genome_no_llm' if run_llm_enabled else 'phase4_12_one_genome'
        LOGGER.info('LLM enabled: %s  →  Stage 2 target: %s', run_llm_enabled, stage2_target)

        # Per-protein cache config: the account's config plus this run's settings.
        pc_cfg = {**(self.conf or {}), **smk_config}
        pc_on = bool(db_path) and key_name == 'margie_sb' and protein_cache.enabled(pc_cfg)

        total = len(genome_files)
        pending = set(genome_files.keys())
        queue: list[str] = []
        skipped: list[str] = []
        # Genomes whose Stage 2 failed; the queue goes on with the others.
        failed: list[str] = []
        finished: list[str] = []
        processed = 0
        last_proc = None
        progress_memo: dict[str, tuple[int, int]] = {}  # genome -> completeness, for most-complete-first ordering

        # Run again (the Jobs page): while Stage 2 goes, the API asks for a failed genome with
        # <output_dir>/.margie-requests/<genome>.again; the genome goes back in the queue and its
        # Stage 2 runs again from the failed step, keeping its finished steps. The answer is written
        # beside it (<genome>.taken or <genome>.declined), and `open` says the run takes requests.
        run_root = (smk_config.get('output_dir') or self.conf.get('output_dir', '') or '').rstrip('/')
        requests_dir = Path(run_root) / '.margie-requests' if run_root else None
        asked_again: set[str] = set()

        def _requests_open(on: bool) -> None:
            if requests_dir is None:
                return
            try:
                if on:
                    requests_dir.mkdir(parents=True, exist_ok=True)
                    (requests_dir / 'open').write_text(f"{os.environ.get('SLURM_JOB_ID', '')}\n")
                else:
                    (requests_dir / 'open').unlink(missing_ok=True)
            except OSError as exc:
                LOGGER.warning('Run again requests: %s could not be %s: %s', requests_dir, 'opened' if on else 'closed', exc)

        def _answer(genome: str, taken: bool, note: str) -> None:
            try:
                (requests_dir / f"{genome}.{'taken' if taken else 'declined'}").write_text(note + '\n')
            except OSError as exc:
                LOGGER.warning('Run again requests: no answer written for %s: %s', genome, exc)

        def _asks() -> list[str]:
            """The genomes asked for again since the last look; each request is read once."""
            if requests_dir is None:
                return []
            try:
                asks = sorted(requests_dir.glob('*.again'))
            except OSError:
                return []
            names = []
            for ask in asks:
                try:
                    ask.unlink()
                except OSError:
                    continue
                names.append(ask.name[:-len('.again')])
            return names

        _requests_open(True)

        # Stage 2 takes up to `at_once` genomes at a time (margie_sb.stage2.at_once): a genome starts
        # once its gene calls are in and a place is free, and its own steps run as before. Their
        # database loads take turns through SQLite's lock (the load rules wait and retry), and the
        # shared operon and fingerprint references are written under their own file locks.
        at_once = self._stage2_at_once(smk_config)
        active: list[dict] = []
        last = {'proc': None}

        def _start(genome: str) -> dict | None:
            """Prepares one genome (cache restore, protein cache, report rows) and starts its Stage 2;
            None when its selected steps all came back from the cache."""
            genome_restored: dict = {}
            merged_fp = ''
            # The genome's sequence hash: its proteins and genes are linked to it in the database.
            hashed = _safely(f'Hashing {genome}', fasta_hashes, genome_files[genome]) if db_path else None
            genome_hash = hashed[0] if isinstance(hashed, list) and hashed else ''
            # This genome's genes by hash (RASTtk gene calls): cached tables are stored and come back
            # by them, whatever numbers a submission gives the genes.
            genes: dict = {}
            if genome not in prodigal_genomes:
                hashed = _safely(f'Hashing the genes of {genome}', gene_hashes,
                                 _gene_calls(genome)['gff'], _gene_calls(genome)['faa'])
                genes = hashed if isinstance(hashed, dict) else {}
            # Restored after rast.faa so mtimes are newer; must precede the skip below. A Prodigal
            # genome restores nothing: the MARGIE database keeps RASTtk-based results.
            if db_path and genome not in prodigal_genomes:
                genome_cache_map_now = cache_map_fn(genome)
                tools_map = {k: v for k, v in genome_cache_map_now.items() if not input_keyed(k)}
                genome_restored = _safely(f'Restoring {genome} from the cache', restore_all,
                                          db_path, genome_files[genome], tools_map, genes=genes) or {}
                if genome_restored is _FAILED:
                    genome_restored = {}
                # Gene-call guard: cached tables name genes by number under the RASTtk id they were
                # made with. A table under another id moves onto this run's id only when the cached
                # gene calls under that id hold the same protein under each number as this run's;
                # otherwise it is dropped and its tool runs (the protein cache still serves the
                # proteins it holds).
                prefix = get_workflow_prefix_for(genome, smk_config)
                current_id = current_rast_genome_id(f"{prefix}rasttk/rast.gff")
                if current_id and genome_restored:
                    verdict: dict = {}
                    dropped: list[str] = []
                    for tool, hit in list(genome_restored.items()):
                        made_with = rast_genome_ids(tools_map.get(tool, [])) - {current_id} if hit else set()
                        if not made_with:
                            continue
                        old = next(iter(made_with))
                        if len(made_with) == 1 and old not in verdict:
                            verdict[old] = _safely(f'Comparing the gene calls of {genome} with those under {old}', gene_calls_match,
                                                   db_path, genome_files[genome], f"{prefix}rasttk/rast.faa", old)
                        if len(made_with) == 1 and verdict[old] is True:
                            continue
                        for path in tools_map.get(tool, []):
                            Path(path).unlink(missing_ok=True)
                        genome_restored[tool] = False
                        dropped.append(tool)
                    if dropped:
                        LOGGER.warning('The gene calls of %s differ from those its cached %s were made with (RASTtk %s); '
                                       'those tools run on this run\'s genes', genome, ', '.join(dropped), ', '.join(sorted(verdict)))
                # Consolidation and labeling: only a merge of exactly the tables now in the folder.
                merged_fp = merged_inputs_fingerprint(get_workflow_prefix_for(genome, smk_config))
                merged_back = _safely(f'Restoring {genome} merged tables from the cache', restore_all,
                                      db_path, genome_files[genome],
                                      {cache_name(k, merged_fp): v for k, v in genome_cache_map_now.items() if input_keyed(k)},
                                      genes=genes)
                genome_restored.update(merged_back if isinstance(merged_back, dict) else {})
                # Back under the cache-map keys, for the checks and the report below.
                genome_restored = {k: genome_restored.get(cache_name(k, merged_fp), False) for k in genome_cache_map_now}
                restored[genome] = genome_restored
                LOGGER.info('Phase4+ cache restore for %s: %s (merged tables %s)', genome, genome_restored, merged_fp)

                # Rewrites restored tables into this run's RASTtk id namespace.
                rast_ref = f"{get_workflow_prefix_for(genome, smk_config)}rasttk/rast.gff"
                current_id = current_rast_genome_id(rast_ref)
                if current_id:
                    hit_paths = [p for tool, hit in genome_restored.items() if hit
                                 for p in genome_cache_map_now.get(tool, [])]
                    realigned = realign_rast_genome_id(hit_paths, current_id)
                    if realigned:
                        LOGGER.warning(
                            'Realigned %d cache-restored file(s) for %s onto RASTtk genome id %s '
                            '(cached under a different submission): %s',
                            len(realigned), genome, current_id, sorted(realigned.values())[:1])
                else:
                    LOGGER.warning('No single RASTtk genome id readable from %s — skipping '
                                   'cache realignment for %s', rast_ref, genome)

            # Per-protein cache: only proteins not in the cache go to each tool.
            pc_prefix = get_workflow_prefix_for(genome, smk_config)
            pc_faa_path = _gene_calls(genome)['faa']
            # Which genome each protein and gene belongs to, by hash (RASTtk's genes only).
            if db_path and genome not in prodigal_genomes and Path(pc_faa_path).exists():
                _safely(f'Linking the proteins and genes of {genome} to its genome hash', protein_cache.link_genome,
                        db_path, pc_faa_path, genome_hash, genome, genes)
            pc_tools: list[str] = []
            pc_stored: set[str] = set()
            # {tool: (proteins from the protein cache, proteins to annotate)} for this genome's report.
            pc_counts: dict[str, tuple[int, int]] = {}
            # {tool: {genome its cached proteins came from: proteins}}.
            pc_sources: dict[str, dict[str, int]] = {}
            if pc_on and Path(pc_faa_path).exists():
                pc_tools = [t for t in protein_cache.TOOLS
                            if smk_config.get(f'run_{t}', True) not in (False, 'false', '0', 'no')]
                to_split = [t for t in pc_tools if not genome_restored.get(t, False)]
                for t in pc_tools:
                    if t not in to_split:
                        protein_cache.clear(pc_prefix, t)
                try:
                    counts = protein_cache.split(db_path, pc_faa_path, pc_prefix, genome, to_split, pc_cfg, sources=pc_sources)
                    pc_counts = counts
                    served = {t: c for t, c in counts.items() if c[0]}
                    LOGGER.info('Protein cache for %s: %s', genome,
                                ', '.join(f'{t} {c}/{c + n} cached' for t, (c, n) in counts.items()) or 'no tool to split')
                    for t, src in pc_sources.items():
                        if src:
                            LOGGER.info('Protein cache sources for %s, %s: matched from %s', genome, t, cache_report.matched(src))
                    if served:
                        LOGGER.info('Protein cache: %d tool(s) run on fewer proteins for %s', len(served), genome)
                except Exception as exc:
                    LOGGER.warning('Protein cache split failed for %s (tools run on every protein): %s', genome, exc)
                    for t in to_split:
                        protein_cache.clear(pc_prefix, t)

            # The genome's steps after gene calling in the cache report: restored (genome or protein
            # level), partly restored, kept from an earlier attempt, or fresh.
            off = lambda step: smk_config.get(f'run_{step}', True) in (False, 'false', '0', 'no')
            if genome in prodigal_genomes:
                # Prodigal's genes: no genome-level results come back, and the protein cache serves the
                # proteins it holds (a protein's results are the same whichever tool called its gene).
                for t in MARGIE_SB_PHASED_TOOLS:
                    key = t.get('key')
                    if not key or not 4 <= t.get('phase', 0) <= 10 or off(key):
                        continue
                    if key in pc_counts:
                        provenance.set(genome, key, **cache_report.proteins(*pc_counts[key], sources=pc_sources.get(key)))
                    else:
                        provenance.set(genome, key, cache_report.FRESH, 'run fresh on Prodigal genes')
            for key, paths in cache_map_fn(genome).items():
                step = key.split('@')[0]
                if db_path and genome_restored.get(key):
                    detail = (f'{SAME_GENOME}, merging the same tool tables' if input_keyed(key) else SAME_GENOME)
                    provenance.set(genome, step, cache_report.RESTORED, detail,
                                   when.get(genome, {}).get(cache_name(key, merged_fp), ''), cache_report.GENOME_LEVEL)
                elif off(step):
                    provenance.set(genome, step, cache_report.NOT_RUN, 'not chosen for this run')
                elif all(Path(p).exists() for p in paths):
                    provenance.set(genome, step, cache_report.KEPT, "already in this run's folder (an earlier attempt)")
                elif step in pc_counts:
                    provenance.set(genome, step, **cache_report.proteins(*pc_counts[step], sources=pc_sources.get(step)))
                else:
                    provenance.set(genome, step, cache_report.FRESH, '' if db_path else 'no MARGIE database set')
            if smk_config.get('run_scoring', True) not in (False, 'false', '0', 'no'):
                provenance.set(genome, 'scoring', cache_report.FRESH, 'run fresh: the operon reference grows with each genome')
            provenance.write()

            # Skips Stage 2 only at PIPELINE_VERSION with every selected step restored.
            if db_path:
                fasta_hash = fasta_hashes(genome_files[genome])
                missing_selected = [
                    t for t, hit in genome_restored.items()
                    if not hit and smk_config.get(f"run_{t.split('@')[0]}", True) not in (False, 'false', '0', 'no')
                ]
                # Scoring is never cached (its OCC reference grows), so no fast path.
                scoring_always_recomputes = smk_config.get('run_scoring', True) not in (False, 'false', '0', 'no')
                # Unknown (a busy database) counts as not processed: the genome is computed.
                already = _safely(f'Checking {genome} in the database', is_already_processed,
                                  db_path, fasta_hash, PIPELINE_VERSION) is True
                # A Prodigal genome restores nothing, so it always computes.
                if (genome not in prodigal_genomes and already
                        and not missing_selected and not scoring_always_recomputes):
                    LOGGER.info('Genome %s already at pipeline version %s — skipping Stage 2 compute (all selected outputs restored from cache)',
                                genome, PIPELINE_VERSION)
                    LOGGER.info(provenance.summary(genome))
                    _safely(f'Recording {genome} in the run log table', log_workflow_run, db_path, run_id,
                            genome_files[genome], key_name, 0, status='success')
                    return None
                if missing_selected:
                    LOGGER.info('Genome %s at version %s but selected steps not in cache: %s — running Stage 2 to compute them',
                                genome, PIPELINE_VERSION, missing_selected)
                elif scoring_always_recomputes and already:
                    LOGGER.info('Genome %s already at version %s, and scoring runs fresh — running Stage 2 to RE-SCORE (only scoring + fingerprint recompute; all other phases restore from cache)',
                                genome, PIPELINE_VERSION)

            stage2_config = {**smk_config, 'target_genome': genome}
            stage2_command = self.build_executable(selected_wf, config_overrides=stage2_config, mode=mode,
                                                    compute_config=compute_config, extra_resources=extra_resources,
                                                    rerun_triggers=rerun_triggers, target=stage2_target)
            if genome in asked_again:
                # Run again: a step stopped part way starts afresh.
                stage2_command.append('--rerun-incomplete')
            LOGGER.info('Starting Stage 2 (%s) for %s: %s', stage2_target, genome, ' '.join(stage2_command))
            stage2_proc = self._start_background_subprocess(stage2_command)

            return {'genome': genome, 'proc': stage2_proc, 'command': stage2_command, 'pc_prefix': pc_prefix,
                    'pc_faa_path': pc_faa_path, 'pc_tools': pc_tools, 'pc_stored': pc_stored,
                    'cache_map': cache_map_fn(genome), 'restored': restored.get(genome, {}), 'stored': set(),
                    'genes': genes, 'genome_hash': genome_hash}

        def _store_ready(slot: dict) -> None:
            """Stores each of a genome's tools once its outputs and db token (written last) exist."""
            if not db_path:
                return
            genome, pc_prefix = slot['genome'], slot['pc_prefix']
            # Each tool's proteins, once its results are loaded (its db token); a Prodigal genome's
            # proteins are not kept, as the MARGIE database keeps RASTtk-based results.
            for t in ([] if genome in prodigal_genomes else slot['pc_tools']):
                if t in slot['pc_stored'] or not Path(f"{pc_prefix}{t}/{t}_db.tkn").exists():
                    continue
                slot['pc_stored'].add(t)
                try:
                    added = protein_cache.store(db_path, slot['pc_faa_path'], pc_prefix, t, pc_cfg, genome=genome)
                    if added:
                        LOGGER.info('Protein cache: %d new protein(s) of %s kept for %s', added, genome, t)
                except Exception as exc:
                    LOGGER.warning('Protein cache store failed for %s / %s: %s', genome, t, exc)
            for tool, paths in slot['cache_map'].items():
                if tool in slot['stored'] or slot['restored'].get(tool, False):
                    continue
                if all(Path(p).exists() for p in paths):
                    # Consolidation is done, so every table it merged is final.
                    name = cache_name(tool, merged_inputs_fingerprint(pc_prefix)) if input_keyed(tool) else tool
                    if _safely(f'Caching {tool} for {genome}', store, db_path, genome_files[genome], name, paths,
                               genes=slot['genes']) is _FAILED:
                        # Asked again at the next look; after five tries the step stays uncached this time.
                        slot.setdefault('tries', {})[tool] = slot.get('tries', {}).get(tool, 0) + 1
                        if slot['tries'][tool] >= 5:
                            slot['stored'].add(tool)
                        continue
                    slot['stored'].add(tool)
                    LOGGER.info('Cached %s for %s as soon as its own db token appeared '
                                '(Stage 2 still running)', tool, genome)

        def _finish(slot: dict) -> None:
            """Wraps up a genome whose Stage 2 has ended: its last tools stored, its record and report."""
            genome = slot['genome']
            _store_ready(slot)  # tokens written right before exit
            p = slot['proc']
            proc = None if p is None else subprocess.CompletedProcess(
                args=slot['command'], returncode=p.proc.returncode,
                stdout='\n'.join(p.stdout_lines), stderr='\n'.join(p.stderr_lines))
            last['proc'] = proc
            if proc is None or proc.returncode != 0:
                rc = proc.returncode if proc else None
                LOGGER.error('Stage 2 (phase4-10) failed for genome "%s" (rc=%s); going on with the others.',
                             genome, rc)
                result = (self._build_result(key_name, proc) if proc else
                          {'workflow': key_name, 'returncode': rc, 'rules_summary': {}, 'stdout_tail': '', 'stderr_tail': ''})
                provenance.unfinished(genome)
                provenance.write()
                LOGGER.info(provenance.summary(genome))
                if db_path:
                    _safely(f'Recording {genome} in the run log table', log_workflow_run, db_path, run_id,
                            genome_files[genome], key_name, result['rules_summary'].get('completed', 0), status='failed')
                failed.append(genome)
                return
            finished.append(genome)
            prodigal = genome in prodigal_genomes
            if db_path:
                tools_to_store = {tool: paths for tool, paths in slot['cache_map'].items()
                                  if tool not in slot['stored'] and not slot['restored'].get(tool, False)}
                if prodigal:
                    LOGGER.info('%s: Prodigal genes, so its results stay out of the MARGIE caches', genome)
                elif tools_to_store:
                    merged_fp = merged_inputs_fingerprint(slot['pc_prefix'])
                    _safely(f'Caching the rest of {genome}', store_all, db_path, genome_files[genome],
                            {cache_name(t, merged_fp): p for t, p in tools_to_store.items()}, genes=slot['genes'])
                else:
                    LOGGER.info('All outputs were already cached incrementally or were cache hits for %s', genome)
                _safely(f'Recording {genome} in the run log table', log_workflow_run, db_path, run_id, genome_files[genome],
                        key_name, self._build_result(key_name, proc)['rules_summary'].get('completed', 0), status='success')
                if not prodigal:
                    # Each gene's fingerprint, beside its gene hash.
                    _safely(f'Recording the fingerprints of {genome}', protein_cache.record_fingerprints, db_path, slot['genome_hash'],
                            f"{slot['pc_prefix']}fingerprint/labeled-genes-fingerprint-hash-label.tsv", slot['genes'])
                    # Each protein's record: its descriptors tool by tool, and its core and additional fingerprints.
                    _safely(f'Recording the proteins of {genome}', protein_cache.record_proteins, db_path,
                            f"{slot['pc_prefix']}labeling/labeled-genes.tsv", slot['pc_prefix'], slot['genome_hash'])
            LOGGER.info(provenance.summary(genome))

        while pending or queue or active:
            # Caches GTDB-Tk outputs once the split has written them (its compute token comes
            # last), so a run that stops before a genome's Stage 1 wave keeps them, and again
            # once they are loaded, with the database token.
            if db_path and run_gtdbtk_enabled:
                for genome in genome_files:
                    if genome in gtdbtk_loaded:
                        continue
                    paths = self._gtdbtk_split_paths(genome, smk_config)
                    split = [*paths[:2], f"{get_workflow_prefix_for(genome, smk_config)}gtdbtk/gtdbtk_compute.tkn"]
                    if Path(paths[2]).exists() or (genome not in gtdbtk_stored and all(Path(p).exists() for p in split)):
                        _safely(f'Caching GTDB-Tk for {genome}', store, db_path, genome_files[genome], 'gtdbtk', paths)
                        gtdbtk_stored.add(genome)
                        if Path(paths[2]).exists():
                            gtdbtk_loaded.add(genome)

            for genome in list(pending):
                if Path(_gene_calls(genome)['loaded']).exists():
                    pending.discard(genome)
                    queue.append(genome)
                    if db_path:
                        if run_gtdbtk_enabled and genome not in gtdbtk_stored:
                            _safely(f'Caching GTDB-Tk for {genome}', store, db_path, genome_files[genome], 'gtdbtk',
                                    self._gtdbtk_split_paths(genome, smk_config))
                            gtdbtk_stored.add(genome)
                        if genome not in prodigal_genomes and not rasttk_restored.get(genome, False):
                            _safely(f'Caching RASTtk for {genome}', store, db_path, genome_files[genome], 'rasttk',
                                    self._rasttk_paths(genome, smk_config))

            # The genomes in Stage 2: finished tools stored, ended ones wrapped up.
            for slot in list(active):
                _store_ready(slot)
                if slot['proc'] is None or slot['proc'].poll() is not None:
                    active.remove(slot)
                    _finish(slot)

            # Run again: a failed genome asked for from the Jobs page goes back in the queue.
            for genome in _asks():
                if genome in failed:
                    failed.remove(genome)
                    asked_again.add(genome)
                    progress_memo.pop(genome, None)
                    processed -= 1
                    queue.append(genome)
                    LOGGER.info('Running %s again from its failed step, as asked from the Jobs page', genome)
                    _answer(genome, True, f'{genome} goes back in the queue and runs again from its failed step.')
                else:
                    why = ('it is running now' if any(s['genome'] == genome for s in active)
                           else 'it is waiting for its turn' if genome in queue or genome in pending
                           else 'it has finished' if genome in finished
                           else 'its gene calls (RASTtk or Prodigal) did not finish; Resume runs them again once this run ends' if genome in skipped
                           else 'it is not in this run')
                    LOGGER.info('A request to run %s again was set aside: %s', genome, why)
                    _answer(genome, False, f'{genome} was not run again: {why}.')

            if not queue:
                if not active and stage1.poll() is not None and pending:
                    # No token after Stage 1 exit: phase1-3 failure, skipped.
                    LOGGER.warning('Stage 1 exited without producing a RASTtk token for: %s -- skipping',
                                   sorted(pending))
                    skipped.extend(pending)
                    pending.clear()
                elif pending or active:
                    time.sleep(10)
                continue

            # Most complete first; memoised since pending genomes do not change.
            if len(queue) > 1:
                queue.sort(
                    key=lambda g: progress_memo.setdefault(
                        g, self._genome_stage2_progress(g, genome_files[g], smk_config)),
                    reverse=True,
                )
            while queue and len(active) < at_once:
                genome = queue.pop(0)
                processed += 1
                LOGGER.info('=== STAGE 2: genome %d/%d (%s) phase4-12 starting, up to %d at a time ===',
                            processed, total, genome, at_once)
                slot = _start(genome)
                if slot is not None:
                    active.append(slot)
            if active:
                time.sleep(10)

        _requests_open(False)
        last_proc = last['proc']

        # Stage 3: LLM for all genomes at once; --keep-going lets one failure pass.
        if run_llm_enabled and processed > 0:
            LOGGER.info('=== Stage 3: LLM scoring for all %d genome(s) (rule llm_all) ===', processed)
            stage3_command = self.build_executable(selected_wf, config_overrides=smk_config, mode=mode,
                                                    compute_config=compute_config, extra_resources=extra_resources,
                                                    rerun_triggers=rerun_triggers, target='llm_all')
            LOGGER.info('Starting Stage 3 (llm_all): %s', ' '.join(stage3_command))
            stage3_proc = self._run_subprocess(stage3_command)
            last_proc = stage3_proc
            if stage3_proc is None or stage3_proc.returncode != 0:
                rc_val = stage3_proc.returncode if stage3_proc else None
                LOGGER.error('Stage 3 (LLM) failed (rc=%s) -- pipeline CPU phases completed successfully; '
                             'LLM results are missing but DB is otherwise intact.', rc_val)
                result = (self._build_result(key_name, stage3_proc) if stage3_proc else
                          {'workflow': key_name, 'returncode': rc_val, 'rules_summary': {}, 'stdout_tail': '', 'stderr_tail': ''})
                self.failed(msg=f'Workflow "{key_name}" Stage 3 (LLM) failed', dex=result)
                return rc_val or 1

        stage1.wait()
        if stage1.poll() != 0:
            LOGGER.warning('Stage 1 (rasttk_all) exited with rc=%s after Stage 2/3 finished draining', stage1.poll())
        if quast_proc is not None and quast_proc.wait() != 0:
            LOGGER.warning('QUAST exited rc=%s: assembly quality is missing for some genomes; '
                           'the annotations are complete without it', quast_proc.poll())

        if skipped:
            LOGGER.warning('%d genome(s) skipped (RASTtk/GTDB-Tk did not finish): %s', len(skipped), sorted(skipped))
        if failed:
            LOGGER.warning('%d genome(s) failed in Stage 2 (phase4-10): %s', len(failed), sorted(failed))
        # The run-wide finalize steps wait for a run with no gaps; the finished genomes' folders are
        # reorganized either way, and a failed genome's stay as they are for a rerun.
        gaps = bool(skipped or failed)

        run_scoring_enabled = smk_config.get('run_scoring', True) not in (False, 'false', '0', 'no')
        queue_sqlite_backup_enabled = smk_config.get('run_sqlite_snapshot_queue', True) not in (False, 'false', '0', 'no')
        if run_scoring_enabled and queue_sqlite_backup_enabled and processed > 0 and not gaps:
            LOGGER.info('=== FINALIZE: queue background sqlite snapshot backup ===')
            finalize_command = self.build_executable(
                selected_wf,
                config_overrides=smk_config,
                mode=mode,
                compute_config=compute_config,
                extra_resources=extra_resources,
                rerun_triggers=rerun_triggers,
                target='queue_sqlite_backup_snapshot',
            )
            LOGGER.info('Starting finalize target (queue_sqlite_backup_snapshot): %s', ' '.join(finalize_command))
            finalize_proc = self._run_subprocess(finalize_command)
            if finalize_proc is None or finalize_proc.returncode != 0:
                LOGGER.warning(
                    'Could not queue sqlite backup snapshot (target queue_sqlite_backup_snapshot, rc=%s). '
                    'Pipeline outputs are complete; continuing without blocking completion status.',
                    finalize_proc.returncode if finalize_proc else None,
                )

        # Pangenome report figures in an isolated subprocess; a failure only warns.
        report_figures_enabled = smk_config.get('run_report_figures', True) not in (False, 'false', '0', 'no')
        if run_scoring_enabled and report_figures_enabled and processed > 0 and not gaps:
            LOGGER.info('=== FINALIZE: generate pangenome report figures ===')
            figures_command = self.build_executable(
                selected_wf,
                config_overrides=smk_config,
                mode=mode,
                compute_config=compute_config,
                extra_resources=extra_resources,
                rerun_triggers=rerun_triggers,
                target='run_report_figures_global',
            )
            LOGGER.info('Starting finalize target (run_report_figures_global): %s', ' '.join(figures_command))
            figures_proc = self._run_subprocess(figures_command)
            if figures_proc is None or figures_proc.returncode != 0:
                LOGGER.warning(
                    'Could not generate pangenome report figures (target run_report_figures_global, rc=%s). '
                    'Pipeline outputs are complete; continuing without blocking completion status.',
                    figures_proc.returncode if figures_proc else None,
                )

        # FINALIZE: reorganises organism folders outside the DAG; a failure only warns.
        reorganize_enabled = smk_config.get('run_reorganize_outputs', True) not in (False, 'false', '0', 'no')
        output_dir = (smk_config.get('output_dir') or self.conf.get('output_dir', '') or '').rstrip('/')
        if run_scoring_enabled and reorganize_enabled and finished and output_dir:
            LOGGER.info('=== FINALIZE: reorganize per-organism output folders ===')
            reorg_script = str(WORKFLOW_DIR / 'reorganize_outputs.py')
            excel_script = str(WORKFLOW_DIR / 'fingerprint' / 'make-final-excel.py')
            reorg_workers = str(min(4, max(1, len(finished))))
            reorg_command = [
                sys.executable, reorg_script,
                '--run-root', output_dir,
                '--genomes', *finished,
                '--figures-dirname', 'diagrams',
                '--excel-script', excel_script,
                '--python', sys.executable,
                '--workers', reorg_workers,
            ]
            LOGGER.info('Starting finalize step (reorganize_outputs): %s', ' '.join(reorg_command))
            try:
                reorg_proc = subprocess.run(reorg_command, capture_output=True, text=True)
                for line in (reorg_proc.stdout or '').splitlines():
                    LOGGER.info('[reorganize] %s', line)
                if reorg_proc.returncode != 0:
                    LOGGER.warning(
                        'Output reorganization exited rc=%s (stderr: %s). Pipeline outputs are '
                        'complete; continuing without blocking completion status.',
                        reorg_proc.returncode, (reorg_proc.stderr or '').strip()[:500],
                    )
            except Exception as reorg_exc:  # never let cleanup fail the run
                LOGGER.warning('Output reorganization raised %s; continuing.', reorg_exc)

        result = self._build_result(key_name, last_proc) if last_proc else {'workflow': key_name, 'rules_summary': {}}
        stage1_rc = stage1.poll()
        result['stage1_returncode'] = stage1_rc
        done = processed - len(failed)
        failed_names = ', '.join(sorted(failed))
        result['genomes_total'] = total
        result['genomes_processed'] = done
        result['genomes_skipped'] = sorted(skipped)
        result['genomes_failed'] = sorted(failed)

        summary = (f'{done}/{total} genome(s) processed'
                   f'{f", {len(failed)} failed ({failed_names})" if failed else ""}'
                   f'{f", {len(skipped)} skipped" if skipped else ""}')

        # No output: reported as a failure, since the GUI decides by exit code.
        if total > 0 and done == 0:
            self.failed(
                msg=f'Workflow "{key_name}" produced nothing ({summary})'
                    f'{f" -- Stage 1 (rasttk_all) exited rc={stage1_rc}" if stage1_rc else ""}',
                dex=result,
            )
            return stage1_rc or 1

        # Partial run: outputs stand, but reported as inconclusive (exit 0, no banner).
        if gaps or stage1_rc:
            self.finished(
                msg=f'Workflow "{key_name}" completed with gaps ({summary})'
                    f'{f" -- Stage 1 (rasttk_all) exited rc={stage1_rc}" if stage1_rc else ""}',
                dex=result,
            )
            return

        self.succeeded(
            msg=f'Workflow "{key_name}" completed ({summary})',
            dex=result,
        )

    @command
    def do_example(self):
        '''example workflow to execute'''
        input_file = self.conf.get('input', None)
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf example input: <file>')
            self.failed('No input file specified')
            return 1

        input_path = Path(input_file)
        prodigal_config = self.conf.get('prodigal', {})

        smk_config = {
            'input_fasta': input_file,
            'output_fasta': f"{input_path.stem}-output.txt",
            'prodigal_threads': prodigal_config.get('threads', 4),
        }

        self._run_pipeline('example', smk_config)

    def _selftest_config(self, stem, tmpdir, inject_failure=False):
        '''Build smk_config and cache_map for selftest workflows.'''
        td = Path(tmpdir)
        out_step_a = str(td / f"step_a/{stem}-step_a.out")
        out_step_a_extra = str(td / f"step_a/{stem}-step_a.extra")
        out_step_a_db = str(td / f"step_a/{stem}-step_a_db.tkn")
        out_step_b = str(td / f"step_b/{stem}-step_b.out")
        out_step_b_db = str(td / f"step_b/{stem}-step_b_db.tkn")
        out_step_c_primary = str(td / f"step_c/{stem}-step_c.tsv")
        out_step_c_secondary = str(td / f"step_c/{stem}-step_c_count.tsv")
        out_step_c_db = str(td / f"step_c/{stem}-step_c_db.tkn")

        # For selftest, use temp DB path (not required from config)
        selftest_db = str(td / 'selftest.db')

        smk_config = {
            'workdir': tmpdir,
            'stem': stem,
            'inject_failure': str(inject_failure).lower(),
            'out_step_a': out_step_a,
            'out_step_a_extra': out_step_a_extra,
            'out_step_a_db': out_step_a_db,
            'out_step_b': out_step_b,
            'out_step_b_db': out_step_b_db,
            'out_step_c_primary': out_step_c_primary,
            'out_step_c_secondary': out_step_c_secondary,
            'out_step_c_db': out_step_c_db,
            'main_database': selftest_db,
        }

        cache_map = {
            'step_a': [out_step_a, out_step_a_extra],
            'step_a_db': [out_step_a_db],
            'step_b': [out_step_b],
            'step_b_db': [out_step_b_db],
            'step_c': [out_step_c_primary, out_step_c_secondary],
            'step_c_db': [out_step_c_db],
        }

        return smk_config, cache_map

    @command
    def do_quick_example(self, inject_failure=False):
        '''Run selftest with real margie.db cache (deterministic input — cached on second run).'''
        stem = 'quick-example'

        with tempfile.TemporaryDirectory(prefix='dane_quick_') as tmpdir:
            # Deterministic content so the hash is stable across runs.
            # First run: cache miss → snakemake runs → store_all caches.
            # Second run: cache hit → restore_all writes files → snakemake skips.
            tmp_input = str(Path(tmpdir) / f'{stem}.txt')
            Path(tmp_input).write_text('quick-example deterministic input\n')

            smk_config, cache_map = self._selftest_config(stem, tmpdir, inject_failure)
            smk_config['input_file'] = tmp_input

            self._run_pipeline('selftest', smk_config, cache_map, mode='dev')

    @command
    def do_fresh_test(self, inject_failure=False):
        '''Run selftest with real margie.db — unique input each run so cache always misses.'''
        stem = 'fresh-test'

        with tempfile.TemporaryDirectory(prefix='dane_freshtest_') as tmpdir:
            # Unique content per run (includes timestamp) so the hash is always new.
            # restore_all will miss → snakemake runs all rules → store_all caches.
            tmp_input = str(Path(tmpdir) / f'{stem}.txt')
            Path(tmp_input).write_text(f'fresh-test {self.timestamp}\n')

            smk_config, cache_map = self._selftest_config(stem, tmpdir, inject_failure)
            smk_config['input_file'] = tmp_input

            self._run_pipeline('selftest', smk_config, cache_map, mode='dev')

    @command
    def do_margie(self, mode='slurm'):
        '''run margie workflow'''
        input_file = (self.conf.get('input', None)
                      or self.conf.get('margie', {}).get('input_path', None)
                      or WORKFLOW_PATH_DEFAULTS.get('margie', {}).get('input_path'))
        if not input_file:
            LOGGER.error('No input file specified. Use: dane_wf margie input: <file>, '
                        'or set margie.input_path in your ~/.config/bioinformatics-tools/config.yaml')
            self.failed('No input file specified')
            return 1

        # Require main_database from config - no fallback
        main_database = self.conf.get('main_database', None)
        if not main_database:
            LOGGER.error('main_database not set in config. Add main_database: <path> to your ~/.config/bioinformatics-tools/config.yaml')
            self.failed('main_database configuration is required')
            return 1

        # Expand ~ in database path (SQLite doesn't understand ~)
        main_database = str(Path(main_database).expanduser())

        # Extract and validate compute config for SLURM mode
        compute_config = None
        if mode != 'dev':
            compute_config = self.conf.get('compute', {}).get('cluster_default', {})
            slurm_account = compute_config.get('account', '').strip()
            if not slurm_account:
                LOGGER.error('compute.cluster_default.account not set in config. Add account: <your-slurm-account> to your ~/.config/bioinformatics-tools/config.yaml')
                self.failed('SLURM account configuration is required for cluster execution')
                return 1

        stem = Path(input_file).stem
        output_dir = (self.conf.get('output_dir', None)
                      or self.conf.get('margie', {}).get('output_path', None)
                      or WORKFLOW_PATH_DEFAULTS.get('margie', {}).get('output_path', ''))
        prefix = f"{output_dir.rstrip('/')}/" if output_dir else ''

        # Only pass workflow-specific overrides to Snakemake
        # The full config is loaded via --configfile from self.config_paths
        config_overrides = {
            'input_fasta': input_file,
            'output_dir': prefix.rstrip('/'),
            'main_database': main_database,
        }

        # Cache map - compute paths using same logic as workflow_helpers
        # Note: These paths must match what margie.smk generates (includes stem subdirectory)
        prefix_with_stem = f"{prefix}{stem}/"
        out_prodigal_gff = f"{prefix_with_stem}prodigal/{stem}-prodigal.gff"
        out_prodigal_faa = f"{prefix_with_stem}prodigal/{stem}-prodigal.faa"
        out_prodigal_db = f"{prefix_with_stem}prodigal/prodigal_db.tkn"
        out_pfam = f"{prefix_with_stem}pfam/pfam.tsv"
        out_pfam_db = f"{prefix_with_stem}pfam/pfam_db.tkn"
        out_cog_tkn = f"{prefix_with_stem}cog/cog.tkn"
        out_cog_classify = f"{prefix_with_stem}cog/cog_classify.tsv"
        out_cog_count = f"{prefix_with_stem}cog/cog_count.tsv"
        out_cog_db = f"{prefix_with_stem}cog/cog_db.tkn"
        out_kofam = f"{prefix_with_stem}kofam/kofam.tsv"
        out_kofam_db = f"{prefix_with_stem}kofam/kofam_db.tkn"
        out_uniop = f"{prefix_with_stem}uniop/operons.tsv"
        out_uniop_db = f"{prefix_with_stem}uniop/uniop_db.tkn"
        out_dbcan = f"{prefix_with_stem}dbcan/overview.tsv"
        out_dbcan_db = f"{prefix_with_stem}dbcan/dbcan_db.tkn"

        # Cache map - each tool includes ALL files (intermediates + token)
        # This ensures when we have a cache HIT, we restore everything Snakemake needs
        cache_map = {
            'prodigal': [out_prodigal_gff, out_prodigal_faa, out_prodigal_db],
            'pfam': [out_pfam, out_pfam_db],
            'cog': [out_cog_tkn, out_cog_classify, out_cog_count, out_cog_db],
            'kofam': [out_kofam, out_kofam_db],
            'uniop': [out_uniop, out_uniop_db],
            'dbcan': [out_dbcan, out_dbcan_db],
        }

        self._run_pipeline('margie', config_overrides, cache_map, mode=mode, compute_config=compute_config)

    @command
    def do_margie_sb(self, mode='slurm'):
        '''Runs the margie_sb workflow on a single genome file or a folder of genomes.'''
        input_path_value = (self.conf.get('input', None)
                            or self.conf.get('margie_sb', {}).get('input_path', None)
                            or WORKFLOW_PATH_DEFAULTS.get('margie_sb', {}).get('input_path'))
        if not input_path_value:
            LOGGER.error('No input specified. Use: dane_wf margie_sb input: <file_or_folder>, '
                        'or set margie_sb.input_path in your ~/.config/bioinformatics-tools/config.yaml')
            self.failed('No input file or folder specified')
            return 1

        main_database = self.conf.get('main_database', None)
        if not main_database:
            LOGGER.error('main_database not set in config. Add main_database: <path> to your ~/.config/bioinformatics-tools/config.yaml')
            self.failed('main_database configuration is required')
            return 1

        main_database = str(Path(main_database).expanduser())

        compute_config = None
        if mode != 'dev':
            compute_config = self.conf.get('compute', {}).get('cluster_default', {})
            slurm_account = compute_config.get('account', '').strip()
            if not slurm_account:
                LOGGER.error('compute.cluster_default.account not set in config. Add account: <your-slurm-account> to your ~/.config/bioinformatics-tools/config.yaml')
                self.failed('SLURM account configuration is required for cluster execution')
                return 1

        # The genomes directly in the folder, as margie_sb.smk and the website see them: one
        # in a subfolder would be sent to GTDB-Tk and then have no rule (MissingInputException).
        genomes = discover_genomes(input_path_value)
        if not genomes:
            LOGGER.error('No genome files found at %s', input_path_value)
            self.failed(f'No genome files found at {input_path_value}')
            return 1

        output_dir = (self.conf.get('output_dir', None)
                      or self.conf.get('margie_sb', {}).get('output_path', None)
                      or WORKFLOW_PATH_DEFAULTS.get('margie_sb', {}).get('output_path', ''))

        # Right after the genome hash check, before GTDB-Tk: each genome runs as <name>--<its hash>
        # (coli--a1b2c3d4), so genomes that share a file name stay apart in every table, result and
        # in scoring's operon reference. The run reads a folder of links under those names.
        if output_dir:
            input_path_value = named_with_hash(genomes, f"{output_dir.rstrip('/')}/.margie-input")
            genomes = discover_genomes(input_path_value)
            LOGGER.info('Genomes, named with their hashes: %s', ', '.join(genomes))

        config_overrides = {
            'input_fasta': input_path_value,
            'output_dir': output_dir.rstrip('/') if output_dir else '',
            'main_database': main_database,
        }

        # Production default: stops at scoring (phase11); later phases are opt-in.
        _tool_to_run_flag = {'scoring_heuristic': 'run_scoring'}
        _post_scoring_tools = {
            'fingerprint',
            'fingerprint_database',
            'operon_fingerprint',
            'annotation_gff',
            'genome_pool',
            'ani',
            'aai',
            'closest',
            'mauve',
            'synteny',
            'evidence',
            'llm',
        }
        for tool_key in _post_scoring_tools:
            config_overrides[_tool_to_run_flag.get(tool_key, f'run_{tool_key}')] = False

        # selected_tools, else default_selected_tools, else the production defaults.
        _margie_sb_conf = self.conf.get('margie_sb', {})
        selected_tools_raw = (
            _margie_sb_conf.get('selected_tools', '')
            or _margie_sb_conf.get('default_selected_tools', '')
        )
        sif_files_override = None
        if selected_tools_raw:
            selected_tool_keys = {t.strip() for t in selected_tools_raw.split(',') if t.strip()}
            # The tools every run needs come with any choice.
            selected_tool_keys |= MARGIE_SB_REQUIRED_TOOLS
            for tool in MARGIE_SB_PHASED_TOOLS:
                run_flag = _tool_to_run_flag.get(tool['key'], f"run_{tool['key']}")
                config_overrides[run_flag] = tool['key'] in selected_tool_keys
            # rasttk stays on; fingerprint_database also enables operon-fingerprint DBs.
            if config_overrides.get('run_fingerprint_database'):
                config_overrides['run_operon_fingerprint'] = True
            sif_files_override = margie_sb_sif_files(selected_tool_keys | {'rasttk'} | (
                {'gtdbtk'} if config_overrides.get('run_gtdbtk', True) else set()))

        # ---- Licensing gate: accepted terms required, unlicensed tools disabled ----
        from bioinformatics_tools.workflow_tools.env_keys import ensure_api_keys
        ensure_api_keys()
        from bioinformatics_tools.workflow_tools.license_gate import (
            ensure_cli_license, LicenseError,
        )
        from bioinformatics_tools.api.licensing.catalog import disabled_tool_ids
        try:
            _entitlement = ensure_cli_license()
        except LicenseError as _exc:
            LOGGER.error('%s', _exc)
            self.failed(str(_exc))
            return 1
        _gateable_keys = {tool['key'] for tool in MARGIE_SB_PHASED_TOOLS}
        _disabled = disabled_tool_ids(
            _entitlement.get('usage_type'), _entitlement.get('licensed_tools')
        ) & _gateable_keys
        if _disabled:
            # Refuses if the caller explicitly asked for a tool they cannot run.
            if selected_tools_raw:
                _conflict = selected_tool_keys & _disabled
                if _conflict:
                    _msg = (
                        'These tools require a license you have not confirmed: '
                        f"{', '.join(sorted(_conflict))}. Remove them from "
                        'selected_tools, or record the license via the pipeline '
                        'setup / web app, then re-run.'
                    )
                    LOGGER.error('%s', _msg)
                    self.failed(_msg)
                    return 1
            # Otherwise disables them and drops their containers from validation.
            for _tid in _disabled:
                config_overrides[_tool_to_run_flag.get(_tid, f'run_{_tid}')] = False
            if selected_tools_raw:
                _keep = (selected_tool_keys - _disabled) | {'rasttk'} | (
                    {'gtdbtk'} if config_overrides.get('run_gtdbtk', True) else set())
            else:
                _keep = _gateable_keys - _disabled
            sif_files_override = margie_sb_sif_files(_keep)
            LOGGER.warning(
                'Licensing: disabled (not licensed for your usage type): %s',
                ', '.join(sorted(_disabled)),
            )

        # Prodigal genomes (GTDB-Tk off, no genome_info entry): RASTtk-based results stand in when the
        # database has them; otherwise their results stay out of the MARGIE caches.
        _calls = genome_calls(genomes, {'run_gtdbtk': config_overrides.get('run_gtdbtk', True),
                                        'margie_sb': self._margie_sb_dict()})
        prodigal_genomes = {g for g, c in _calls.items() if c['gene_caller'] == 'prodigal'}
        if prodigal_genomes:
            LOGGER.info('Prodigal calls the genes of %d genome(s) with no domain or genetic code: %s',
                        len(prodigal_genomes), ', '.join(sorted(prodigal_genomes)))
            sif_files_override = [*(margie_sb_sif_files() if sif_files_override is None else sif_files_override),
                                  ('prodigal.sif', 'latest')]

        def _genome_cache_map(genome: str) -> dict[str, list[str]]:
            '''Returns each phase 4-8 tool's output files for one genome, keyed by
            tool name, for restore_all()/store_all().

            Excludes gtdbtk/rasttk, which run as batches the DAG replans anyway, and
            QUAST, never cached: it measures the assembly submitted, and two assemblies
            of one strain can differ in quality. _run_pipeline_batch_sequential leaves
            out the genomes Prodigal calls the genes of.'''
            prefix = get_workflow_prefix_for(genome, config_overrides)
            simple_tools = ['cog', 'pfam', 'merops', 'tcdb', 'uniprot', 'kegg', 'eggnog',
                            'dbcan', 'pgap', 'geneprop', 'operon', 'tmbed', 'signalp6',
                            'deepsig', 'psortb', 'signalp4']
            cache_map = {t: [f'{prefix}{t}/{t}_results.tsv', f'{prefix}{t}/{t}_db.tkn'] for t in simple_tools}
            cache_map['tigrfam'] = [f'{prefix}tigrfam/tigrfam_results.tsv',
                                     f'{prefix}tigrfam/tigrfam_domtbl.out',
                                     f'{prefix}tigrfam/tigrfam_db.tkn']
            cache_map['phobius'] = [f'{prefix}phobius/phobius_results.tsv',
                                     f'{prefix}phobius/phobius_top1.tsv',
                                     f'{prefix}phobius/phobius_db.tkn']
            cache_map['envelope'] = [f'{prefix}envelope/envelope_results.tsv',
                                      f'{prefix}envelope/envelope_summary.tsv',
                                      f'{prefix}envelope/envelope_db.tkn']
            interpro_paths = [f'{prefix}interpro/interpro_results.tsv', f'{prefix}interpro/interpro_db.tkn']
            for db in INTERPRO_DB_BASENAMES:
                interpro_paths += [f'{prefix}interpro/interpro_{db}_results.tsv',
                                    f'{prefix}interpro/interpro_{db}_db.tkn']
            cache_map['interpro'] = interpro_paths
            # From consolidation on, nothing is cached: consolidation and labeling take about a minute and
            # their tables take hundreds of MB a genome; scoring's operon reference grows with each run.
            return cache_map

        # RASTtk concurrency: a mkdir mutex in margie_sb.smk's run_rasttk rule.

        # Number of phase4 tools running at once (margie_sb.phase4.max_parallel_tools).
        max_parallel_tools = self.conf.get('margie_sb', {}).get('phase4', {}).get('max_parallel_tools', 4)
        extra_resources = {
            'margie_sb_phase4_slot': max_parallel_tools,
            # One database load at a time (margie_sb.smk, load_minutes).
            'margie_sb_db_writer': 1,
            # One RASTtk (BV-BRC) job at a time (margie_sb.smk, run_rasttk).
            'margie_sb_bvbrc': 1,
        }

        # Set by resume_job's relaunch; mtime-only triggers treat copied outputs as done.
        resume_raw = str(self.conf.get('margie_sb', {}).get('resume', '')).strip().lower()
        rerun_triggers = 'mtime' if resume_raw not in ('false', '0', 'no', 'off', '') else None

        self._run_pipeline_batch_sequential('margie_sb', config_overrides, genomes,
                                 cache_map_fn=_genome_cache_map, mode=mode, compute_config=compute_config,
                                 extra_resources=extra_resources, sif_files_override=sif_files_override,
                                 rerun_triggers=rerun_triggers, prodigal_genomes=prodigal_genomes)
