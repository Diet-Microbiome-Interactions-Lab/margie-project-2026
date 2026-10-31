"""
What a run left unwritten in the MARGIE database, read from its log (workflow.py's lines), genome by
genome: the writes it lost (its warnings), and every write of the genomes its database writer had not
reached when it stopped. `margie sb` with margie_sb.finish_from: <that log> makes them from the run's
folder instead of running, then the closing steps the run had not taken (workflow.py,
_finish_from_log); each write reads what the database holds first, so one made since is not made twice.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class Lost:
    """A genome's writes to make: the tools whose proteins and whose results go to the cache, or
    all its results (every), its genes' fingerprints and proteins' records, and its run log row. A
    genome the writer had not reached (whole) has all of them made."""
    proteins: set[str] = field(default_factory=set)
    results: set[str] = field(default_factory=set)
    every: bool = False
    records: bool = False
    whole: bool = False
    # The results that came back from the cache in that run: they stay as they are.
    restored: set[str] = field(default_factory=set)


@dataclass
class RunLog:
    """A run's log, as far as its writes and closing steps go."""
    run_id: str = ''
    lost: dict[str, Lost] = field(default_factory=dict)
    # Genomes whose results were loaded, and those not loaded as their Stage 2 failed.
    loaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    # Whether the run had begun its closing steps (=== FINALIZE: ...).
    closed: bool = False
    # What its Snakemake commands were given, for the closing steps: the genomes whose GTDB-Tk and
    # RASTtk outputs came from the database (cached_gtdbtk, cached_rasttk) and the rerun triggers.
    config: dict[str, str] = field(default_factory=dict)
    rerun_triggers: str = ''


RUN_ID_RE = re.compile(r'Starting sequential batch workflow "\S+" run_id=(\S+)')
PROTEINS_RE = re.compile(r'Protein cache store failed for (\S+) / (\S+?):')
RESULTS_RE = re.compile(r'Caching (\S+) for (\S+) failed \(the run goes on without it\)')
EVERY_RE = re.compile(r'Caching the rest of (\S+) failed \(the run goes on without it\)')
RESTORED_RE = re.compile(r'Phase4\+ cache restore for (\S+): (\{[^}]*\})')
RECORDS_RE = re.compile(r'Recording the (?:proteins|fingerprints) of (\S+) failed \(the run goes on without it\)')
LOADED_RE = re.compile(r'=== LOADS: (\S+) loaded: ')
NOT_LOADED_RE = re.compile(r'=== LOADS: (\S+) not loaded: ')
# A genome's last write, its run log row, names it by its hash.
WRITTEN_RE = re.compile(r'Logged workflow run: \S+ run_id=\S+ status=success .*\(hash (fa1:[0-9a-f]+)')
LABEL_RE = re.compile(r'--(fa1:[0-9a-f]+)$')
FINALIZE_RE = re.compile(r'=== FINALIZE: ')
COMMAND_RE = re.compile(r'(?:Starting Stage 2 \(|Loads pass for )')
CACHED_RE = re.compile(r'\b(cached_gtdbtk|cached_rasttk)=(\S*)')
TRIGGERS_RE = re.compile(r'--rerun-triggers (\S+)')
# Stage 1's batches are cached by their own steps, not by genome tool.
BATCHES = {'GTDB-Tk', 'RASTtk'}


def read_run_log(log: str) -> RunLog:
    """Reads what a run's log says of its writes and closing steps."""
    run = RunLog()
    restored: dict[str, set[str]] = {}
    written: set[str] = set()
    for line in log.splitlines():
        if COMMAND_RE.search(line):
            run.config.update(CACHED_RE.findall(line))
            if m := TRIGGERS_RE.search(line):
                run.rerun_triggers = m.group(1)
        if m := RESTORED_RE.search(line):
            restored[m.group(1)] = {t for t, hit in ast.literal_eval(m.group(2)).items() if hit}
        elif m := PROTEINS_RE.search(line):
            run.lost.setdefault(m.group(1), Lost()).proteins.add(m.group(2))
        elif m := EVERY_RE.search(line):
            run.lost.setdefault(m.group(1), Lost()).every = True
        elif (m := RESULTS_RE.search(line)) and m.group(1) not in BATCHES:
            run.lost.setdefault(m.group(2), Lost()).results.add(m.group(1))
        elif m := RECORDS_RE.search(line):
            run.lost.setdefault(m.group(1), Lost()).records = True
        elif m := LOADED_RE.search(line):
            run.loaded.append(m.group(1))
        elif m := NOT_LOADED_RE.search(line):
            run.failed.append(m.group(1))
        elif m := WRITTEN_RE.search(line):
            written.add(m.group(1))
        elif not run.run_id and (m := RUN_ID_RE.search(line)):
            run.run_id = m.group(1)
        elif FINALIZE_RE.search(line):
            run.closed = True
    # A loaded genome without its run log row: the writer had not reached it.
    for genome in run.loaded:
        label = m.group(1) if (m := LABEL_RE.search(genome)) else genome
        if label not in written:
            run.lost.setdefault(genome, Lost()).whole = True
    for genome, what in run.lost.items():
        what.restored = restored.get(genome, set())
    return run


def lost_writes(log: str) -> dict[str, Lost]:
    """Returns {genome: its writes to make} from a run's log."""
    return read_run_log(log).lost
