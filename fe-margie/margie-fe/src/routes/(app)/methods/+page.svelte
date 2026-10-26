<script lang="ts">
	import { ArrowRight } from 'lucide-svelte';
	import { api } from '$lib/api';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';
	import { FAQS } from '$lib/crisp/faq';

	/**
	 * Methods: what MARGIE does, phase by phase (margie_sb.smk). The FAQ, which explains each step with
	 * its references and code, is on its own page (/faq).
	 */
	type Phase = { n: string; step: string; tools: string[]; does: string; more?: { href: string; label: string } };
	const STAGES: { title: string; blurb: string; phases: Phase[] }[] = [
		{
			title: 'Prepare each genome',
			blurb: 'Quality, taxonomy and the gene calls that the later steps share.',
			phases: [
				{ n: '1', step: 'Quality', tools: ['QUAST (optional)'], does: 'Assembly statistics for each genome: contigs, N50 and total length.' },
				{
					n: '2',
					step: 'Taxonomy',
					tools: ['GTDB-Tk (optional)'],
					does: "Places each genome in the GTDB taxonomy, which gives its domain and genetic code. The genome table on Analyze can give both instead."
				},
				{
					n: '3',
					step: 'Gene calling',
					tools: ['RASTtk', 'Prodigal'],
					does: "RASTtk calls and names the genes of each genome with a known domain and genetic code; Prodigal calls the others, in RASTtk's file layout, so the later steps are shared.",
					more: { href: '/faq#gene-calling', label: 'How MARGIE calls genes' }
				}
			]
		},
		{
			title: 'Annotate and place the proteins',
			blurb: 'Many tools, each on its own, then operons, topology, envelope and location.',
			phases: [
				{
					n: '4',
					step: 'Function',
					tools: ['COG', 'KEGG (KofamScan)', 'eggNOG', 'UniProt Swiss-Prot', 'Pfam', 'TIGRFAM', 'PGAP', 'InterPro', 'dbCAN', 'Genome Properties', 'MEROPS', 'TCDB'],
					does: 'Each tool annotates the predicted proteins on its own. The nine that labeling and scoring read run in each run, so scores compare across runs; Genome Properties, MEROPS and TCDB run when chosen. Results are stored per protein, so a protein annotated before comes back from the cache.'
				},
				{
					n: '5',
					step: 'Operons',
					tools: ['UniOP'],
					does: 'Pairwise operon probabilities between neighbouring genes, from intergenic distance, which group the genes into operons.',
					more: { href: '/faq#operons', label: 'How operons are called' }
				},
				{ n: '6', step: 'Membrane topology', tools: ['Phobius', 'TMbed', 'SignalP 6'], does: 'Transmembrane helices and signal peptides. Phobius and SignalP 6 run once the user records a licence for them.' },
				{
					n: '7',
					step: 'Envelope',
					tools: ["MARGIE's own inference"],
					does: 'Infers the cell envelope type (monoderm or diderm) from marker annotations in TIGRFAM, PGAP, Pfam and UniProt, and sets the model the localisation tools run with.',
					more: { href: '/faq#envelope', label: 'How the envelope is inferred' }
				},
				{ n: '8', step: 'Localisation', tools: ['PSORTb', 'DeepSig', 'SignalP 4'], does: 'Subcellular location and signal peptides, run with the inferred envelope type. SignalP 4 runs once the user records a licence for it.' }
			]
		},
		{
			title: 'Label, score and remember',
			blurb: "MARGIE's own steps: one row per gene, one label, a confidence, and fingerprints that later genomes are compared with.",
			phases: [
				{
					n: '9',
					step: 'Consolidation',
					tools: ["MARGIE's own"],
					does: "Joins the tools' results into one table, one row per gene, with each column kept.",
					more: { href: '/faq#consolidation', label: 'How consolidation works' }
				},
				{
					n: '10',
					step: 'Labeling',
					tools: ["MARGIE's own"],
					does: 'Gives each gene one product label by a fixed trust hierarchy, from curated family models down to domain models.',
					more: { href: '/faq#label-derivation', label: 'How a label is derived' }
				},
				{
					n: '11',
					step: 'Fingerprints',
					tools: ["MARGIE's own"],
					does: "Hashes each gene's pattern of hits across the tools, and each operon's, into a fingerprint, so the same evidence is recognised in other genomes.",
					more: { href: '/faq#fingerprints', label: 'What a fingerprint is' }
				},
				{
					n: '12',
					step: 'Scoring',
					tools: ["MARGIE's own"],
					does: 'A 0 to 1 confidence for each gene from four measures (C1 to C4), with a tier and a review flag.',
					more: { href: '/faq#scoring', label: 'How scoring works' }
				},
				{
					n: '13',
					step: 'Fingerprint databases',
					tools: ["MARGIE's own"],
					does: "Adds the genome's gene and operon fingerprints to the shared databases that later genomes are compared with.",
					more: { href: '/faq#pool-databases', label: 'How the shared databases grow' }
				}
			]
		},
		{
			title: 'Report',
			blurb: 'The evidence behind each annotation, gene by gene.',
			phases: [{ n: '15', step: 'Gene report', tools: ["MARGIE's own (optional)"], does: 'A per-gene report of the evidence behind each annotation.' }]
		}
	];
	/** The hashes MARGIE recognises genomes, proteins and genes by, so each is annotated once. */
	const HASHES = [
		{
			hash: 'Genome hash',
			level: 'Genome',
			from: "The genome's DNA, contig by contig (its file name and line lengths aside)",
			when: 'Before the run starts',
			why: 'A genome is the same genome under any file name',
			helps: 'Restores a genome annotated before, whole; names its results <name>--<the first 8 characters> (coli--a1b2c3d4); keys its rows in the database'
		},
		{
			hash: 'Protein hash',
			level: 'Protein',
			from: "The protein's amino-acid sequence",
			when: 'After gene calling, before the tools',
			why: 'A protein gives the same answer from a tool in any genome',
			helps: 'Each tool runs on new proteins only; each protein is linked to the genomes it occurs in'
		},
		{
			hash: 'Gene hash',
			level: 'Gene',
			from: "Its contig, start, end, strand and protein (an RNA's feature type)",
			when: "Storing and restoring a genome's cached tables",
			why: 'Gene callers number genes anew with each submission, and copies of one protein sit in different places',
			helps: 'Puts cached results back on the right gene under any numbering'
		},
		{
			hash: 'Fingerprint hash',
			level: 'Protein and gene',
			from: "The protein's descriptors from the tools: a core part from the seven C1 tools, an additional part from the others",
			when: 'After scoring',
			why: 'Proteins with the same descriptors share a fingerprint',
			helps: "One record per protein; a tool added later changes only the additional part"
		},
		{
			hash: 'Protein-set hash',
			level: 'Genome',
			from: "The genome's protein hashes, together",
			when: "Scoring (C3's operon reference)",
			why: 'Recognises a genome by its content, under any name',
			helps: 'Adds a genome to the operon reference once, and leaves it out when it is scored'
		},
		{
			hash: 'Tool key',
			level: "A protein's results",
			from: 'The tool and the settings that change its answer (its thresholds, InterPro analyses)',
			when: 'With the protein hash',
			why: "Keeps a protein's results apart by tool and settings; new tool and database versions keep them",
			helps: 'Genomes annotated once are not run again when a tool or database is updated'
		},
		{
			hash: 'Results-file hash',
			level: 'Load',
			from: "A tool's results file",
			when: 'Loading into the database',
			why: 'A file loaded before holds the same rows',
			helps: 'Skips loading it again; a reload replaces the genome\'s rows by genome hash'
		},
	];
	/** What the database keeps by hash, read by eye when checking hashes and restoring results. */
	const RECORDS = [
		{ table: 'protein_records', what: 'One row per protein: its hash, the genomes it occurs in, its fingerprints and label, the descriptor of each core tool, then the additional tools' },
		{ table: 'protein_genomes', what: 'Each protein hash with each genome hash it occurs in' },
		{ table: 'genome_proteomes', what: "Each genome hash with its protein set and the names it came under" },
		{ table: 'genome_genes', what: "Each genome's genes by gene hash, with each gene's protein hash and fingerprint" },
		{ table: 'genome_protein_descriptors', what: 'Answers that depend on the genome as well as the protein (PSORTb, DeepSig), by genome hash and protein hash' }
	];
	const HASH_CODE = [
		{ path: 'genome_identity.py', what: 'The genome and protein hashes' },
		{ path: 'output_cache.py', what: 'The genome cache: whole tool outputs by genome hash, genes by gene hash' },
		{ path: 'protein_cache.py', what: "The protein cache, the links between proteins and genomes, and each protein's record" },
		{ path: 'load_to_db.py', what: "Loading into the database, a genome's rows replaced by genome hash" },
		{ path: 'scoring/update-occ-reference-depot.py', what: 'The operon reference, a genome added once by its content' },
		{ path: 'fingerprint/add-gene-fingerprint.py', what: "Each gene's fingerprint" }
	];
	const DOES = [
		{ title: 'Calls genes', text: 'RASTtk or Prodigal, genome by genome' },
		{ title: 'Annotates proteins', text: 'with many tools at once, each on its own' },
		{ title: 'Finds operons', text: 'from the spacing between neighbouring genes' },
		{ title: 'Places proteins', text: 'in the cell, with the inferred envelope' },
		{ title: 'Labels each gene', text: 'with one product name, by a trust hierarchy' },
		{ title: 'Scores the label', text: 'from 0 to 1, by how well the evidence agrees' }
	];

	/** MARGIE's own steps and their scripts, as the Code page lists them (routers/code.py). */
	interface CodeStep {
		key: string;
		title: string;
		what: string;
		files: { path: string; name: string; lines: number }[];
	}
	let code = $state<CodeStep[]>([]);
	$effect(() => {
		api<{ steps: CodeStep[] }>('/code').then(
			(r) => (code = r.steps),
			() => (code = [])
		);
	});
