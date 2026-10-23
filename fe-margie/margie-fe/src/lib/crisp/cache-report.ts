/**
 * A run's cache report (<run folder>/cache-report.tsv, written by the workflow's
 * cache_report.py): for each genome and step, whether its results were restored from the
 * MARGIE database, run fresh, partly each, kept from an earlier attempt, or not run; and for
 * a restored one, which cache (genome level: the whole output of a run on the same genome
 * sequence; protein level: rows for proteins seen before), at what stage, from which database
 * and when it was cached. Read by the Jobs page and the progress grids.
 */

import { api } from '$lib/api';

export type Source = 'restored' | 'fresh' | 'partly restored' | 'kept' | 'not run';

export interface SourceRow {
	genome: string;
	step: string;
	stage: string;
	source: Source;
	level: '' | 'genome' | 'protein';
	database: string;
	detail: string;
	cached_at: string;
}

export const REPORT_FILE = 'cache-report.tsv';

export function parseCacheReport(text: string): SourceRow[] {
	const [head, ...lines] = text.split('\n').filter((l) => l.trim());
	if (!head) return [];
	const keys = head.split('\t');
	return lines.map((l) => {
		const cells = l.split('\t');
		return Object.fromEntries(keys.map((k, i) => [k, cells[i] ?? ''])) as unknown as SourceRow;
	});
}

/** A run's report, or null when it has none (a run from before reports, or one not started). */
export async function readCacheReport(dir: string): Promise<SourceRow[] | null> {
	if (!dir) return null;
	try {
		const d = await api<{ content: string; binary: boolean }>(`/files/text?path=${encodeURIComponent(`${dir.replace(/\/$/, '')}/${REPORT_FILE}`)}`);
		return d.binary ? null : parseCacheReport(d.content);
	} catch {
		return null;
	}
}

/** The progress grid's column for a step (both gene callers share one). */
export const columnOf = (step: string) => (step === 'rasttk' || step === 'prodigal' ? 'genes' : step);

/** "1 Sep 2026" from an ISO time; '' when none. */
export function cachedOn(iso: string): string {
	const t = Date.parse(iso);
	return Number.isNaN(t) ? '' : new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

const LEVEL: Record<string, string> = { genome: 'genome-level cache', protein: 'protein-level cache' };

/** One line on where a step's results came from, for a tooltip or a popup. */
export function sourceSay(r: SourceRow): string {
	const when = cachedOn(r.cached_at);
	switch (r.source) {
		case 'restored':
			return `restored from the database (${LEVEL[r.level] ?? 'cache'}${when ? `, cached ${when}` : ''})${r.detail ? `: ${r.detail}` : ''}`;
		case 'partly restored':
			return `partly restored (${LEVEL[r.level] ?? 'cache'}): ${r.detail}`;
		case 'kept':
			return `kept: ${r.detail}`;
		case 'not run':
			return `not run${r.detail ? `: ${r.detail}` : ''}`;
		default:
			return `run fresh${r.detail ? `: ${r.detail}` : ''}`;
	}
}

/** Per genome: how many steps came from each source, for a one-line summary. */
export function countsByGenome(rows: SourceRow[]) {
	const by = new Map<string, { restoredGenome: number; restoredProtein: number; partly: number; fresh: number; kept: number }>();
	for (const r of rows) {
		if (r.source === 'not run') continue;
		const c = by.get(r.genome) ?? { restoredGenome: 0, restoredProtein: 0, partly: 0, fresh: 0, kept: 0 };
		if (r.source === 'restored') c[r.level === 'protein' ? 'restoredProtein' : 'restoredGenome']++;
		else if (r.source === 'partly restored') c.partly++;
		else if (r.source === 'kept') c.kept++;
		else c.fresh++;
		by.set(r.genome, c);
	}
	return by;
}
