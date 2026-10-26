<script lang="ts">
	import { ArrowRight, ChartPie, FolderOpen, ListChecks, Maximize2, Package, Play, SlidersHorizontal, SquareTerminal, X } from 'lucide-svelte';
	import { clusterParts } from '$lib/workspace/cluster-parts';
	import { backend } from '$lib/workspace/backend.svelte';
	import { uiBase } from '../base.svelte';
	import { ui } from '../ui.svelte';
	import TabPicture from './home/TabPicture.svelte';
	import LogoPuzzle from '../LogoPuzzle.svelte';
	import MargieLogo from '../MargieLogo.svelte';
	import { LOGO_PUZZLE } from '$lib/features';

	/**
	 * Home: the logo, what MARGIE is, and where to start; under Learn more, what a run does,
	 * what comes out, and a drawing of each page; at the bottom, links to Contributors and Acknowledgements.
	 */

	/** The pages, in the sidebar's order, each with what it is for. */
	const TABS = [
		{ id: 'analyze', label: 'Analyze', icon: Play, to: '/analyze', points: ['Add FASTA files, and give each genome its domain and genetic code (or let GTDB-Tk)', 'Choose the tools; tick the genomes to run, or press and drag to tick many', 'Each genome’s progress fills in as the tools finish'] },
		{ id: 'jobs', label: 'Jobs', icon: ListChecks, to: '/jobs', points: ['One line per job: name, id and status', 'Each genome’s progress beside it, with the time left', 'The log underneath; resume or restart a failed run'] },
		{ id: 'results', label: 'Results', icon: ChartPie, to: '/results', points: ['A genome map, coloured by confidence', 'Every gene: its name, evidence and confidence tier', 'The tables as Excel or TSV, with the figures'] },
		{ id: 'files', label: 'Files', icon: FolderOpen, to: '/files', points: ['Your folders on the cluster', 'Tables, logs, pages and images open in place', 'Download any file'] },
		{ id: 'terminal', label: 'Terminal', icon: SquareTerminal, to: '/terminal', points: ['A shell on your cluster account', 'Quick commands: squeue, ls, less', 'Long work goes to SLURM with sbatch'] },
		{ id: 'install', label: 'Install', icon: Package, to: '/install', points: ['What a run needs, and whether it is ready', 'Copy or build missing containers and databases', 'Accept the tools’ licences'] },
		{ id: 'settings', label: 'Settings', icon: SlidersHorizontal, to: '/settings', points: ['Folders, cores, memory and time', 'Per-tool settings in one table, by phase', 'Databases, and their backups'] }
	] as const;

	/** What a run does, in order. */
	const ORDER = [
		{ title: 'Find the genes', text: 'RASTtk or Prodigal marks every protein-coding gene in each genome.' },
		{ title: 'Read each protein', text: 'The annotation tools compare every protein with their reference databases.' },
		{ title: 'Weigh the evidence', text: 'Genes are grouped into operons, and each gets a name and a confidence tier.' }
	];

	let open = $state<string | null>(null);
	/** What a run does and what each page does: behind Learn more, open by itself in Guided mode. */
	let more = $state(false);
	const detailed = $derived(more || ui.guided);
	/** Whether the map is full screen. */
	let full = $state(false);
	const mapSrc = $derived(ui.dark ? '/home/genome-map-dark.webp' : '/home/genome-map.jpg');
	/** Moves the full-screen map to the interface root so it covers the whole window. */
	function toRoot(node: HTMLElement) {
		(node.closest('[data-mg-root]') ?? document.body).appendChild(node);
		return { destroy: () => node.remove() };
	}
	const shown = $derived(TABS.find((t) => t.id === open));
	const toggle = (id: string) => (open = open === id ? null : id);

	/** Closes the open card on a click outside the tiles and the card. */
	function outside(e: MouseEvent) {
		if (open && !(e.target as Element | null)?.closest?.('[data-home-keep]')) open = null;
	}

</script>

<svelte:window
	onclick={outside}
	onkeydown={(e) => {
		if (e.key !== 'Escape') return;
		if (full) full = false;
		else open = null;
	}}
/>

