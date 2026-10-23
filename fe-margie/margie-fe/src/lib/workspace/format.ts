/** Small formatting helpers shared by the workspace's panels and pages. */

import type { Run } from '$lib/api';

/** Formats a time as "just now", "5 min ago", "3 h ago" or "2 d ago". */
export function ago(iso: string | undefined, now = Date.now()): string {
	if (!iso) return '';
	const s = (now - new Date(iso).getTime()) / 1000;
	if (!Number.isFinite(s)) return '';
	if (s < 60) return 'just now';
	if (s < 3600) return `${Math.floor(s / 60)} min ago`;
	if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
	return `${Math.floor(s / 86400)} d ago`;
}

/**
 * Returns how long a run took, or has taken so far by `now` (a clock that ticks keeps it live);
 * a run still going counts its seconds at every length, so the count is seen to move.
 */
export function duration(run: Pick<Run, 'started' | 'finished'>, now = Date.now()): string {
	const s = Math.floor(Math.max(0, ((run.finished ? new Date(run.finished).getTime() : now) - new Date(run.started).getTime()) / 1000));
	if (s < 60) return `${s} s`;
	if (s < 3600) return `${Math.floor(s / 60)} min ${s % 60} s`;
	const hm = `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
	return run.finished ? hm : `${hm} ${s % 60} s`;
}

/** Turns a figure file name into a title: "fig03_operon_context_by_size.png" -> "Operon context by size". */
export function figureTitle(file: string): string {
	const base = (file.split('/').pop() ?? file).replace(/\.png$/i, '');
	if (/_circular$/.test(base)) return 'Circular map';
	const words = base.replace(/^fig\d+_/, '').replace(/_/g, ' ').replace(/\bc3\b/i, 'C3');
	return words.charAt(0).toUpperCase() + words.slice(1);
}

export const count = (n: number) => n.toLocaleString('en-US');
