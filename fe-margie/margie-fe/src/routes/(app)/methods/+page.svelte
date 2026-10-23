<script lang="ts">
	import '$lib/crisp/about.css';

	/**
	 * Methods: how MARGIE annotates a genome and scores each gene, phase by phase, as the
	 * workflow (margie_sb.smk) and its scoring scripts (workflow_tools/scoring) do it.
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

	const TIERS = [
		['1', 'PGAP, NCBIfam, TIGRFAM', 'curated prokaryotic family rules'],
		['2', 'HAMAP, PIRSF, UniProt Swiss-Prot', 'family rules, whole-protein models, Swiss-Prot hits (identity at least 40%)'],
		['3', 'KEGG', ''],
		['4', 'eggNOG', ''],
		['5', 'RASTtk', ''],
		['6', 'Pfam', ''],
		['7', 'CDD', ''],
		['8', 'COG', ''],
		['9', 'Fallback', 'the first tool with any description, else "No DB hits"']
	];
</script>

<svelte:head><title>Methods | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-methods">
	<div class="cr-head">
		<h1 class="cr-title">Methods</h1>
		<p class="cr-lede">How MARGIE annotates a genome and scores each gene.</p>
	</div>

	<div class="ab">
		<section class="ab-box">
			<h2>Overview</h2>
			<p>
				MARGIE is a Snakemake workflow that runs on an HPC cluster through SLURM, the tools in their own containers. A run takes genome
				assemblies (FASTA) and, for each genome, its domain and genetic code when known. It calls genes, annotates their proteins with
				many tools at once, groups genes into operons, works out where proteins sit in the cell, gives every gene one label, and scores
				how much the evidence for that label agrees. Every step's output is kept, so each label can be traced to the hits behind it.
			</p>
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

		<div class="ab-pair">
			<section class="ab-box">
				<h2>Labeling: one label per gene</h2>
				<p>
					Each gene's label comes from the first tool, in this order, whose best hit is informative and passes its threshold. MEROPS, TCDB
					and dbCAN confirm a label but do not set it.
				</p>
				<table class="ab-table">
					<thead><tr><th>Tier</th><th>Tools</th><th></th></tr></thead>
					<tbody>
						{#each TIERS as [t, tools, note] (t)}
							<tr><td class="ab-num">{t}</td><td>{tools}</td><td class="ab-lab">{note}</td></tr>
						{/each}
					</tbody>
				</table>
			</section>

			<section class="ab-box">
				<h2>Scoring: four measures</h2>
				<h3>C1, tool coverage</h3>
				<p>
					How many of seven sources have an informative hit for the gene: RASTtk, KEGG, eggNOG, COG, Pfam, UniProt, and one slot for the
					TIGRFAM family (PGAP, TIGRFAM and NCBIfam share models). C1 = sources with a hit / 7.
				</p>
				<h3>C2, operon probability</h3>
				<p>The mean UniOP probability that the gene shares an operon with its neighbours; 0.5 where there is none.</p>
				<h3>C3, operon context</h3>
				<p>
					How often the gene's operon neighbourhood recurs across the reference genomes, as a Bayesian estimate per adjacency; 0.5 for
					single genes and operons of hypothetical proteins, and 0 for an operon whose neighbours have no support in the reference.
				</p>
				<h3>C4, EC agreement</h3>
				<p>Whether the tools that give an EC number agree; conflicts lower the score.</p>
			</section>
		</div>

		<section class="ab-box">
			<h2>The confidence score</h2>
			<p class="ab-formula">preliminary = C1 × C4{'\n'}context     = C2 × C3 for genes in an operon, else 0{'\n'}confidence  = preliminary + context, kept between 0 and 1</p>
			<p>
				Operon context only raises a score. The confidence sets the tier: <b>highest</b> above 0.9, <b>high</b> above 0.7, <b>medium</b>
				above 0.5, <b>fair</b> above 0.3, and <b>low</b> otherwise. A gene is flagged for review when its tools' EC numbers conflict, its
				confidence is below 0.5, it sits in an operon with C2 below 0.5, or its operon is ambiguous and gave no boost.
			</p>
		</section>

		<section class="ab-box">
			<h2>Caching and restoration</h2>
			<p>
				The MARGIE database keeps what earlier runs found, at two levels, so a genome or a protein seen before is not worked out again. Each run
				writes <b>cache-report.tsv</b> in its folder, saying for every genome and step whether it ran or came back, and from which level; Jobs
				shows it under the progress, and the progress grid marks restored steps.
			</p>
			<h3>Genome level</h3>
			<p>
				A genome is recognised by a SHA-256 hash of its records' names and bases, so a copy with different line breaks or file name is still the
				same genome. For each step it has finished (GTDB-Tk, RASTtk's gene calls, every annotation tool, the operons, the location tools,
				consolidation and labeling) its output files are stored under that hash. When the genome is run again, each step's files come back before
				the step would start, and the step is skipped; restored tables are rewritten onto this run's RASTtk gene ids. Consolidation and labeling
				come back only when the tool tables they merge are exactly the same as before, so a different set of tools, or a tool with new results,
				merges again.
			</p>
			<h3>Protein level</h3>
			<p>
				After gene calling, a tool whose answer depends on the protein alone (COG, KEGG, eggNOG, UniProt, Pfam, PGAP, TIGRFAM, InterPro, MEROPS,
				TCDB, dbCAN, Phobius, TMbed and SignalP 6) is given only the proteins it has not seen. Each protein is recognised by a SHA-256 hash of its
				sequence, together with a key for the tool's container, database and settings; the rows for known proteins are merged back in under this
				genome's gene ids. A new database release or changed settings change the key, and those proteins are annotated again. This is what speeds
				up a new genome that shares many proteins with genomes already run.
			</p>
			<h3>Which applies when</h3>
			<p>
				The genome level is tried first; a tool it does not cover for this genome then uses the protein level. Genomes whose genes Prodigal calls
				run each step fresh. Scoring, the fingerprints and the comparisons with other genomes run fresh in each run, as they depend on every
				genome in the database at the time.
			</p>
		</section>

		<section class="ab-box">
			<h2>What comes out</h2>
			<ul>
				<li><b>FINAL_ANNOTATION_WITH_CONFIDENCE.tsv</b>: every gene's label, where it came from, its location and topology, C1 to C4 with their reasoning, its confidence and tier.</li>
				<li>A GFF of the annotation, and each tool's own results.</li>
				<li>Gene and operon fingerprints, and an interactive genome map coloured by operon (Results).</li>
				<li>Everything is also kept in the MARGIE database, so later runs reuse what is known.</li>
			</ul>
		</section>
	</div>
</div>