<div class="home">
	<section class="hero">
		<!-- The logo turns in and turns again under the pointer; with LOGO_PUZZLE on, a click breaks it into a jigsaw. -->
		{#if LOGO_PUZZLE}
			<LogoPuzzle size="clamp(220px, 24vw, 300px)" />
		{:else}
			<h1 class="logo-h1"><MargieLogo size="clamp(220px, 24vw, 300px)" /></h1>
		{/if}
		<p class="full">Mostly Automated Rapid Genome Inference Environment</p>
		<p class="motto">Annotate with confidence: a genome-centric, context-dependent approach</p>
		<div class="cta">
			<a class="pill primary" href="/analyze"><Play size={15} /> Start annotating</a>
			<a class="pill" href={uiBase.to('/results')}>See results</a>
			{#if !ui.guided}
				<button type="button" class="pill quiet" aria-pressed={more} aria-controls="home-more" onclick={() => (more = !more)}>
					{more ? 'Show less' : 'Learn more'}
				</button>
			{/if}
		</div>
	</section>

	{#if detailed}
		<div id="home-more" class="more">
			<div class="run">
				<section class="steps" aria-labelledby="steps-title">
					<h2 id="steps-title">What a run does</h2>
					<ol>
						{#each ORDER as o, i (o.title)}
							<li style="--i: {i}">
								<span class="num">{i + 1}</span>
								<strong>{o.title}</strong>
								<span>{o.text}</span>
							</li>
						{/each}
					</ol>
				</section>
				<figure class="outcome">
					<h2>What comes out</h2>
					<button type="button" class="map-btn" aria-label="Show the map full screen" title="Full screen" onclick={() => (full = true)}>
						<img src={mapSrc} alt="Circular genome map of Sedimenticola thiotaurini, coloured by operon" loading="lazy" />
						<span class="zoom" aria-hidden="true"><Maximize2 size={14} /></span>
					</button>
					<figcaption>A map of each genome, coloured by operon, with a report on every gene.</figcaption>
				</figure>
			</div>

			<section class="guide" aria-labelledby="guide-title">
				<h2 id="guide-title">What each page does</h2>
				<div class="tabs" role="group" aria-label="What each page does" data-home-keep>
					{#each TABS as t (t.id)}
						<button type="button" class="tab" aria-expanded={open === t.id} aria-controls="home-card" onclick={() => toggle(t.id)}>
							<t.icon size={16} /><span>{t.label}</span>
						</button>
					{/each}
				</div>
				{#if shown}
					<div id="home-card" class="stage" data-home-keep>
						{#key shown.id}
							<div class="card-in">
								<div class="picture"><TabPicture tab={shown.id} /></div>
								<div class="words">
									<h3>{shown.label}</h3>
									<ol class="points">
										{#each shown.points as p, i (p)}
											<li style="--i: {i}">{p}</li>
										{/each}
									</ol>
									<a class="pill primary go" href={uiBase.to(shown.to)}>Open {shown.label} <ArrowRight size={15} /></a>
								</div>
								<button type="button" class="close" aria-label="Close" onclick={() => (open = null)}><X size={16} /></button>
							</div>
						{/key}
					</div>
				{/if}
			</section>

		<footer class="foot">
			<p>
				Who made MARGIE, how to cite it and the tools it runs:
				<a class="mg-link" href={uiBase.to('/contributors')}>Contributors</a> |
				<a class="mg-link" href={uiBase.to('/acknowledgements')}>Acknowledgements</a>
			</p>
		</footer>
		</div>
	{/if}

	{#if full}
		<div class="lightbox" role="dialog" aria-modal="true" aria-label="Genome map, full screen" use:toRoot>
			<button type="button" class="lb-back" aria-label="Close" onclick={() => (full = false)}></button>
			<img src={mapSrc} alt="Circular genome map of Sedimenticola thiotaurini, coloured by operon" />
			<button type="button" class="close lb-close" aria-label="Close" onclick={() => (full = false)}><X size={18} /></button>
		</div>
	{/if}

	{#if clusterParts.Compute && ui.explain}
		<section class="hpc-note" aria-labelledby="hpc-note-t">
			<h2 id="hpc-note-t">On an HPC: where MARGIE works</h2>
			<div class="hpc-cols">
				<p>
					<b>Login node</b> (the default). Browsing, the genome maps and chat run on the node you signed in to, and annotation runs go to SLURM.
				</p>
				<p>
					<b>Compute node.</b> Choose it with the <i>Login node / Compute node</i> button at the top to run MARGIE's server as a SLURM job.
					{#if !backend.cluster}
						The button appears once you are connected to an HPC{#if clusterParts.switchHref}: <a class="mg-link" href={clusterParts.switchHref}>connect</a>{/if}.
					{/if}
				</p>
				<p><b>Copies</b>, such as reference data the first time or a backup, go to SLURM when an account is set.</p>
			</div>
		</section>
	{/if}


</div>

<style>
	.home {
		display: flex;
		flex-direction: column;
		gap: 28px;
		width: 100%;
		max-width: 1180px;
		margin: 0 auto;
		padding: 36px var(--cr-gutter, 24px) 48px;
		color: var(--mg-text);
	}
	p {
		margin: 0;
		line-height: 1.55;
	}
	h2 {
		margin: 0 0 12px;
		font-size: var(--mg-fs-xs);
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}

	/* ---- the opening: the logo, centred, and where to start ---- */
	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		padding: 28px 16px 8px;
		text-align: center;
	}
	.hero > * {
		animation: rise 520ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
	}
	.hero > :nth-child(2) {
		animation-delay: 80ms;
	}
	.hero > :nth-child(3) {
		animation-delay: 140ms;
	}
	.hero > :nth-child(4) {
		animation-delay: 200ms;
	}
	.logo-h1 {
		margin: 0;
		line-height: 0;
	}
	.full {
		font-size: 1.15rem;
		font-weight: 600;
	}
	.motto {
		max-width: 60ch;
		color: var(--mg-text-2);
	}
	.cta {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 10px;
		margin-top: 10px;
	}
	.pill {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		height: 36px;
		padding: 0 16px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-accent-ink, var(--mg-accent));
		font: inherit;
		font-weight: 600;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
		transition:
			border-color 140ms,
			background 140ms;
	}
	.pill:hover {
		border-color: var(--mg-accent);
	}
	.pill.primary {
		border-color: var(--mg-accent);
		background: var(--mg-accent);
		color: var(--mg-on-accent);
	}
	.pill.primary:hover {
		filter: brightness(1.06);
	}
	.pill.quiet {
		border-color: var(--mg-border);
		color: var(--mg-text-2);
	}
	.pill.quiet[aria-pressed='true'] {
		border-color: color-mix(in srgb, var(--mg-accent) 40%, var(--mg-border));
		background: color-mix(in srgb, var(--mg-accent) 10%, var(--mg-surface));
		color: var(--mg-accent-ink);
	}
	/* The platform's line, quiet, between the opening and the notes. */
	/* ---- Learn more ---- */
	.more {
		display: flex;
		flex-direction: column;
		gap: 28px;
		animation: fade 220ms ease-out both;
	}
	.run {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 20px;
		align-items: start;
	}
	.outcome {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 0;
	}
	.map-btn {
		position: relative;
		display: block;
		padding: 10px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		cursor: zoom-in;
	}
	.map-btn img {
		display: block;
		width: 100%;
		height: auto;
		mix-blend-mode: multiply;
	}
	:global([data-theme='dark']) .map-btn img {
		mix-blend-mode: normal;
	}
	.map-btn .zoom {
		position: absolute;
		top: 10px;
		right: 10px;
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-text-2);
		opacity: 0;
		transition: opacity 140ms;
	}
	.map-btn:hover .zoom,
	.map-btn:focus-visible .zoom {
		opacity: 1;
	}
	figcaption {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.steps ol {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 12px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.steps li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 4px 12px;
		padding: 14px 16px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		animation: rise 320ms ease-out both;
		animation-delay: calc(var(--i) * 70ms);
	}
	.steps .num {
		grid-row: span 2;
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink);
		font-size: 12px;
		font-weight: 700;
	}
	.steps strong {
		font-weight: 650;
	}
	.steps li > span:last-child {
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.tabs {
		display: grid;
		grid-template-columns: repeat(8, minmax(0, 1fr));
		gap: 8px;
	}
	.tab {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 7px;
		height: 40px;
		padding: 0 8px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
	}
	.tab:hover {
		border-color: var(--mg-border-strong);
		color: var(--mg-text);
	}
	.tab[aria-expanded='true'] {
		border-color: var(--mg-accent);
		color: var(--mg-accent-ink);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-accent) 16%, transparent);
	}
	.stage {
		position: relative;
		margin-top: 12px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
	}
	.card-in {
		display: grid;
		grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
		gap: 28px;
		align-items: center;
		padding: 22px 26px;
		animation: fade 220ms ease-out both;
	}
	.picture {
		width: 100%;
		max-width: 460px;
		justify-self: center;
	}
	.words {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	h3 {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 700;
	}
	.points {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 0 0 0 18px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.points li {
		animation: rise 260ms ease-out both;
		animation-delay: calc(60ms + var(--i) * 50ms);
	}
	.go {
		align-self: flex-start;
	}
	.close {
		position: absolute;
		top: 10px;
		right: 10px;
		display: grid;
		place-items: center;
		width: 30px;
		height: 30px;
		border: 1px solid var(--mg-border);
		border-radius: 50%;
		background: var(--mg-surface);
		color: var(--mg-text-2);
		cursor: pointer;
	}
	.close:hover {
		color: var(--mg-text);
	}

	/* ---- the map, full screen ---- */
	.lightbox {
		position: fixed;
		inset: 0;
		z-index: 50;
		display: grid;
		place-items: center;
		padding: 24px;
		animation: fade 180ms ease-out both;
	}
	.lb-back {
		position: absolute;
		inset: 0;
		border: none;
		background: var(--mg-bg);
		cursor: zoom-out;
	}
	.lightbox img {
		position: relative;
		max-width: calc(100vw - 64px);
		max-height: calc(100vh - 64px);
		object-fit: contain;
		border-radius: var(--mg-r-sm);
		box-shadow: 0 10px 40px rgb(0 0 0 / 0.18);
		background: var(--mg-surface);
	}
	.lb-close {
		position: absolute;
		top: 16px;
		right: 16px;
	}

	/* ---- on an HPC (desktop app) ---- */
	.hpc-note {
		padding: 14px 18px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
	}
	.hpc-cols {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 18px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.hpc-cols b {
		font-weight: 600;
		color: var(--mg-text);
	}

	/* ---- credits and how to cite, side by side ---- */
	.foot {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
		text-align: center;
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
	:global([data-motion='off']) .home * {
		animation: none !important;
	}

	@media (max-width: 980px) {
		.run,
		.card-in {
			grid-template-columns: minmax(0, 1fr);
		}
		.tabs {
			grid-template-columns: repeat(4, minmax(0, 1fr));
		}
		}
	@media (max-width: 640px) {
		.steps ol,
		.hpc-cols {
			grid-template-columns: minmax(0, 1fr);
		}
		.tabs {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
