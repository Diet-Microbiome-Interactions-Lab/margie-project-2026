"""
Where each step's results in a run came from, per genome: restored from the MARGIE database,
run fresh, partly each, kept from an earlier attempt in the same run folder, or not run.

The database has two caches. Genome level (output_cache.py): a step's whole output for a
genome, keyed by the genome's sequence hash: GTDB-Tk before gene calling, RASTtk's gene
calls, and each step after gene calling. Protein level (protein_cache.py): one tool's rows
per protein, keyed by the protein's hash and the tool's container, database and settings,
used after gene calling so a tool annotates only proteins it has not seen.

Written to <output_dir>/cache-report.tsv as the run goes (the website shows it with the run),
and summed up in the run's log one line per genome. Never raises: a report that cannot be
written is logged and the run goes on.
"""
import csv
import io
import logging
import os
import re
from pathlib import Path

LOGGER = logging.getLogger(__name__)

FILE = 'cache-report.tsv'
HEADER = ['genome', 'step', 'stage', 'source', 'level', 'database', 'detail', 'cached_at']

RESTORED = 'restored'
FRESH = 'fresh'
PARTLY = 'partly restored'
KEPT = 'kept'
NOT_RUN = 'not run'

# The cache a restored row came from.
GENOME_LEVEL = 'genome'
PROTEIN_LEVEL = 'protein'

UNFINISHED = 'the run stopped before this finished'


def stage_of(step: str) -> str:
    if step == 'quast':
        return 'beside the pipeline'
    if step == 'gtdbtk':
        return 'before gene calling'
    if step in ('rasttk', 'prodigal'):
        return 'gene calling'
    return 'after gene calling'


def proteins(cached: int, to_run: int) -> dict:
    """Returns set()'s source, level and detail for a protein-level tool: how many proteins came from the cache."""
    total = cached + to_run
    if total and not to_run:
        return {'source': RESTORED, 'level': PROTEIN_LEVEL, 'detail': f'all {total:,} proteins from the protein cache'}
    if cached:
        return {'source': PARTLY, 'level': PROTEIN_LEVEL,
                'detail': f'{cached:,} of {total:,} proteins from the protein cache; {to_run:,} annotated now'}
    return {'source': FRESH, 'detail': f'none of its {total:,} proteins in the protein cache; all annotated now'}


# The job log's lines that say where results came from (workflow.py, output_cache.py), for a run
# started before this report was written: grep -E with this, then rows_from_log.
LOG_PATTERN = 'main_database: |Restored from cache: |Protein cache for '
# Folders in a run folder that are not a genome's.
NOT_GENOMES = {'.snakemake', 'original_container_outputs', 'scoring', 'gtdbtk', 'logs'}
_PROTEIN_COUNT = re.compile(r'([\w.-]+) (\d+)/(\d+) cached')


def rows_from_log(lines, output_dir: str) -> list[dict]:
    """Rebuilds a run's report from its job log: the database it used, each step restored from the
    genome-level cache ("Restored from cache: <run>/<genome>/<step>/..."), and each tool's share of
    proteins from the protein-level cache ("Protein cache for <genome>: <tool> <cached>/<all> cached").
    Steps the log does not mention are left out; a finished one of those ran in the job."""
    report = CacheReport('')
    root = output_dir.rstrip('/') + '/'
    for line in lines:
        if 'main_database: ' in line:
            if not report.database:
                report.database = line.split('main_database: ', 1)[1].strip().strip("'\",")
        elif 'Restored from cache: ' in line:
            path = line.split('Restored from cache: ', 1)[1].strip()
            parts = path[len(root):].split('/') if path.startswith(root) else []
            if len(parts) >= 3 and parts[0] not in NOT_GENOMES:
                report.set(parts[0], parts[1], RESTORED, level=GENOME_LEVEL)
        elif 'Protein cache for ' in line:
            genome, _, counts = line.split('Protein cache for ', 1)[1].partition(': ')
            for tool, cached, total in _PROTEIN_COUNT.findall(counts):
                row = report.rows.get((genome.strip(), tool))
                if row and row['source'] == RESTORED:
                    continue
                c, n = int(cached), int(total)
                report.set(genome.strip(), tool, **proteins(c, n - c))
    return list(report.rows.values())


class CacheReport:
    """One row per genome and step; set() replaces a step's row, write() puts them all on disk."""

    def __init__(self, output_dir: str, database: str = ''):
        self.path = os.path.join(output_dir, FILE) if output_dir else ''
        # The MARGIE database the run reads its caches from (and adds to).
        self.database = database or ''
        self.rows: dict[tuple[str, str], dict[str, str]] = {}

    def set(self, genome: str, step: str, source: str, detail: str = '', cached_at: str = '', level: str = '') -> None:
        """level: GENOME_LEVEL or PROTEIN_LEVEL for a row restored (wholly or partly) from a cache."""
        self.rows[(genome, step)] = {
            'genome': genome, 'step': step, 'stage': stage_of(step), 'source': source, 'level': level,
            'database': self.database if level else '', 'detail': detail, 'cached_at': cached_at or ''}

    def unfinished(self, genome: str) -> None:
        """Marks the genome's fresh and partly restored steps as cut short."""
        for (g, _), row in self.rows.items():
            if g == genome and row['source'] in (FRESH, PARTLY) and UNFINISHED not in row['detail']:
                row['detail'] = f"{row['detail']}; {UNFINISHED}" if row['detail'] else UNFINISHED

    def summary(self, genome: str) -> str:
        """One line on the genome: which steps were restored, run fresh, partly restored or kept."""
        by: dict[tuple[str, str], list[str]] = {}
        for (g, step), row in self.rows.items():
            if g == genome and row['source'] != NOT_RUN:
                by.setdefault((row['source'], row['level']), []).append(step)
        order = [(RESTORED, GENOME_LEVEL, 'restored, genome level'), (RESTORED, PROTEIN_LEVEL, 'restored, protein level'),
                 (PARTLY, PROTEIN_LEVEL, 'partly restored, protein level'), (FRESH, '', 'run fresh'),
                 (KEPT, '', 'kept from an earlier attempt')]
        parts = [f"{words}: {', '.join(by[(s, lv)])}" for s, lv, words in order if by.get((s, lv))]
        where = f' (cache: {self.database})' if any(r['level'] for (g, _), r in self.rows.items() if g == genome) else ''
        return f"Fresh or restored, {genome}: {'; '.join(parts) or 'nothing ran'}{where}"

    def text(self) -> str:
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=HEADER, delimiter='\t', lineterminator='\n')
        w.writeheader()
        for row in self.rows.values():
            w.writerow({k: str(v).replace('\t', ' ').replace('\n', ' ') for k, v in row.items()})
        return out.getvalue()

    def write(self) -> None:
        if not self.path:
            return
        try:
            tmp = Path(f'{self.path}.tmp')
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(self.text())
            os.replace(tmp, self.path)
        except OSError as exc:
            LOGGER.warning('Could not write the cache report %s: %s', self.path, exc)
