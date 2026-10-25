/**
 * Saving a genome's figures from Results: one figure, or each of them in a zip with an index
 * (index.tsv: number, title, file, source). Files are named by the figure's number, as the list
 * shows it, so a figure keeps its place once saved: <genome>_figure-03_<title>.png.
 */

import { zipSync } from 'fflate';
import { fileUrl } from '$lib/api';
import { fileBlob } from '$lib/cluster/backend';
import { backend } from '$lib/workspace/backend.svelte';
import { figureTitle } from '$lib/workspace/format';

const slug = (s: string) => s.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** The saved name of figure `file`, numbered by its place in `files`. */
export const figureName = (genome: string, files: string[], file: string) =>
	`${slug(genome)}_figure-${String(files.indexOf(file) + 1).padStart(2, '0')}_${slug(figureTitle(file))}.png`;

async function blobOf(path: string): Promise<Blob> {
	if (backend.cluster) return fileBlob(path, true);
	const r = await fetch(fileUrl(path));
	if (!r.ok) throw new Error(`${path.split('/').pop()} could not be read (${r.status}).`);
	return r.blob();
}

function save(blob: Blob, name: string) {
	const url = URL.createObjectURL(blob);
	const a = Object.assign(document.createElement('a'), { href: url, download: name });
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Saves one figure under its numbered name. */
export async function downloadFigure(genome: string, files: string[], file: string) {
	save(await blobOf(file), figureName(genome, files, file));
}

/** Saves each figure, numbered, with index.tsv, as <genome>_figures.zip; onEach reports progress. */
export async function downloadFigures(genome: string, files: string[], onEach?: (done: number, total: number) => void) {
	const dir = `${slug(genome)}_figures`;
	const entries: Record<string, Uint8Array> = {};
	const rows = ['figure\ttitle\tfile\tsource'];
	for (const [i, f] of files.entries()) {
		const name = figureName(genome, files, f);
		entries[`${dir}/${name}`] = new Uint8Array(await (await blobOf(f)).arrayBuffer());
		rows.push([i + 1, figureTitle(f), name, f].join('\t'));
		onEach?.(i + 1, files.length);
	}
	entries[`${dir}/index.tsv`] = new TextEncoder().encode(rows.join('\n') + '\n');
	// PNGs are compressed already, so the zip stores them as they are.
	save(new Blob([new Uint8Array(zipSync(entries, { level: 0 }))], { type: 'application/zip' }), `${dir}.zip`);
}
