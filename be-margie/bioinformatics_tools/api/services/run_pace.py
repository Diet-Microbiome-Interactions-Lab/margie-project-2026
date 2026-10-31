"""
The pace of a running annotation, read from its log (workflow.py's lines): how far apart its
genomes start Stage 2, which genome MARGIE is writing to the database's cache, how many genomes
are not written yet and how long one takes, and the run's closing step. The Jobs page adds these
to the time its steps still need.
"""
from __future__ import annotations

import re
from statistics import mean

STAMP_RE = re.compile(r'^\[(\d\d):(\d\d):(\d\d)')
START_RE = re.compile(r'=== STAGE 2: genome (\d+)/(\d+) ')
# The protein cache's split: "cog 0/3347 cached, ..." names a genome with proteins to annotate.
SPLIT_RE = re.compile(r'Protein cache for (\S+): (.*)')
CACHED_RE = re.compile(r'(\d+)/(\d+) cached')
# A genome's compute has ended: its results wait to load or are loading.
COMPUTED_RE = re.compile(r'=== LOADS: (\S+) (?:waiting|loading)')
# The run's database writer at work on a genome.
WRITER_RE = re.compile(r'Protein cache: \d+ new protein\(s\) of (\S+) kept for '
                       r'|Protein cache store failed for (\S+) / '
                       r'|Cached \S+ for (\S+) as soon as '
                       r'|Caching \S+ for (\S+) failed '
                       r'|Recording the proteins of (\S+) failed ')
# The writer's last write for a genome, its run log, names the genome by its hash.
WRITTEN_RE = re.compile(r'Logged workflow run: .*\(hash (fa1:[0-9a-f]+)')
DRAIN_RE = re.compile(r'Waiting for \d+ write\(s\) to the MARGIE database to finish')
CLOSING_RE = re.compile(r'=== (FINALIZE: .+?|Stage 3: .+?) ===')
LABEL_RE = re.compile(r'--(fa1:[0-9a-f]+)$')
# The last few genomes set the pace.
RECENT = 5


def _label(genome: str) -> str:
    m = LABEL_RE.search(genome)
    return m.group(1) if m else genome


class RunPace:
    """Follows a run's log line by line; snapshot() gives what the Jobs page shows."""

    def __init__(self) -> None:
        self._day = 0
        self._last: float | None = None
        self._starts: list[float] = []
        self._started = 0
        self._total = 0
        self._new: set[str] = set()
        self._computed: dict[str, float] = {}
        self._written: set[str] = set()
        self._written_at: float | None = None
        self._durations: list[float] = []
        self._writing = ''
        self._draining = False
        self._closing = ''

    def _seconds(self, line: str) -> float | None:
        m = STAMP_RE.match(line)
        if not m:
            return None
        h, mi, s = (int(x) for x in m.groups())
        t = h * 3600 + mi * 60 + s + self._day * 86400
        # The log's clock has no date: a step back of over 12 hours is the next day.
        if self._last is not None and t < self._last - 43200:
            self._day += 1
            t += 86400
        self._last = t
        return t

    def feed(self, line: str) -> bool:
        """Reads one log line; returns whether the snapshot changed."""
        t = self._seconds(line)
        if t is None:
            return False
        if m := START_RE.search(line):
            self._started, self._total = int(m.group(1)), int(m.group(2))
            self._starts.append(t)
            return True
        if m := SPLIT_RE.search(line):
            if any(int(a) < int(b) for a, b in CACHED_RE.findall(m.group(2))):
                self._new.add(m.group(1))
            return False
        if m := COMPUTED_RE.search(line):
            self._computed.setdefault(m.group(1), t)
            return True
        if m := WRITER_RE.search(line):
            genome = next(g for g in m.groups() if g)
            if _label(genome) not in self._written and genome != self._writing:
                self._writing = genome
                return True
            return False
        if m := WRITTEN_RE.search(line):
            label = m.group(1)
            self._written.add(label)
            genome = next((g for g in self._computed if _label(g) == label), '')
            if genome in self._new:
                began = max(self._computed[genome], self._written_at or 0)
                self._durations.append(t - began)
            if _label(self._writing) == label:
                self._writing = ''
            self._written_at = t
            return True
        if DRAIN_RE.search(line):
            self._draining = True
            return True
        if m := CLOSING_RE.search(line):
            self._closing = m.group(1)
            self._writing = ''
            return True
        return False

    def snapshot(self) -> dict:
        waiting = [g for g in self._computed if _label(g) not in self._written and g != self._writing]
        new_left = sum(g in self._new for g in waiting) + (0.5 if self._writing in self._new else 0)
        per = mean(self._durations[-RECENT:]) if self._durations else None
        gaps = [b - a for a, b in zip(self._starts, self._starts[1:])][-RECENT:]
        gap = mean(gaps) if gaps else None
        return {
            'writing': self._writing,
            'writes_waiting': len(waiting),
            'write_genome_s': round(per) if per is not None else None,
            'writes_left_s': round(per * new_left) if per is not None else None,
            'start_gap_s': round(gap) if gap is not None else None,
            'starts_left_s': round(gap * (self._total - self._started)) if gap is not None and self._total else None,
            'draining': self._draining,
            'closing': self._closing,
        }
