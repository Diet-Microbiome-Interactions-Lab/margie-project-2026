/**
 * Who makes MARGIE, how to cite MARGIE and where the desktop app is: one copy, for the
 * Contributors, Acknowledgements, README and Home pages.
 */

export const LAB = {
	name: 'Diet-Microbiome Interactions Lab',
	pi: 'Stephen R Lindemann',
	email: 'lindems@purdue.edu'
};

export const PEOPLE = [
	{ name: 'Sajal Bhattarai', role: "Developed MARGIE's methods and the pipeline's host scripts" },
	{ name: 'Dane Deemer', role: 'Developed the Bioinformatics Supercomputing Platform (BSP), which houses MARGIE' },
	{ name: 'Stephen R Lindemann', role: 'Principal investigator' }
];

/** The repository to cite, which holds the backend and the interface. */
export const CITE_URL = 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026';

/** APA 7th, as the repository's README gives it. */
export const CITATION =
	'Bhattarai, S., Deemer, D., & Lindemann, S. R. (2026). MARGIE: Mostly Automated Rapid Genome Inference Environment [Computer software]. Purdue University. ' +
	CITE_URL;

/** The thesis in which MARGIE was first built (APA 7th), cited beside the software. */
export const THESIS_DOI = 'https://doi.org/10.25394/PGS.33103682.v1';
export const THESIS_CITATION =
	'Bhattarai, S. (2026). Mostly Automated Rapid Genome Inference Environment [Thesis, Purdue University]. Purdue University Graduate School. ' +
	THESIS_DOI;
/** The thesis as BibTeX, as Purdue's repository gives it. */
export const THESIS_BIBTEX = `@article{Bhattarai2026,
author = "Sajal Bhattarai",
title = "{MOSTLY AUTOMATED RAPID GENOME INFERENCE ENVIRONMENT}",
year = "2026",
month = "7",
url = "https://hammer.purdue.edu/articles/thesis/_b_MOSTLY_AUTOMATED_RAPID_GENOME_INFERENCE_ENVIRONMENT_b_/33103682",
doi = "10.25394/PGS.33103682.v1"
}`;

/** The code and data as the thesis used and cites them (its references 2026a to 2026c), with BibTeX. */
export const THESIS_RECORDS: { what: string; text: string; href: string }[] = [
	{
		what: 'The backend as used in the thesis',
		text: 'Bhattarai, S., Deemer, D., & Lindemann, S. (2026a). bioinformatics-tools (Version 1.0.0) [Computer software]. https://github.com/sajalbhattarai/bioinformatics-tools/releases/tag/v.1.0.0',
		href: 'https://github.com/sajalbhattarai/bioinformatics-tools/releases/tag/v.1.0.0'
	},
	{
		what: 'The web interface as used in the thesis',
		text: 'Bhattarai, S., Deemer, D., & Lindemann, S. (2026b). biolab-fe (Version 1.0.0) [Computer software]. https://github.com/sajalbhattarai/biolab-fe/releases/tag/v1.0.0',
		href: 'https://github.com/sajalbhattarai/biolab-fe/releases/tag/v1.0.0'
	},
	{
		what: "The thesis's data, archived (embargoed until 30 August 2028)",
		text: 'Bhattarai, S., Deemer, D., & Lindemann, S. (2026c). Mostly Automated Rapid Genome Inference Environment [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.21632205',
		href: 'https://doi.org/10.5281/zenodo.21632205'
	}
];
export const THESIS_RECORDS_BIBTEX = `@software{Bhattarai2026aBioinformaticsTools,
author = "Sajal Bhattarai and Dane Deemer and Stephen Lindemann",
title = "{bioinformatics-tools}",
version = "1.0.0",
year = "2026",
url = "https://github.com/sajalbhattarai/bioinformatics-tools/releases/tag/v.1.0.0"
}
@software{Bhattarai2026bBiolabFe,
author = "Sajal Bhattarai and Dane Deemer and Stephen Lindemann",
title = "{biolab-fe}",
version = "1.0.0",
year = "2026",
url = "https://github.com/sajalbhattarai/biolab-fe/releases/tag/v1.0.0"
}
@misc{Bhattarai2026cData,
doi = {10.5281/ZENODO.21632205},
url = {https://zenodo.org/doi/10.5281/zenodo.21632205},
author = {Bhattarai, Sajal and Deemer, Dane and Lindemann, Stephen},
title = {Mostly Automated Rapid Genome Inference Environment},
publisher = {Zenodo},
year = {2026},
note = {Embargoed until 2028-08-30}
}`;

