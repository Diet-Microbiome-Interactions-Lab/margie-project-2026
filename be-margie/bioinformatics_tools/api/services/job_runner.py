"""
Job execution and monitoring.

Contains the core SSH task runner that streams remote output, parses logs
for SLURM job IDs, Snakemake progress, and container metadata, and the
SLURM status checker daemon thread.

The `connection` parameter threads a per-user SSHConnection through from the
API router all the way to the SLURM status checker daemon, so every SSH call
hits the correct cluster and account.
"""
import asyncio
import datetime
import json
import logging
import os
from pathlib import PurePosixPath
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from bioinformatics_tools.utilities import ssh_slurm
from bioinformatics_tools.utilities.ssh_connection import SSHConnection
from bioinformatics_tools.api.services import hosting_usage, run_mail
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.workflow_tools.usage_report import MARKER as USAGE_REPORT

LOGGER = logging.getLogger(__name__)

# Thread pool for background SSH tasks
# One thread watches each run for as long as it goes (hours, days), for every user at once,
# so the pool is sized for many runs; a watcher ends with its run, or when it is cancelled.
executor = ThreadPoolExecutor(max_workers=int(os.environ.get('BSP_MAX_WATCHED_RUNS', '64')))

# Regex patterns for parsing Snakemake/SLURM log output
# Grouped rules capture only the group's short name (see margie_sb.smk).
SLURM_SUBMIT_RE = re.compile(r'SLURM jobid (\d+) \(log: (.*?)\)\.?$')
RULE_NAME_FROM_LOG_PATH_RE = re.compile(r'/slurm_logs/(?:rule_(\w+)|group_([^_]+)_\w+)/')
SLURM_SUBMIT_FALLBACK_RE = re.compile(r'SLURM jobid (\d+)')
# Genome is the dir between rule and log file; batch rules have none, so empty.
GENOME_FROM_LOG_PATH_RE = re.compile(r'/slurm_logs/[^/]+/([^/]+)/[^/]+$')
STEPS_PROGRESS_RE = re.compile(r'(\d+) of (\d+) steps \((\d+)%\) done')
CACHE_HIT_RE = re.compile(r'Cache HIT for (\w+) \(genome=([^)]+)\)')
RESTORED_FROM_CACHE_RE = re.compile(r'Restored from cache:\s+(.+)$')
# Fallback genome source: Snakemake's --verbose "wildcards: genome=..." line.
WILDCARDS_GENOME_RE = re.compile(r'wildcards:.*\bgenome=([^\s,]+)')
# Sequential orchestrator's per-genome progress; step counts reset per genome.
# "STAGE 2: genome i/N" as genomes start (older logs say "SEQUENTIAL: genome i/N").
SEQUENTIAL_GENOME_RE = re.compile(r'(?:SEQUENTIAL|STAGE 2): genome (\d+)/(\d+)')
# "=== LOADS: <genome> waiting|loading|loaded|not loaded" as Stage 2's genomes load (workflow.py).
LOADS_RE = re.compile(r'=== LOADS: (\S+) (waiting|loading|loaded|not loaded)')


def _slurm_status_checker(job_id: str, connection: SSHConnection):
    """Daemon thread that periodically checks SLURM job statuses."""
    driver_checked = 0.0
    while job_store.get_status(job_id) == "running":
        slurm_jobs = job_store.get_slurm_jobs(job_id)
        active_ids = [sj["job_id"] for sj in slurm_jobs if sj["status"] not in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "CACHED")]
        if active_ids:
            try:
                statuses = ssh_slurm.check_multiple_slurm_jobs(active_ids, connection=connection)
                for sj in slurm_jobs:
                    if sj["job_id"] in statuses:
                        sj["status"] = statuses[sj["job_id"]]["state"]
                        sj["time"] = statuses[sj["job_id"]]["time"]
            except Exception as e:
                LOGGER.warning("SLURM status check failed: %s", e)

        # Backfills genomes missed in the live log; stays empty for batch rules.
        for sj in slurm_jobs:
            if not sj.get("genome") and sj.get("log_path"):
                # Path check first: free and cannot race log cleanup.
                path_match = GENOME_FROM_LOG_PATH_RE.search(sj["log_path"])
                if path_match:
                    sj["genome"] = path_match.group(1)
                    continue
                try:
                    genome = ssh_slurm.get_job_genome(sj["log_path"], connection=connection)
                    if genome:
                        sj["genome"] = genome
                except Exception as e:
                    LOGGER.warning("Genome backfill failed for job %s: %s", sj["job_id"], e)

        # A step pending for over an hour, or the run's own job before any step, is emailed about once.
        now = time.time()
        for sj in slurm_jobs:
            if sj["status"] == "PENDING":
                sj.setdefault("pending_since", now)
        if any(sj["status"] == "PENDING" and now - sj["pending_since"] > run_mail.PENDING_SECONDS for sj in slurm_jobs):
            run_mail.notify(job_id, "pending", connection)
        elif not slurm_jobs and now - driver_checked > 300 and now - _started(job_id) > run_mail.PENDING_SECONDS:
            driver_checked = now
            if run_mail.driver_pending(job_id, connection):
                run_mail.notify(job_id, "pending", connection)

        # Persists this cycle's status changes; checkpoint() throttles.
        job_store.checkpoint(job_id)

        # Wait 15 seconds between checks
        for _ in range(15):
            if job_store.get_status(job_id) != "running":
                break
            time.sleep(1)


