/**
 * Genus and species names in the quiz's text, set in italics (Sci.svelte): a listed genus, with its
 * epithet when one follows ("Escherichia coli"), and the short form ("E. coli"). Higher ranks
 * (Bacillota, Bacteroidota) and words such as "strain" or "sp." stay upright.
 * scripts/check-quiz.mjs lists capitalised words that look like a genus and are missing here.
 */

export const GENERA = [
	'Acetobacterium', 'Akkermansia', 'Aliivibrio', 'Anaerobutyricum', 'Anaerostipes', 'Azotobacter',
	'Bacillus', 'Bacteroides', 'Bifidobacterium', 'Bilophila', 'Cellulomonas', 'Chlorobium',
	'Clostridium', 'Deinococcus', 'Desulfovibrio', 'Enterobacter', 'Escherichia', 'Eubacterium',
	'Faecalibacterium', 'Halobacterium', 'Klebsiella', 'Lactobacillus', 'Lactococcus', 'Leuconostoc',
	'Methanobrevibacter', 'Methanocaldococcus', 'Methanosaeta', 'Methanosarcina', 'Methanosphaera',
	'Methanothermobacter', 'Methanothrix', 'Methylococcus', 'Methylosinus', 'Mycobacterium',
	'Mycoplasma', 'Nitrobacter', 'Nitrosomonas', 'Nitrospira', 'Paracoccus', 'Prevotella',
	'Propionibacterium', 'Pseudomonas', 'Roseburia', 'Ruminococcus', 'Spiroplasma', 'Staphylococcus',
	'Vibrio'
];

export const EPITHETS = [
	'aerogenes', 'aureus', 'bromii', 'cholerae', 'coli', 'fimi', 'fischeri', 'freudenreichii', 'hallii',
	'jannaschii', 'lactis', 'megaterium', 'mesenteroides', 'muciniphila', 'piger', 'prausnitzii',
	'radiodurans', 'rectale', 'salinarum', 'smithii', 'subtilis', 'thetaiotaomicron', 'tuberculosis',
	'vinelandii', 'woodii'
];

const EP = EPITHETS.join('|');
const NAME = new RegExp(`\\b(?:(?:${GENERA.join('|')})(?:\\s+(?:${EP}))?|[A-Z]\\.\\s?(?:${EP}))\\b`, 'g');

/** `text` cut into runs, with the names marked. */
export function nameRuns(text: string): { text: string; name: boolean }[] {
	const runs: { text: string; name: boolean }[] = [];
	let at = 0;
	for (const m of text.matchAll(NAME)) {
		if (m.index > at) runs.push({ text: text.slice(at, m.index), name: false });
		runs.push({ text: m[0], name: true });
		at = m.index + m[0].length;
	}
	if (at < text.length) runs.push({ text: text.slice(at), name: false });
	return runs;
}
