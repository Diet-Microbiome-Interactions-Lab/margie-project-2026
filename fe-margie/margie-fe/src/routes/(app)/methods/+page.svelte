<script lang="ts">
	import '$lib/crisp/about.css';
	import { ArrowRight, CircleQuestionMark, FileCode, Gauge, LockKeyhole } from 'lucide-svelte';
	import FaqList from '$lib/crisp/FaqList.svelte';
	import { FAQS } from '$lib/crisp/faq';

	/**
	 * Methods: what MARGIE does, phase by phase (margie_sb.smk), then the FAQ (FaqList), which explains
	 * each step with its references and code.
	 */
	const PHASES: { n: string; step: string; tools: string; does: string }[] = [
		{ n: '1', step: 'Quality', tools: 'QUAST (optional)', does: 'Assembly statistics for each genome: contigs, N50, total length.' },
		{
			n: '2',
			step: 'Taxonomy',
			tools: 'GTDB-Tk (optional)',
			does: "Places each genome in the GTDB taxonomy, which gives its domain and genetic code. Without it, both come from the genome table."
		},
		{
			n: '3',
			step: 'Gene calling',
			tools: 'RASTtk, or Prodigal',
			does: 'RASTtk calls and annotates the genes of every genome whose domain and genetic code are known; any other genome is called by Prodigal, written in the same layout so later steps are shared.'
		},
		{
			n: '4',
			step: 'Function',
			tools: 'COG, KEGG (KofamScan), eggNOG, UniProt Swiss-Prot, Pfam, TIGRFAM, PGAP, InterPro and dbCAN in every run; Genome Properties, MEROPS and TCDB when chosen',
			does: 'Each tool annotates the predicted proteins on its own. The ones labeling and scoring read are part of every run, so scores compare across runs. Results are kept per protein, so a protein annotated in an earlier run is not searched again.'
		},
		{ n: '5', step: 'Operons', tools: 'UniOP', does: 'Pairwise operon probabilities between neighbouring genes, from intergenic distance, grouping genes into operons.' },
		{ n: '6', step: 'Membrane topology', tools: 'Phobius, TMbed, SignalP 6 (when licensed)', does: 'Transmembrane helices and signal peptides.' },
		{
			n: '7',
			step: 'Envelope',
			tools: "MARGIE's own inference",
			does: 'Infers the cell envelope type (monoderm or diderm) from marker annotations in TIGRFAM, PGAP, Pfam and UniProt, so the localisation tools use the right model.'
		},
		{ n: '8', step: 'Localisation', tools: 'PSORTb, DeepSig, SignalP 4 (when licensed)', does: 'Subcellular location and signal peptides, run with the inferred envelope type.' },
		{ n: '9', step: 'Consolidation', tools: "MARGIE's own", does: "Joins every tool's results into one table, one row per gene, every column kept." },
		{ n: '10', step: 'Labeling', tools: "MARGIE's own", does: 'Gives each gene one product label by a fixed trust hierarchy (below).' },
		{
			n: '11',
			step: 'Fingerprints',
			tools: "MARGIE's own",
			does: "Each gene's pattern of hits across the tools, and each operon's, is hashed into a fingerprint, so the same evidence can be recognised in other genomes."
		},
		{ n: '12', step: 'Scoring', tools: "MARGIE's own", does: 'A 0 to 1 confidence for every gene, from four measures (below), with a tier and a review flag.' },
		{ n: '13', step: 'Fingerprint database', tools: "MARGIE's own", does: "Adds the genome's gene and operon fingerprints to the shared database that later genomes are scored against." },
		{ n: '15', step: 'Gene report', tools: "MARGIE's own (optional)", does: 'A per-gene report of the evidence behind each annotation.' }
	];

</script>

<svelte:head><title>Methods | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-methods">
	<div class="cr-head">
		<h1 class="cr-title">Methods</h1>
		<p class="cr-lede">How MARGIE annotates a genome and scores each gene.</p>
	</div>

	<div class="ab mt-read">
		<section class="ab-box">
			<h2>Overview</h2>
			<p>
				MARGIE is a Snakemake workflow that runs on an HPC cluster through SLURM, the tools in their own containers. She takes genome
				assemblies (FASTA) and, for each genome, its domain and genetic code when known. She calls genes, annotates their proteins with
				many tools at once, groups genes into operons, works out where proteins sit in the cell, gives each gene one label, and scores
				how much the evidence for that label agrees. She keeps each step's output, so each label can be traced to the hits behind it.
			</p>
			<a class="ab-go" href="/code">
				<FileCode size={26} />
				<span class="ab-go-text">
					<b>Read the code behind each step</b>
					<span>Consolidation | Labeling | Operon database | Scoring | Fingerprinting | Fingerprint databases: the Python scripts as the server runs them, highlighted, with line numbers.</span>
				</span>
				<span class="ab-go-to">Open the code <ArrowRight size={15} /></span>
			</a>
		</section>

		<section class="ab-box">
			<h2>The phases of a run</h2>
			<table class="ab-table">
				<thead><tr><th>Phase</th><th>Step</th><th>Tools</th><th>What it does</th></tr></thead>
				<tbody>
					{#each PHASES as p (p.n)}
						<tr><td class="ab-num">{p.n}</td><td><b>{p.step}</b></td><td>{p.tools}</td><td>{p.does}</td></tr>
					{/each}
				</tbody>
			</table>
			<p class="ab-lab">Phase 14 (genome comparison: ANI, AAI, closest genomes, synteny) and the LLM layer are being worked on and do not run yet.</p>
		</section>

		{#if FAQS.length}
		<section id="faq" class="mt-faq" aria-labelledby="faq-title">
			<div class="mt-faq-head">
				<CircleQuestionMark size={24} />
				<div>
					<h2 id="faq-title">Frequently asked questions</h2>
					<p>How each step works, with the papers it rests on and the code that does it.</p>
				</div>
			</div>
			<a class="ab-go" href="/methods/scores">
				<Gauge size={26} />
				<span class="ab-go-text">
					<b>Reading the scores</b>
					<span>C3's two channels | the genome pool it compares against | what each tier means | a gene scored in five genomes | the check against EcoCyc. Opens with a password the lab gives on request.</span>
				</span>
				<span class="ab-go-to"><LockKeyhole size={14} /> Open <ArrowRight size={15} /></span>
			</a>
			<FaqList />
		</section>
		{/if}

	</div>
</div>

<style>
	/* Easier reading: body text at the large size, tables at the base size (both follow Customize → text size). */
	.mt-read :global(.ab-box) {
		font-size: var(--mg-fs-lg);
		line-height: 1.65;
	}
	.mt-read :global(.ab-table) {
		font-size: var(--mg-fs);
	}
	.mt-read :global(.ab-formula) {
		font-size: var(--mg-fs-sm);
	}
	.mt-read :global(.ab-go-text) {
		font-size: var(--mg-fs);
	}
	/* The FAQ: coloured so it stands out on the page. */
	.mt-faq {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 16px 18px 18px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 40%, var(--mg-border));
		border-top: 4px solid var(--mg-accent);
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-accent) 8%, var(--mg-surface));
		scroll-margin-top: 12px;
	}
	.mt-faq-head {
		display: flex;
		align-items: center;
		gap: 12px;
		color: var(--mg-accent);
	}
	.mt-faq-head h2 {
		margin: 0;
		color: var(--mg-accent);
		font-size: var(--mg-fs-xl);
		font-weight: 700;
	}
	.mt-faq-head p {
		margin: 2px 0 0;
		color: var(--mg-text-2);
		font-size: var(--mg-fs);
	}
</style>
