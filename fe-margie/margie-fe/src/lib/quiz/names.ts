/**
 * Genus and species names in the quiz's text, set in italics (Sci.svelte): a listed genus, with its
 * epithet when one follows ("Escherichia coli"), and the short form ("E. coli"). Higher ranks
 * (Bacillota, Bacteroidota) and words such as "strain" or "sp." stay upright.
 * scripts/check-quiz.mjs lists capitalised words that look like a genus and are missing here.
 */

export const GENERA = [
	'Acetobacterium', 'Acidithiobacillus', 'Akkermansia', 'Aliivibrio', 'Anabaena', 'Anaerobutyricum',
	'Anaerostipes', 'Azotobacter', 'Bacillus', 'Bacteroides', 'Beggiatoa', 'Bifidobacterium', 'Bilophila',
	'Cellulomonas', 'Chlorobium', 'Clostridium', 'Cupriavidus', 'Deinococcus', 'Desulfovibrio',
	'Enterobacter', 'Enterococcus', 'Escherichia', 'Eubacterium', 'Faecalibacterium', 'Geobacter',
	'Halobacterium', 'Klebsiella', 'Lactobacillus', 'Lactococcus', 'Leptospirillum', 'Leuconostoc',
	'Methanobrevibacter', 'Methanocaldococcus', 'Methanosaeta', 'Methanosarcina', 'Methanosphaera',
	'Methanothermobacter', 'Methanothrix', 'Methylococcus', 'Methylosinus', 'Mycobacterium', 'Mycoplasma',
	'Myxococcus', 'Nitrobacter', 'Nitrosomonas', 'Nitrospira', 'Oxalobacter', 'Paracoccus', 'Prevotella',
	'Propionibacterium', 'Propionigenium', 'Pseudomonas', 'Roseburia', 'Ruminococcus', 'Shewanella',
	'Spiroplasma', 'Staphylococcus', 'Streptococcus', 'Streptomyces', 'Sulfolobus', 'Thermoanaerobacter',
	'Vibrio', 'Zymomonas'
];

export const EPITHETS = [
	'acidocaldarius', 'aerogenes', 'aeruginosa', 'alginolyticus', 'aureus', 'bromii', 'cholerae', 'coli',
	'denitrificans', 'faecalis', 'ferrooxidans', 'fimi', 'fischeri', 'formigenes', 'freudenreichii',
	'hallii', 'hirae', 'jannaschii', 'kivui', 'lactis', 'megaterium', 'mesenteroides', 'mobilis',
	'modestum', 'muciniphila', 'necator', 'oneidensis', 'piger', 'prausnitzii', 'pseudofirmus',
	'radiodurans', 'rectale', 'salinarum', 'smithii', 'subtilis', 'sulfurreducens', 'thetaiotaomicron',
	'tuberculosis', 'vinelandii', 'wadsworthia', 'woodii', 'xanthus'
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
