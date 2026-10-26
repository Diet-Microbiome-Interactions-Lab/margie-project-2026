<script lang="ts">
	import { ArrowRight, Compass } from 'lucide-svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * How to set up MARGIE, in Guided mode: setting up and running as numbered steps that rise in
	 * one after another (as Home's Learn more does), then sharing one setup with a lab, the
	 * defaults, and what to back up. In Simple mode it offers Guided mode instead. Opened from
	 * Home's button and from the working folder setup; not in the sidebar.
	 */

	/** Setting up, in order: what each step is, and where it is done. */
	const SETUP = [
		{
			title: 'Connect your cluster account',
			text: 'Sign up with your cluster’s address and your username. Make a key for MARGIE with ssh-keygen and add its public half to ~/.ssh/authorized_keys; the sign-up page shows the commands.'
		},
		{
			title: 'Set up your working folder',
			text: 'MARGIE asks for it first: margie in your scratch by default. One click makes margie-input, margie-output and margie-databases in it, and sif and reference-databases/db when your group’s cannot be read.',
			to: '/analyze',
			go: 'Open Analyze'
		},
		{
			title: 'Set your SLURM account',
			text: 'Settings → Cluster: the account your jobs run under and the main partition. GTDB-Tk needs a large-memory partition (about 400 GB), set under Phases.',
			to: '/settings#cluster',
			go: 'Open Settings'
		},
		{
			title: 'Containers and reference databases',
			text: 'Install shows what a run needs. Your group’s are used where they are; otherwise Install copies what it can and builds the rest with margie-build. This is the long part: many hours.',
			to: '/install',
			go: 'Open Install'
		},
		{
			title: 'MARGIE’s databases',
			text: 'The first run sets up margie-databases as a short SLURM job: a copy of your group’s base databases, or new ones where your account reads none. Settings → Databases can start fresh ones.',
			to: '/settings#databases',
			go: 'Open Databases'
		},
		{
			title: 'Test it',
			text: 'Install’s self-test sends a small job to SLURM and shows how it went, so you know the setup works before a real run.',
			to: '/install',
			go: 'Run the self-test'
		}
	];

	/** Running, once set up. */
	const RUN = [
		{ title: 'Add your genomes', text: 'Drop FASTA files (.fna, .fa, .fasta) on Genomes, on Analyze. They go into margie-input.' },
		{ title: 'Check gene calling and the tools', text: 'Recommended settings are applied; unlock them only to change them. Accept the licence terms once, before the first run.' },
		{ title: 'Start the run', text: 'Each step goes to SLURM. Jobs follows the run genome by genome, with its log.' },
		{ title: 'Read the results', text: 'Results shows each genome’s map, every gene with its confidence tier, and the tables to download.' }
	];

	/** One setup for a whole lab. */
	const LAB = [
		'One person sets up the containers, the reference databases and margie-build in the group’s shared folder (a depot folder, for example), with the base databases under it.',
		'They make the folder readable by the group (chmod -R g+rX on it).',
		'Each member points Containers and Reference databases (Settings → Folders) there, and sets the Group folder (Settings → Databases).',
		'Each member keeps their own working folder: genomes, results and MARGIE’s databases stay per person.'
	];

	/** Each default, and where it is changed. */
	const DEFAULTS = [
		{ what: 'Working folder', value: '/scratch/<cluster>/<you>/margie', where: 'Settings → Folders' },
		{ what: 'Genomes | results', value: 'margie-input | margie-output, in the working folder', where: 'Settings → Folders' },
		{ what: 'MARGIE’s databases', value: 'margie-databases, in the working folder', where: 'Settings → Folders' },
		{ what: 'Containers', value: 'Your group’s, else sif in the working folder', where: 'Settings → Folders' },
		{ what: 'Reference databases', value: 'Your group’s, else reference-databases/db in the working folder', where: 'Settings → Folders' },
		{ what: 'margie-build', value: 'The folder you name, else your group’s, else ~/margie-build', where: 'Settings → Folders' }
	];

	/** What to back up once it is made. */
	const KEEP = [
		{ title: 'Containers and reference databases', text: 'Copy sif and reference-databases/db to your group’s shared space, then point Settings → Folders at the copies.' },
		{ title: 'MARGIE’s databases', text: 'Back them up from Settings → Databases; they grow with each run.' },
		{ title: 'Results', text: 'Copy what you need out of scratch: many clusters clear files there that go unused for a while.' }
	];
</script>

<svelte:head><title>How to set up MARGIE | MARGIE</title></svelte:head>

<div class="cr-page sg" data-shade="page-setup">
	<div class="cr-head">
		<h1 class="cr-title">How to set up MARGIE</h1>
		<p class="cr-lede">For you alone or for a whole lab: what to prepare, what MARGIE sets up on her own, and what to keep once it is done.</p>
	</div>

	{#if !ui.guided}
		<section class="sg-card sg-simple">
			<span class="sg-ic" aria-hidden="true"><Compass size={18} /></span>
			<div>
				<b>The setup guide is part of Guided mode.</b>
				<p>Guided mode explains each page as you go, and shows this guide step by step.</p>
			</div>
			<button type="button" class="mg-btn primary" onclick={() => ui.update({ mode: 'guided' })}>Switch to Guided</button>
		</section>
	{:else}
		<section class="sg-sec" aria-labelledby="sg-setup">
			<h2 id="sg-setup">Setting up</h2>
			<ol class="sg-steps">
				{#each SETUP as s, i (s.title)}
					<li style="--i: {i}">
						<span class="sg-num">{i + 1}</span>
						<strong>{s.title}</strong>
						<span class="sg-text">{s.text}</span>
						{#if s.to}<a class="sg-go" href={uiBase.to(s.to)}>{s.go} <ArrowRight size={14} /></a>{/if}
					</li>
				{/each}
			</ol>
		</section>

		<section class="sg-sec" aria-labelledby="sg-run">
			<h2 id="sg-run">Running MARGIE</h2>
			<ol class="sg-steps sg-four">
				{#each RUN as s, i (s.title)}
					<li style="--i: {i + 2}">
						<span class="sg-num">{i + 1}</span>
						<strong>{s.title}</strong>
						<span class="sg-text">{s.text}</span>
					</li>
				{/each}
			</ol>
			<div class="sg-card sg-cache">
				<b>MARGIE’s cache</b>
				<span
					>Genomes and proteins annotated before come back from MARGIE’s database with their processed tables, so their tools do not run
					again; <span class="mg-mono">cache-report.tsv</span>, in each run folder, says which steps came from the cache. Those steps have no
					raw output in <span class="mg-mono">original_container_outputs</span>. When you need it, unlock <b>Run without the cache</b> under the Run
					button on Analyze: the next run runs each tool again and keeps its raw output.</span
				>
			</div>
			<a class="mg-btn primary sg-start" href={uiBase.to('/analyze')}>Start on Analyze <ArrowRight size={15} /></a>
		</section>

		<section class="sg-sec" aria-labelledby="sg-lab">
			<h2 id="sg-lab">For a whole lab</h2>
			<div class="sg-card">
				<p class="sg-lead">A lab can share one setup, so the long part is done once:</p>
				<ol class="sg-points">
					{#each LAB as p, i (p)}<li style="--i: {i}">{p}</li>{/each}
				</ol>
				<p class="sg-note">Individual setups are your choice: you can set up your own containers and databases in your working folder instead, at the cost of the hours and the space again.</p>
			</div>
		</section>

		<div class="sg-two">
			<section class="sg-sec" aria-labelledby="sg-defaults">
				<h2 id="sg-defaults">Defaults</h2>
				<div class="sg-card sg-table">
					{#each DEFAULTS as d, i (d.what)}
						<div class="sg-row" style="--i: {i}">
							<b>{d.what}</b>
							<span class="mg-mono">{d.value}</span>
							<span class="sg-where">{d.where}</span>
						</div>
					{/each}
				</div>
			</section>
			<section class="sg-sec" aria-labelledby="sg-keep">
				<h2 id="sg-keep">Keep what took long</h2>
				<div class="sg-card">
					{#each KEEP as k, i (k.title)}
						<div class="sg-keep" style="--i: {i}">
							<b>{k.title}</b>
							<span>{k.text}</span>
						</div>
					{/each}
				</div>
			</section>
		</div>
	{/if}
</div>

<style>
	.sg {
		display: flex;
		flex-direction: column;
		gap: 26px;
	}
	.sg-sec {
		display: flex;
		flex-direction: column;
		gap: 12px;
		animation: fade calc(220ms * var(--mo-k, 1)) ease-out both;
	}
	.sg-sec h2 {
		margin: 0;
		font-size: var(--mg-fs-md, 1.05rem);
		font-weight: 650;
	}
	.sg-card {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 16px 18px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
	}

	/* ---- numbered steps that rise in one after another ---- */
	.sg-steps {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.sg-steps.sg-four {
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}
	.sg-steps li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		grid-template-rows: auto 1fr auto;
		gap: 4px 12px;
		padding: 14px 16px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		animation: rise calc(320ms * var(--mo-k, 1)) ease-out both;
		animation-delay: calc(var(--i) * 70ms * var(--mo-k, 1));
	}
	.sg-num {
		grid-row: span 3;
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: 12px;
		font-weight: 700;
	}
	.sg-steps strong {
		font-weight: 650;
	}
	.sg-text {
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
		line-height: 1.5;
	}
	.sg-go {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		margin-top: 4px;
		font-size: var(--mg-fs-sm);
		font-weight: 600;
		color: var(--mg-accent-ink, var(--mg-accent));
		text-decoration: none;
	}
	.sg-go:hover {
		text-decoration: underline;
	}
	.sg-cache {
		gap: 4px;
		font-size: var(--mg-fs-sm);
		animation: rise calc(320ms * var(--mo-k, 1)) ease-out both;
		animation-delay: calc(6 * 70ms * var(--mo-k, 1));
	}
	.sg-cache > span {
		color: var(--mg-text-2);
		line-height: 1.5;
	}
	.sg-start {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		align-self: flex-start;
		text-decoration: none;
	}

	/* ---- the lab, the defaults, what to keep ---- */
	.sg-lead {
		margin: 0;
		font-weight: 600;
	}
	.sg-points {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding-left: 20px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.sg-points li {
		animation: rise calc(280ms * var(--mo-k, 1)) ease-out both;
		animation-delay: calc(80ms + var(--i) * 60ms * var(--mo-k, 1));
	}
	.sg-note {
		margin: 0;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.sg-two {
		display: grid;
		grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
		gap: 20px;
		align-items: start;
	}
	.sg-table {
		gap: 0;
		padding: 4px 18px;
	}
	.sg-row {
		display: grid;
		grid-template-columns: 9.5em minmax(0, 1fr);
		gap: 2px 12px;
		padding: 9px 0;
		border-bottom: 1px solid var(--cr-rule, var(--mg-border));
		font-size: var(--mg-fs-sm);
		animation: rise calc(260ms * var(--mo-k, 1)) ease-out both;
		animation-delay: calc(var(--i) * 50ms * var(--mo-k, 1));
	}
	.sg-row:last-child {
		border-bottom: 0;
	}
	.sg-row .mg-mono {
		font-size: var(--mg-fs-xs);
		overflow-wrap: anywhere;
	}
	.sg-where {
		grid-column: 2;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.sg-keep {
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-size: var(--mg-fs-sm);
		animation: rise calc(260ms * var(--mo-k, 1)) ease-out both;
		animation-delay: calc(var(--i) * 60ms * var(--mo-k, 1));
	}
	.sg-keep span {
		color: var(--mg-text-2);
	}

	/* ---- Simple mode ---- */
	.sg-simple {
		flex-direction: row;
		flex-wrap: wrap;
		align-items: center;
		gap: 12px 16px;
	}
	.sg-simple div {
		flex: 1 1 280px;
	}
	.sg-simple p {
		margin: 2px 0 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.sg-ic {
		display: inline-flex;
		color: var(--mg-accent-ink, var(--mg-accent));
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	:global([data-motion='off']) .sg * {
		animation: none !important;
	}
	@media (max-width: 1100px) {
		.sg-steps,
		.sg-steps.sg-four {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.sg-two {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	@media (max-width: 640px) {
		.sg-steps,
		.sg-steps.sg-four {
			grid-template-columns: minmax(0, 1fr);
		}
		.sg-row {
			grid-template-columns: minmax(0, 1fr);
		}
		.sg-where {
			grid-column: 1;
		}
	}
</style>