/** The base architecture MARGIE was built on (APA 7th): Dane Deemer's backend and web interface. */
export const BASE_CITATIONS: { what: string; text: string; href: string }[] = [
	{
		what: 'The backend (API, command line and workflow engine) that be-margie grew from',
		text: 'Deemer, D. (2020). bioinformatics-tools [Computer software]. GitHub. https://github.com/wintermutant/bioinformatics-tools',
		href: 'https://github.com/wintermutant/bioinformatics-tools'
	},
	{
		what: 'The web interface that fe-margie grew from',
		text: 'Deemer, D. (2025). biolab-fe [Computer software]. GitHub. https://github.com/wintermutant/biolab-fe',
		href: 'https://github.com/wintermutant/biolab-fe'
	}
];
/** The base architecture as BibTeX. */
export const BASE_BIBTEX = `@software{Deemer2020,
author = "Dane Deemer",
title = "{bioinformatics-tools}",
year = "2020",
publisher = "GitHub",
url = "https://github.com/wintermutant/bioinformatics-tools"
}
@software{Deemer2025,
author = "Dane Deemer",
title = "{biolab-fe}",
year = "2025",
publisher = "GitHub",
url = "https://github.com/wintermutant/biolab-fe"
}`;

/**
 * The computing MARGIE runs on, acknowledged and cited
 * (https://www.rcac.purdue.edu/about/acknowledge): its community cluster paper (BibTeX as RCAC gives
 * it), the Geddes platform paper (BibTeX from its DOI) and the Negishi cluster's own page.
 */
export const COMPUTING = {
	thanks:
		"MARGIE's runs use research computing resources of the Rosen Center for Advanced Computing (RCAC), Information Technology at Purdue University: the Negishi community cluster and the Geddes Community Composable Platform, which the National Science Foundation funded under award OAC-2018926 (CC* Compute: Private Campus Cloud for Data Analytics and Machine Learning). We thank RCAC and its staff for these resources and their support.",
	award: 'https://www.nsf.gov/awardsearch/showAward?AWD_ID=2018926',
	refs: [
		{
			id: 'mccartney2014',
			apa: 'McCartney, G., Hacker, T., & Yang, B. (2014). Empowering faculty: A campus cyberinfrastructure strategy for research communities. EDUCAUSE Review.',
			url: 'https://er.educause.edu/articles/2014/7/empowering-faculty-a-campus-cyberinfrastructure-strategy-for-research-communities'
		},
		{
			id: 'smith2020geddes',
			apa: 'Smith, P. M., Gough, E., Younts, A., Werts, B., Hacker, T. J., Neumeister, N., & Wisecaver, J. (2020). The “Geddes” composable platform: An evolution of community clusters for a composable world. 2020 IEEE/ACM International Workshop on Interoperability of Supercomputing and Cloud Technologies (SuperCompCloud), 33–38.',
			url: 'https://doi.org/10.1109/SuperCompCloud51944.2020.00011'
		},
		{
			id: 'rcacnegishi',
			apa: 'Rosen Center for Advanced Computing. (n.d.). Negishi [Community cluster]. Purdue University. Retrieved October 25, 2026, from',
			url: 'https://www.rcac.purdue.edu/compute/negishi'
		}
	],
	bibtex: `@article{McCartney2014,
author = {McCartney, Gerry and Hacker, Thomas and Yang, Baijian},
journal = {Educause Review},
title = {{Empowering Faculty: A Campus Cyberinfrastructure Strategy for Research Communities}},
year = {2014},
url = {https://er.educause.edu/articles/2014/7/empowering-faculty-a-campus-cyberinfrastructure-strategy-for-research-communities}
}
@inproceedings{Smith2020Geddes,
title = {The “Geddes” Composable Platform - An Evolution of Community Clusters for a Composable World},
url = {http://dx.doi.org/10.1109/SuperCompCloud51944.2020.00011},
DOI = {10.1109/supercompcloud51944.2020.00011},
booktitle = {2020 IEEE/ACM International Workshop on Interoperability of Supercomputing and Cloud Technologies (SuperCompCloud)},
publisher = {IEEE},
author = {Smith, Preston M. and Gough, Erik and Younts, Alexander and Werts, Brian and Hacker, Thomas J. and Neumeister, Norbert and Wisecaver, Jennifer},
year = {2020},
month = nov,
pages = {33--38}
}
@misc{RCACNegishi,
author = {{Rosen Center for Advanced Computing}},
title = {Negishi community cluster},
howpublished = {Purdue University},
url = {https://www.rcac.purdue.edu/compute/negishi},
note = {Accessed 2026-10-25}
}`
};