def _started(job_id: str) -> float:
    """When the run was started, in seconds since the epoch (now when unknown)."""
    try:
        return datetime.datetime.fromisoformat(job_store.get(job_id)["start_time"]).timestamp()
    except (TypeError, KeyError, ValueError):
        return time.time()


def run_ssh_task(job_id: str, command: str, connection: SSHConnection,
                 reattach: bool = False, in_slurm: bool = True,
                 driver_account: str | None = None,
                 driver_partition: str | None = None,
                 driver_time: str | None = None,
                 copy_from: str | None = None,
                 copy_to: str | None = None,
                 copy_only: list[str] | None = None):
    """Runs an SSH command, parsing its log for SLURM jobs, containers and progress.

    reattach=True replays the log of a run already going (after a dane-api
    restart) without launching anything; logs is reset first so lines are not doubled.
    """
    job_store.update(job_id, status="running", logs="",
                     phase="Reattaching to running job" if reattach else "Submitting via SSH")

    # Start SLURM status checker daemon thread (passes the same connection through)
    checker = threading.Thread(
        target=_slurm_status_checker,
        args=(job_id, connection),
        daemon=True
    )
    checker.start()

    def register_cached_job(rule_name: str, genome_name: str) -> None:
        job_store.add_slurm_job(job_id, "—", rule_name, genome=genome_name, source="from cache")
        for sj in job_store.get_slurm_jobs(job_id):
            if sj["job_id"] == "—" and sj["rule"] == rule_name and sj.get("genome") == genome_name:
                # Immediately mark as CACHED so the checker skips it
                sj["status"] = "CACHED"

    exit_code = 0  # Track command exit code
    last_genome = ""  # Most recently seen "wildcards: genome=..." value
    log_bytes = 0  # What the run's log brought in, for its resource report
    saw_snakemake_syntax_error = False

    try:
        # job_id names the log/sentinel files so a reconnect can replay them.
        detached = False
        launched = False
        ended_unfinished = False
        # The genomes waiting for a place to load or loading: {genome: 'waiting' | 'loading'}.
        loads: dict[str, str] = {}
        # The genomes loaded (annotated and in the database), and those not loaded as their Stage 2 failed.
        loaded: set[str] = set()
        not_loaded: set[str] = set()
        for line in ssh_slurm.submit_ssh_job(cmd=command, connection=connection,
                                             job_id=job_id, reattach=reattach,
                                             in_slurm=in_slurm,
                                             driver_account=driver_account,
                                             driver_partition=driver_partition,
                                             driver_time=driver_time,
                                             copy_from=copy_from, copy_to=copy_to, copy_only=copy_only,
                                             # A cancelled run stops being watched, freeing its thread.
                                             stop=lambda: job_store.get_status(job_id) == "cancelled"):
            log_bytes += len(line) + 1
            # Run is live on the cluster; later errors only affect watching it.
            if line == "__LAUNCHED__":
                launched = True
                continue

            # The driver's SLURM job has gone without finishing (cancelled on the cluster, out of time).
            if line == "__ENDED_UNFINISHED__":
                ended_unfinished = True
                break

            # Watching stopped, not the run; job state is left unchanged.
            if line == "__DETACHED__":
                detached = True
                LOGGER.info("Stopped streaming job %s; it continues on the cluster", job_id)
                break

            # Detect exit code metadata from submit_ssh_job
            if line.startswith("__EXIT_CODE__:"):
                try:
                    exit_code = int(line.split(":", 1)[1])
                    LOGGER.info("Captured exit code: %d", exit_code)
                except (ValueError, IndexError):
                    LOGGER.warning("Failed to parse exit code from: %s", line)
                continue

            # Detect structured Report metadata from workflow
            if line.startswith("__REPORT__:"):
                try:
                    report_json = line.split(":", 1)[1]
                    report_data = json.loads(report_json)
                    job_store.update(job_id, report=report_data)
                    LOGGER.info("Captured structured report: status=%s", report_data.get('status', {}).get('code'))
                except (json.JSONDecodeError, IndexError) as e:
                    LOGGER.warning("Failed to parse report JSON: %s", e)
                continue

            # The run's resource report (usage_report.py), written as the run ends.
            if line.startswith(USAGE_REPORT):
                job_store.update(job_id, usage_report=line[len(USAGE_REPORT):].strip())
                continue

            # Detect work_dir metadata from submit_ssh_job
            if line.startswith("__WORKDIR__:"):
                job_store.update(job_id, work_dir=line.split(":", 1)[1])
                continue

            # Parse container metadata from bapptainer log lines
            if "__CONTAINER__:" in line:
                try:
                    container_json = line.split("__CONTAINER__:", 1)[1]
                    job_store.add_container(job_id, json.loads(container_json))
                except (json.JSONDecodeError, IndexError):
                    pass

            job_store.append_log(job_id, line)

            # output_cache.py "Cache HIT for <tool> (genome=...)" lines.
            cache_match = CACHE_HIT_RE.search(line)
            if cache_match:
                rule_name, cache_genome = cache_match.groups()
                register_cached_job(rule_name, cache_genome)

            # Per-file restores become cache rows even without a Cache HIT line.
            restored_match = RESTORED_FROM_CACHE_RE.search(line)
            if restored_match:
                restored_path = restored_match.group(1).strip()
                parts = PurePosixPath(restored_path).parts
                if len(parts) >= 3:
                    cache_tool = parts[-2]
                    cache_genome = parts[-3]
                    if cache_tool and cache_genome:
                        register_cached_job(cache_tool, cache_genome)

            # "wildcards: genome=..." line, printed just before submission.
            wildcards_match = WILDCARDS_GENOME_RE.search(line)
            if wildcards_match:
                last_genome = wildcards_match.group(1)

            # SLURM job IDs; log_path feeds the checker's genome backfill.
            match = SLURM_SUBMIT_RE.search(line)
            if match:
                slurm_id, log_path = match.groups()
                rule_match = RULE_NAME_FROM_LOG_PATH_RE.search(log_path)
                ungrouped_rule_name, group_name = rule_match.groups() if rule_match else (None, None)
                # Path genome first; last_genome is the fallback.
                path_genome_match = GENOME_FROM_LOG_PATH_RE.search(log_path)
                genome = (path_genome_match.group(1) if path_genome_match else "") or last_genome
                job_store.add_slurm_job(job_id, slurm_id, ungrouped_rule_name or group_name or "unknown", genome=genome, log_path=log_path)
            elif SLURM_SUBMIT_FALLBACK_RE.search(line):
                fallback = SLURM_SUBMIT_FALLBACK_RE.search(line)
                slurm_id = fallback.group(1)
                job_store.add_slurm_job(job_id, slurm_id, "unknown", genome=last_genome)

            # Parse Snakemake step progress (e.g. "2 of 4 steps (50%) done")
            progress_match = STEPS_PROGRESS_RE.search(line)
            if progress_match:
                done, total, pct = progress_match.groups()
                job_store.update(job_id, steps_done=int(done), steps_total=int(total), progress=int(pct))

            # Wrapper can exit 0 on a snakefile parse error; never completed.
            if "SyntaxError in file" in line or "Unexpected keyword" in line and "rule definition" in line:
                saw_snakemake_syntax_error = True

            loads_match = LOADS_RE.search(line)
            if loads_match:
                genome, state = loads_match.groups()
                if state in ("waiting", "loading"):
                    loads[genome] = state
                else:
                    loads.pop(genome, None)
                    (loaded if state == "loaded" else not_loaded).add(genome)
                job_store.update(job_id, loads=dict(loads), loaded=len(loaded), not_loaded=len(not_loaded))

            # Parses the orchestrator's marker as each genome starts Stage 2.
            genome_match = SEQUENTIAL_GENOME_RE.search(line)
            if genome_match:
                genome_index, genome_total = genome_match.groups()
                job_store.update(job_id, genome_index=int(genome_index), genome_total=int(genome_total))

            # Resume's copy job (ssh_slurm.build_copy_script) writes the log before the driver starts.
            if line.startswith("Resume: "):
                job_store.update(job_id, phase="Starting the run" if "the run starts next" in line
                                 else "Copying the earlier run's results")

            # Update phase based on output
            if "snakemake" in line.lower():
                job_store.update(job_id, phase="Running Snakemake")

        # Cancelled from MARGIE: the cancel has said so already; watching just stops.
        if job_store.get_status(job_id) == "cancelled":
            LOGGER.info("Stopped watching job %s: it was cancelled", job_id)
        elif ended_unfinished:
            job_store.append_log(
                job_id,
                "\n\n=== The run's SLURM job ended before the run finished (cancelled on the "
                "cluster, or out of time). ===")
            job_store.finalize(job_id, status="failed", phase="Ended before finishing")
        # Detached stops watching only; exit_code 0 must not mark it completed.
        elif detached:
            job_store.append_log(
                job_id,
                "\n\n=== Stopped streaming output. The run continues on the "
                "cluster; reopen this job to reattach. ===")
            job_store.update(job_id, phase="Running (detached)")
            LOGGER.info("Job %s left running detached", job_id)
        # Check exit code and mark as failed if non-zero
        elif exit_code != 0:
            job_store.append_log(job_id, f"\n\n=== Command exited with code {exit_code} ===")
            job_store.finalize(job_id, status="failed", phase="Failed")
            LOGGER.error("Job %s failed with exit code %d", job_id, exit_code)
        elif saw_snakemake_syntax_error:
            job_store.append_log(job_id, "\n\n=== Snakemake syntax validation failed ===")
            job_store.finalize(job_id, status="failed", phase="Failed (Snakemake syntax error)")
            LOGGER.error("Job %s failed due to Snakemake syntax error despite zero wrapper exit code", job_id)
        else:
            job_store.finalize(job_id, status="completed", phase="Done")
    except Exception as e:
        # After launch an exception is a watch failure, not an analysis failure.
        if launched:
            LOGGER.warning("Lost the log stream for job %s (%s); it continues on the cluster", job_id, e)
            job_store.append_log(
                job_id,
                f"\n\n=== Lost the connection carrying this log ({e}). "
                "The run itself is unaffected and continues on the cluster; "
                "reopen this job to reattach. ===")
            job_store.update(job_id, phase="Running (detached)")
            # force: nothing else writes provenance if the API stops first.
            job_store.checkpoint(job_id, force=True)
        else:
            job_store.append_log(job_id, f"\nError: {str(e)}")
            job_store.finalize(job_id, status="failed", phase="Error")

    # Emails the owner that the run completed or failed (run_mail, once per run), and adds the
    # hosting server's use to the run's resource report for the accounts that get it.
    job_store.update(job_id, log_bytes=log_bytes)
    final = job_store.get_status(job_id)
    if final in ("completed", "failed"):
        run_mail.notify(job_id, final, connection)
        hosting_usage.add_to_report(job_id, connection)


