/**
 * Who makes MARGIE, how to cite it and where the desktop app is: one copy, for the
 * Contributors, Acknowledgements, README and Home pages.
 */

export const LAB = {
	name: 'Diet-Microbiome Interactions Lab',
	pi: 'Stephen R Lindemann',
	email: 'lindems@purdue.edu'
};

export const PEOPLE = [
	{ name: 'Sajal Bhattarai', role: '' },
	{ name: 'Dane Deemer', role: 'Developed the Bioinformatics Supercomputing Platform (BSP), which houses MARGIE' },
	{ name: 'Stephen R Lindemann', role: 'Principal investigator' }
];

/** The repository to cite, which holds the backend and the interface. */
export const CITE_URL = 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026';

/** APA 7th, as the repository's README gives it. */
export const CITATION =
	'Bhattarai, S., Deemer, D., & Lindemann, S. R. (2026). MARGIE: Mostly Automated Rapid Genome Inference Environment [Computer software]. Purdue University. ' +
	CITE_URL;

/** Where the desktop app is downloaded from (its releases, for now). */
export const DESKTOP_URL = `${CITE_URL}/releases`;

/** Citations for what MARGIE runs that the licence catalog does not carry (or carries only as a note). */
export const EXTRA_REFERENCES: { phase: number; what: string; text: string }[] = [
	{ phase: 0, what: 'Snakemake', text: 'Mölder F, et al. (2021) Sustainable data analysis with Snakemake. F1000Research 10:33.' },
	{ phase: 3, what: 'Prodigal', text: 'Hyatt D, et al. (2010) Prodigal: prokaryotic gene recognition and translation initiation site identification. BMC Bioinformatics 11:119.' },
	{
		phase: 5,
		what: 'UniOP',
		text: 'Su H, Zhang R, Söding J (2024) UniOP: a universal operon prediction for high-throughput prokaryotic (meta-)genomic data using intergenic distance. bioRxiv, doi:10.1101/2024.11.11.623000.'
	}
];