/** The grants that fund the work (PI Stephen R. Lindemann), as the agencies' records name them. */
export const FUNDING: { funder: string; award: string; title: string; url: string }[] = [
	{
		funder: 'U.S. National Science Foundation',
		award: 'Grant No. 2125155',
		title: 'MIM: Microbial Division of Labor in Polysaccharide-Degrading Communities',
		url: 'https://www.nsf.gov/awardsearch/showAward?AWD_ID=2125155'
	},
	{
		funder: 'National Institute of General Medical Sciences (NIGMS), U.S. National Institutes of Health',
		award: 'Award No. R35 GM133634',
		title: 'Carbohydrate Structure Controls on Human Gut Microbial Ecology',
		url: 'https://reporter.nih.gov/project-details/10645210'
	}
];

/** How AI was used in building MARGIE: the same text as the READMEs' "AI usage in the project". */
export const AI_USAGE = {
	paragraphs: [
		"MARGIE's platform orchestration, the engine, API and interface MARGIE runs on, was developed by Dane Deemer (Deemer, 2020; Deemer, 2025). The methods and the host scripts of the pipeline were developed by Sajal Bhattarai, who designed and implemented the phase 9 to 12 scripts (consolidation, labeling, scoring and fingerprinting) and defined their core ideas, architecture and intended behaviour.",
		'Claude models (Anthropic, Inc.) were used interactively during development to debug the code and scripts, to improve their robustness, and to help refine the visualizations: the circular operon diagrams and the interactive genome map pages. Sajal Bhattarai checked the code, scripts and visualizations repeatedly and validated that they run as intended.'
	],
	reference: { apa: 'Anthropic. (2026). Claude [Large language model].', url: 'https://www.anthropic.com/claude' }
};

/** Where the desktop app is downloaded from (its releases, for now). */
export const DESKTOP_URL = `${CITE_URL}/releases`;

/** The open-source software MARGIE is built with (be-margie/pyproject.toml, fe-margie/margie-fe/package.json). */
export const SOFTWARE: {
	group: string;
	items: { name: string; what: string; href: string; version?: string; licence?: string; licenceUrl?: string; source?: string }[];
}[] = [
	{
		group: 'Workflow and computing',
		items: [
			{ name: 'Snakemake', what: 'the workflow engine, with its SLURM executor plugin', href: 'https://snakemake.github.io' },
			{ name: 'Apptainer', what: 'runs each tool in its own container', href: 'https://apptainer.org' },
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
			{ name: 'Fontsource', what: 'Bricolage Grotesque, IBM Plex, Lato and Roboto Slab', href: 'https://fontsource.org' }
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