def submit_job(job_id: str, command: str, connection: SSHConnection,
               reattach: bool = False, in_slurm: bool = True,
               driver_account: str | None = None,
               driver_partition: str | None = None,
               driver_time: str | None = None,
               copy_from: str | None = None,
               copy_to: str | None = None,
               copy_only: list[str] | None = None):
    """Submits a job to the thread pool executor.

    in_slurm=False keeps the run on the login node, for the quick self-test workflows.
    copy_from and copy_to (Resume): the earlier run's folder (copy_only: those paths in it) is
    copied into the new one on a compute node before the run starts (ssh_slurm.build_driver_launch).
    """
    executor.submit(
        run_ssh_task,
        job_id,
        command,
        connection,
        reattach,
        in_slurm,
        driver_account,
        driver_partition,
        driver_time,
        copy_from,
        copy_to,
        copy_only,
    )


async def job_status_generator(job_id: str):
    """Generator that yields SSE events with job status updates."""
    last_state = None
    last_update_time = 0
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            status = ssh_slurm.check_slurm_job_status(job_id)
            current_state = status['state']
            elapsed = status['elapsed_time']

            current_time = asyncio.get_event_loop().time()
            check_duration = int(current_time - start_time)

            should_send = (
                current_state != last_state or
                (current_time - last_update_time) >= 7
            )

            if should_send:
                message = f"Job {current_state.lower()} (elapsed: {elapsed}, checking for: {check_duration}s)"
                data = {'state': current_state, 'elapsed': elapsed, 'message': message}
                yield f"data: {json.dumps(data)}\n\n"
                last_state = current_state
                last_update_time = current_time

            if current_state in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'NOT_FOUND']:
                data = {'state': current_state, 'elapsed': elapsed, 'done': True}
                yield f"data: {json.dumps(data)}\n\n"
                break

            await asyncio.sleep(10)

        except Exception as e:
            LOGGER.exception("Error checking job status")
            data = {'error': f'Error checking status: {str(e)}'}
            yield f"data: {json.dumps(data)}\n\n"
            break
