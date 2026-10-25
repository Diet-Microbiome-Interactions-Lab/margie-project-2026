/**
 * Every citation that goes with MARGIE's, as one BibTeX file: MARGIE, the thesis, the base
 * architecture, the research computing (RCAC), the tools and databases a run uses and the software
 * MARGIE is built on. Entries come from each paper's DOI (credits.ts) or from the issuer (about.ts);
 * a paper cited by two tools appears once.
 */

import { NOT_YET } from '$lib/license';
import { BASE_BIBTEX, CITE_URL, COMPUTING, THESIS_BIBTEX, THESIS_DOI } from './about';
import { SOFTWARE_CREDITS, TOOLS, type Cite } from './credits';

/** MARGIE herself, as the repository's CITATION.cff gives her. */
export const MARGIE_BIBTEX = `@software{Bhattarai2026MARGIE,
author = "Sajal Bhattarai and Dane Deemer and Stephen R. Lindemann",
title = "{MARGIE: Mostly Automated Rapid Genome Inference Environment}",
year = "2026",
publisher = "Purdue University",
url = "${CITE_URL}"
}`;

/** The tools a run uses (steps being worked on are left out), in run order. */
export const RUN_TOOLS = TOOLS.filter((t) => !NOT_YET.has(t.id)).sort((a, b) => a.phase - b.phase || a.name.localeCompare(b.name));

/** The software whose authors ask to be cited (Snakemake, Apptainer). */
export const CITED_SOFTWARE = SOFTWARE_CREDITS.filter((s) => s.cite.length);

/** The tools' and software's papers, each once (by DOI, else by its key). */
export function citedPapers(): Cite[] {
	// The thesis has its own entry (THESIS_BIBTEX); a tool citing it does not add a second.
	const seen = new Set<string>([THESIS_DOI.replace('https://doi.org/', '').toLowerCase()]);
	const out: Cite[] = [];
	for (const c of [...RUN_TOOLS.flatMap((t) => t.cite), ...CITED_SOFTWARE.flatMap((s) => s.cite)]) {
		const id = (c.doi || c.key).toLowerCase();
		if (seen.has(id)) continue;
		seen.add(id);
		out.push(c);
	}
	return out;
}

/** The whole file. */
export function allBibtex(): string {
	const parts = [
		'% MARGIE, the thesis in which she was first built, and the base architecture she was built on',
		MARGIE_BIBTEX,
		THESIS_BIBTEX,
		BASE_BIBTEX,
		'% The research computing she runs on, as RCAC asks it to be cited',
		COMPUTING.bibtex,
		'% The tools, databases and software she runs, as each asks to be cited',
		...citedPapers().map((c) => c.bibtex)
	];
	return parts.join('\n\n') + '\n';
}

/** Saves the file as margie-citations.bib. */
export function downloadBibtex() {
	const url = URL.createObjectURL(new Blob([allBibtex()], { type: 'application/x-bibtex' }));
	const a = Object.assign(document.createElement('a'), { href: url, download: 'margie-citations.bib' });
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