</script>

<svelte:head><title>Methods | MARGIE</title></svelte:head>

<ReadingPage title="Methods" lede="How MARGIE annotates a genome, phase by phase, and scores each gene's label." shade="page-methods">
	<section class="rp-sec" id="overview" data-toc="Overview">
		<h2>Overview</h2>
		<p class="rp-lead">
			MARGIE is a Snakemake workflow that runs on an HPC cluster through SLURM, each tool in its own container. She takes genome
			assemblies (FASTA) and, for each genome, its domain and genetic code when they are known.
		</p>
		<div class="rp-trio">
			{#each DOES as d (d.title)}
				<div class="rp-tile"><b>{d.title}</b><span>{d.text}</span></div>
			{/each}
		</div>
		<p>She keeps each step's output, so each label traces back to the hits behind it.</p>
	</section>

	<a class="rp-link" href="/faq">
		<span class="rp-link-text"><b>Frequently asked questions</b><span>{FAQS.length} answers on how each step works, with the papers it rests on and the code that does it.</span></span>
		<ArrowRight size={20} />
	</a>

	<section class="rp-sec" id="phases" data-toc="The phases of a run">
		<h2>The phases of a run</h2>
		<p class="rp-note">A run moves through four stages. Each phase starts once the files it reads exist.</p>
		{#each STAGES as s, k (s.title)}
			<h3>Stage {k + 1}: {s.title}</h3>
			<p class="rp-note">{s.blurb}</p>
			<div class="rp-scroll">
				<table class="rp-table mt-phases">
					<thead><tr><th>Phase</th><th>Step</th><th>Tools</th><th>What it does</th></tr></thead>
					<tbody>
						{#each s.phases as p (p.n)}
							<tr>
								<td class="mt-n">{p.n}</td>
								<td><b>{p.step}</b></td>
								<td>{p.tools.join(' | ')}</td>
								<td>{p.does}{#if p.more}{' '}<a href={p.more.href}>{p.more.label} »</a>{/if}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/each}
	</section>

	<section class="rp-sec" id="hashes" data-toc="Annotating each genome and protein once">
		<h2>Annotating each genome and protein once</h2>
		<p class="rp-lead">
			MARGIE recognises genomes, proteins and genes by hashes of their sequences. She runs a tool on a sequence once and restores
			its results when the sequence comes back, under any file name.
		</p>
		<ol class="mt-gates">
			<li><b>Before the run: the genome hash.</b> A genome annotated before comes back from the genome cache: its gene calls, GTDB-Tk and each tool's results. Consolidation, labeling and scoring run again: the first two take about a minute, and scoring reads an operon reference that grows with each genome.</li>
			<li><b>After gene calling: the protein hash.</b> A protein annotated before with a tool comes back from the protein cache; the tool runs on the new proteins. A tool new to a protein runs and is added; the protein's other tools stay.</li>
		</ol>
		<p>
			Each genome runs as its file name and the first 8 characters of its genome hash (<span class="mg-mono">coli--a1b2c3d4</span>), so genomes that share a file name stay apart in the database and the results. The website shows the name you gave it, with the hash beside it on the Jobs page.
		</p>
		<h3>The hashes</h3>
		<div class="rp-scroll">
			<table class="rp-table mt-hashes">
				<thead><tr><th>Hash</th><th>Level</th><th>Made from</th><th>When</th><th>Why</th><th>What it helps with</th></tr></thead>
				<tbody>
					{#each HASHES as h (h.hash)}
						<tr><td><b>{h.hash}</b></td><td>{h.level}</td><td>{h.from}</td><td>{h.when}</td><td>{h.why}</td><td>{h.helps}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
		<h3>What the database keeps by hash</h3>
		<div class="rp-scroll">
			<table class="rp-table">
				<thead><tr><th>Table</th><th>What it holds</th></tr></thead>
				<tbody>
					{#each RECORDS as r (r.table)}
						<tr><td class="mg-mono">{r.table}</td><td>{r.what}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
		<h3>The scripts</h3>
		<ul class="rp-plain">
			{#each HASH_CODE as c (c.path)}
				<li>
					<a class="mt-file" href="/code?file={encodeURIComponent(c.path)}">
						<span class="mg-mono">{c.path.split('/').pop()}</span><span class="mt-lines">{c.what}</span><ArrowRight size={16} />
					</a>
				</li>
			{/each}
		</ul>
	</section>

	<section class="rp-sec" id="code" data-toc="The code behind each step">
		<h2>The code behind each step</h2>
		<p>MARGIE's own steps are Python scripts. Each one opens on the Code page as the server runs it, highlighted, with line numbers.</p>
		{#if code.length}
			<div class="mt-code">
				{#each code as c (c.key)}
					<div class="mt-code-step">
						<b>{c.title}</b>
						<p class="rp-note">{c.what}</p>
						<ul class="rp-plain">
							{#each c.files as f (f.path)}
								<li>
									<a class="mt-file" href="/code?file={encodeURIComponent(f.path)}">
										<span class="mg-mono">{f.name}</span><span class="mt-lines">{f.lines} lines</span><ArrowRight size={16} />
									</a>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>
		{/if}
		<a class="rp-link" href="/code">
			<span class="rp-link-text"><b>Open the Code page</b><span>Each script, with copy and download, and its place on GitHub.</span></span>
			<ArrowRight size={20} />
		</a>
	</section>
</ReadingPage>

<style>
	.mt-gates {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding-left: 1.3em;
	}
	.mt-hashes td:first-child {
		white-space: nowrap;
	}
	.mt-phases td {
		min-width: 0;
	}
	.mt-phases .mt-n {
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
		text-align: center;
	}
	.mt-phases td:nth-child(2) {
		white-space: nowrap;
	}
	.mt-phases td:nth-child(3) {
		width: 24%;
	}
	/* The scripts of each of MARGIE's own steps: a ruled box per step, a row per script. */
	.mt-code {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}
	.mt-code-step {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
		padding: 16px 18px;
		border: 1px solid var(--rp-line);
		border-radius: 3px;
		background: var(--rp-paper);
	}
	.mt-code-step > b {
		color: var(--rp-head);
		font-family: var(--rp-head-font);
		font-size: var(--rp-h3);
		font-weight: 700;
		line-height: 1.3;
	}
	.mt-code-step ul {
		display: flex;
		flex-direction: column;
		margin-top: 4px;
		border-top: 1px solid var(--rp-line);
	}
	.mt-code-step li + li {
		margin-top: 0;
	}
	.mt-file {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 4px;
		border-bottom: 1px solid var(--rp-line);
		color: var(--rp-link);
		text-decoration: none;
	}
	.mt-file:hover {
		background: var(--rp-stripe);
	}
	.mt-file .mg-mono {
		flex: 1;
		min-width: 0;
		font-size: calc(var(--mg-fs) * 1.08);
		font-weight: 600;
		overflow-wrap: anywhere;
	}
	.mt-lines {
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
		white-space: nowrap;
	}
	@container (max-width: 760px) {
		.mt-code {
			grid-template-columns: minmax(0, 1fr);
		}
		/* Each phase as a stacked block on narrow screens. */
		.mt-phases,
		.mt-phases tbody,
		.mt-phases tr,
		.mt-phases td {
			display: block;
			width: auto;
		}
		.mt-phases thead {
			display: none;
		}
		.mt-phases tr {
			border-bottom: 1px solid var(--rp-line);
		}
		.mt-phases tr:last-child {
			border-bottom: 0;
		}
		.mt-phases td {
			padding: 3px 14px;
			border: 0;
		}
		.mt-phases td:nth-child(2) {
			white-space: normal;
		}
		.mt-phases .mt-n {
			padding-top: 12px;
			text-align: left;
		}
		.mt-phases .mt-n::before {
			content: 'Phase ';
		}
		.mt-phases td:nth-child(3) {
			width: auto;
			color: var(--mg-text-2);
		}
		.mt-phases td:last-child {
			padding-bottom: 12px;
		}
	}
</style>
