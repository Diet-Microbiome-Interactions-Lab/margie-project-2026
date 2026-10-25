<script lang="ts">
	import { ArrowRight, Boxes, CircleQuestionMark, Dna, FileCode, Gauge, MapPin, Tag, Workflow } from 'lucide-svelte';
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
	const DOES = [
		{ icon: Dna, title: 'Calls genes', text: 'RASTtk or Prodigal, genome by genome' },
		{ icon: Boxes, title: 'Annotates proteins', text: 'with many tools at once, each on its own' },
		{ icon: Workflow, title: 'Finds operons', text: 'from the spacing between neighbouring genes' },
		{ icon: MapPin, title: 'Places proteins', text: 'in the cell, with the inferred envelope' },
		{ icon: Tag, title: 'Labels each gene', text: 'with one product name, by a trust hierarchy' },
		{ icon: Gauge, title: 'Scores the label', text: 'from 0 to 1, by how well the evidence agrees' }
	];
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
				<div class="rp-tile"><d.icon size={22} /><b>{d.title}</b><span>{d.text}</span></div>
			{/each}
		</div>
		<p>She keeps each step's output, so each label traces back to the hits behind it.</p>
	</section>

	<div class="rp-pair">
		<a class="rp-link" href="/faq">
			<span class="rp-link-icon"><CircleQuestionMark size={24} /></span>
			<span class="rp-link-text"><b>Frequently asked questions</b><span>{FAQS.length} answers, with the papers and the code behind each step.</span></span>
			<ArrowRight size={18} />
		</a>
		<a class="rp-link" href="/code">
			<span class="rp-link-icon"><FileCode size={24} /></span>
			<span class="rp-link-text"><b>The code behind each step</b><span>The Python scripts as the server runs them, highlighted.</span></span>
			<ArrowRight size={18} />
		</a>
	</div>

	<section class="rp-sec" id="phases" data-toc="The phases of a run">
		<h2>The phases of a run</h2>
		<p class="rp-note">A run moves through four stages. Each phase starts once the files it reads exist.</p>
		{#each STAGES as s, k (s.title)}
			<div class="mt-stage">
				<header class="mt-stage-head">
					<span class="mt-stage-k">Stage {k + 1}</span>
					<h3>{s.title}</h3>
					<p class="rp-note">{s.blurb}</p>
				</header>
				<ol class="mt-steps">
					{#each s.phases as p (p.n)}
						<li class="mt-step">
							<span class="mt-n">{p.n}</span>
							<div class="mt-body">
								<b class="mt-name">{p.step}</b>
								<div class="mt-tools">{#each p.tools as t (t)}<span>{t}</span>{/each}</div>
								<p>{p.does}</p>
								{#if p.more}<a class="mt-more" href={p.more.href}>{p.more.label} <ArrowRight size={14} /></a>{/if}
							</div>
						</li>
					{/each}
				</ol>
			</div>
		{/each}
	</section>
</ReadingPage>

<style>
	.mt-stage {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding-top: 18px;
		border-top: 1px solid var(--mg-border);
	}
	.mt-stage:first-of-type {
		padding-top: 6px;
		border-top: none;
	}
	.mt-stage-head {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.mt-stage-k {
		color: var(--rp-ink);
		font-size: var(--mg-fs-xs);
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}
	.mt-stage-head h3 {
		margin: 0;
	}
	/* The phases as a timeline: a numbered dot per phase on one line. */
	.mt-steps {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 16px;
		margin: 4px 0 6px;
		padding: 0;
		list-style: none;
	}
	.mt-steps::before {
		position: absolute;
		top: 18px;
		bottom: 18px;
		left: 17px;
		width: 2px;
		background: color-mix(in srgb, var(--mg-accent) 22%, transparent);
		content: '';
	}
	.mt-step {
		position: relative;
		display: grid;
		grid-template-columns: 36px minmax(0, 1fr);
		gap: 16px;
		margin: 0;
	}
	.mt-steps > li + li {
		margin-top: 0;
	}
	.mt-n {
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border: 2px solid var(--mg-accent);
		border-radius: 50%;
		background: var(--mg-surface);
		color: var(--rp-ink);
		font-size: var(--mg-fs-sm);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.mt-body {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
		padding-top: 4px;
	}
	.mt-name {
		font-size: var(--rp-h3);
		font-weight: 650;
		line-height: 1.3;
	}
	.mt-tools {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.mt-tools span {
		padding: 2px 10px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 25%, var(--mg-border));
		border-radius: 999px;
		background: var(--rp-tint);
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
		line-height: 1.6;
	}
	.mt-more {
		display: inline-flex;
		align-self: flex-start;
		align-items: center;
		gap: 4px;
		font-size: var(--rp-small);
		font-weight: 600;
	}
</style>
