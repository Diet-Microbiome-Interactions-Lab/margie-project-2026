"""
The writes to the MARGIE database that a run's log says were lost (workflow.py's warnings), genome
by genome. `margie sb` with margie_sb.rewrite_from: <that log> writes them again from the run's
folder instead of running (workflow.py, _rewrite_lost_writes); each write reads what the database
holds first, so one made since is not made twice.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class Lost:
    """A genome's lost writes: the tools whose proteins and whose results go to the cache again, or
    all its results (every), and its genes' fingerprints and proteins' records."""
    proteins: set[str] = field(default_factory=set)
    results: set[str] = field(default_factory=set)
    every: bool = False
    records: bool = False
    # The results that came back from the cache in that run: they stay as they are.
    restored: set[str] = field(default_factory=set)


PROTEINS_RE = re.compile(r'Protein cache store failed for (\S+) / (\S+?):')
RESULTS_RE = re.compile(r'Caching (\S+) for (\S+) failed \(the run goes on without it\)')
EVERY_RE = re.compile(r'Caching the rest of (\S+) failed \(the run goes on without it\)')
RESTORED_RE = re.compile(r'Phase4\+ cache restore for (\S+): (\{[^}]*\})')
RECORDS_RE = re.compile(r'Recording the (?:proteins|fingerprints) of (\S+) failed \(the run goes on without it\)')
# Stage 1's batches are cached by their own steps, not by genome tool.
BATCHES = {'GTDB-Tk', 'RASTtk'}


def lost_writes(log: str) -> dict[str, Lost]:
    """Returns {genome: its lost writes} from a run's log."""
    lost: dict[str, Lost] = {}
    restored: dict[str, set[str]] = {}
    for line in log.splitlines():
        if m := RESTORED_RE.search(line):
            restored[m.group(1)] = {t for t, hit in ast.literal_eval(m.group(2)).items() if hit}
        elif m := PROTEINS_RE.search(line):
            lost.setdefault(m.group(1), Lost()).proteins.add(m.group(2))
        elif m := EVERY_RE.search(line):
            lost.setdefault(m.group(1), Lost()).every = True
        elif (m := RESULTS_RE.search(line)) and m.group(1) not in BATCHES:
            lost.setdefault(m.group(2), Lost()).results.add(m.group(1))
        elif m := RECORDS_RE.search(line):
            lost.setdefault(m.group(1), Lost()).records = True
    for genome, what in lost.items():
        what.restored = restored.get(genome, set())
    return lost
