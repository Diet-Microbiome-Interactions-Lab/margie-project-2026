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

/** The open-source software MARGIE itself is built with (be-margie/pyproject.toml, fe-margie/margie-fe/package.json). */
export const SOFTWARE: { group: string; items: { name: string; what: string; href: string }[] }[] = [
	{
		group: 'Workflow and computing',
		items: [
			{ name: 'Snakemake', what: 'the workflow engine, with its SLURM executor plugin', href: 'https://snakemake.github.io' },
			{ name: 'Apptainer', what: 'runs every tool in its own container', href: 'https://apptainer.org' },
			{ name: 'Slurm', what: 'schedules the jobs on the cluster', href: 'https://slurm.schedmd.com' },
			{ name: 'Python', what: 'the pipeline, the scoring and the server', href: 'https://www.python.org' },
			{ name: 'uv', what: 'installs the Python environment', href: 'https://docs.astral.sh/uv/' }
		]
	},
	{
		group: 'Science',
		items: [
			{ name: 'Biopython', what: 'sequence files', href: 'https://biopython.org' },
			{ name: 'NumPy', what: 'numbers', href: 'https://numpy.org' },
			{ name: 'pandas', what: 'the tables', href: 'https://pandas.pydata.org' },
			{ name: 'SciPy', what: 'statistics', href: 'https://scipy.org' },
			{ name: 'Matplotlib', what: 'the figures', href: 'https://matplotlib.org' },
			{ name: 'openpyxl', what: 'the Excel workbooks', href: 'https://openpyxl.readthedocs.io' }
		]
	},
	{
		group: 'Server',
		items: [
			{ name: 'FastAPI', what: 'the web API', href: 'https://fastapi.tiangolo.com' },
			{ name: 'Uvicorn', what: 'serves it', href: 'https://www.uvicorn.org' },
			{ name: 'Pydantic', what: 'checks what comes in', href: 'https://docs.pydantic.dev' },
			{ name: 'Paramiko', what: 'SSH to your cluster account', href: 'https://www.paramiko.org' },
			{ name: 'PyJWT, bcrypt and cryptography', what: 'sign-in and stored keys', href: 'https://cryptography.io' },
			{ name: 'Typer', what: 'the command line', href: 'https://typer.tiangolo.com' },
			{ name: 'PyYAML', what: 'the config files', href: 'https://pyyaml.org' },
			{ name: 'websockets', what: 'the Terminal', href: 'https://websockets.readthedocs.io' }
		]
	},
	{
		group: 'Website',
		items: [
			{ name: 'Svelte and SvelteKit', what: 'the pages', href: 'https://svelte.dev' },
			{ name: 'TypeScript', what: 'the code behind them', href: 'https://www.typescriptlang.org' },
			{ name: 'Vite', what: 'builds them', href: 'https://vite.dev' },
			{ name: 'Tailwind CSS', what: 'styles', href: 'https://tailwindcss.com' },
			{ name: 'Skeleton', what: 'the interface parts and themes', href: 'https://www.skeleton.dev' },
			{ name: 'Flowbite Svelte', what: 'more interface parts', href: 'https://flowbite-svelte.com' },
			{ name: 'Lucide', what: 'the icons', href: 'https://lucide.dev' },
			{ name: 'xterm.js', what: 'the Terminal', href: 'https://xtermjs.org' },
			{ name: 'marked and DOMPurify', what: 'Markdown, safely', href: 'https://marked.js.org' },
			{ name: 'ExcelJS', what: 'workbooks in the browser', href: 'https://github.com/exceljs/exceljs' },
			{ name: 'Anthropic SDK', what: 'the chat with a genome (Claude)', href: 'https://docs.anthropic.com' },
			{ name: 'Fontsource', what: 'Bricolage Grotesque and IBM Plex', href: 'https://fontsource.org' }
		]
	},
	{
		group: 'Documentation',
		items: [
			{ name: 'MkDocs and Material for MkDocs', what: 'the documentation', href: 'https://squidfunk.github.io/mkdocs-material/' },
			{ name: 'Read the Docs', what: 'hosts it', href: 'https://readthedocs.org' }
		]
	}
];
