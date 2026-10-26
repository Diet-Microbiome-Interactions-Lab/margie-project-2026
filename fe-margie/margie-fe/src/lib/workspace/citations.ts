/**
 * Citations for the tools a genome's results came from (the methods paragraph on Results): each
 * tool's papers as its own pages ask (credits.ts), and MARGIE's and the thesis's as on Contributors.
 */

import { CITATION, THESIS_CITATION } from '$lib/crisp/about';
import { TOOLS } from '$lib/crisp/credits';

export const MARGIE_CITATION = CITATION;
/** The thesis in which MARGIE was first built. */
export const MARGIE_THESIS_CITATION = THESIS_CITATION;

/** The names the methods paragraph uses, by tool id. */
const NAMES: Record<string, string> = {
	prodigal: 'Prodigal',
	operon: 'UniOP',
	gtdbtk: 'GTDB-Tk',
	rasttk: 'RASTtk',
	psortb: 'PSORTb',
	deepsig: 'DeepSig',
	tmbed: 'TMbed',
	phobius: 'Phobius',
	dbcan: 'dbCAN',
	eggnog: 'eggNOG-mapper',
	interpro: 'InterProScan',
	pfam: 'Pfam',
	tigrfam: 'TIGRFAMs',
	merops: 'MEROPS',
	tcdb: 'TCDB',
	cog: 'COG',
	uniprot: 'UniProt',
	geneprop: 'Genome Properties',
	kegg: 'KEGG',
	pgap: 'PGAP',
	signalp6: 'SignalP 6',
	quast: 'QUAST'
};

const papers = TOOLS.flatMap((t) => t.cite);
const PRODIGAL = papers.find((c) => c.key.startsWith('hyatt2010'));

/** Each tool's name and its papers (APA), as one reference. */
export const CITATIONS: Record<string, { name: string; cite: string }> = Object.fromEntries(
	Object.entries(NAMES).flatMap(([id, name]) => {
		// Prodigal is cited on its own; UniOP's entry keeps only UniOP's paper.
		const cite = id === 'prodigal' ? (PRODIGAL ? [PRODIGAL] : []) : (TOOLS.find((t) => t.id === id)?.cite ?? []).filter((c) => id !== 'operon' || !c.key.startsWith('hyatt2010'));
		return cite.length ? [[id, { name, cite: cite.map((c) => c.apa).join(' ') }]] : [];
	})
);
