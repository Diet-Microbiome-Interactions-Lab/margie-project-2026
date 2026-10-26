/** Every genome Atlas knows of, from the input folder, the results and the run going on. */

import { ws, type Genome, type OrganismResult } from '$lib/workspace/data.svelte';

export type GenomeState = 'done' | 'running' | 'partial' | 'pending';

export interface AtlasGenome {
	name: string;
	state: GenomeState;
	/** The FASTA file in the input folder, when it is still there. */
	file?: Genome;
	result?: OrganismResult;
}

const STATE_ORDER: Record<GenomeState, number> = { running: 0, done: 1, partial: 2, pending: 3 };
export const stemOf = (file: string) => file.replace(/\.(fna|fa|fasta)$/i, '');
/** A run names each genome <file name>--<the first 8 characters of its hash> (coli--a1b2c3d4); its file's name without them. */
export const baseOf = (name: string) => name.replace(/--[0-9a-f]{8}$/, '');
/** The genome hash a run's name carries (the first 8 characters, assigned by MARGIE from the genome's DNA); '' without one. */
export const hashOf = (name: string) => name.match(/--([0-9a-f]{8})$/)?.[1] ?? '';
/** What the genome hash is, where it is shown. */
export const HASH_NOTE = "Genome hash: assigned by MARGIE from the genome's DNA. Tables and result files name the genome <name>--<hash>, so genomes that share a file name stay apart.";

/** An annotate run is going but its log has not been read yet, so which genome it is on is not known. */
export const settling = () => ws.active?.kind === 'annotate' && !ws.log;

export function genomeList(): AtlasGenome[] {
	const byName = new Map<string, AtlasGenome>();
	for (const f of ws.genomes) byName.set(stemOf(f.name), { name: stemOf(f.name), state: 'pending', file: f });
	for (const r of ws.results) {
		// A result named <file>--<hash> belongs to its file in the folder, unless that file has one already.
		const own = byName.get(baseOf(r.organism));
		const key = byName.has(r.organism) ? r.organism : own?.file && !own.result ? baseOf(r.organism) : r.organism;
		const g = byName.get(key) ?? { name: r.organism, state: 'pending' };
		g.name = r.organism;
		g.result = r;
		g.state = r.final?.table ? 'done' : 'partial';
		byName.set(key, g);
	}
	// The run going on: the genome it is on, and those still queued in it
	// (unless an earlier run already finished them).
	for (const p of ws.progress?.genomes ?? []) {
		if (p.state === 'done') continue;
		const key = byName.has(p.name) ? p.name : byName.has(baseOf(p.name)) ? baseOf(p.name) : p.name;
		const g = byName.get(key) ?? { name: p.name, state: 'pending' };
		g.name = p.name;
		if (p.state === 'running') g.state = 'running';
		else if (g.state !== 'done') g.state = 'pending';
		byName.set(key, g);
	}
	return [...byName.values()].sort((a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state] || a.name.localeCompare(b.name));
}

export const STATE_WORDS: Record<GenomeState, string> = {
	done: 'annotated',
	running: 'annotating now',
	partial: 'not finished',
	pending: 'waiting'
};
