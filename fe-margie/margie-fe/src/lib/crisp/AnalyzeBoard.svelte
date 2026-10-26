<script lang="ts">
	import { ArrowRight, RotateCcw, Square } from 'lucide-svelte';
	import type { Run } from '$lib/api';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import BuildBar from '$lib/workspace/blocks/BuildBar.svelte';
	import GenomesBoard from '$lib/crisp/GenomesBoard.svelte';
	import RunAction from '$lib/workspace/blocks/RunAction.svelte';
	import Licence from '$lib/cluster/Licence.svelte';
	import RunSteps from './RunSteps.svelte';

	/**
	 * The Analyze page, in the order a run is set up: 1 the genomes (folder, files, table),
	 * 2 gene calling and 3 the annotation tools (RunSteps), the licence terms once before a
	 * first run, then the start button (or the run's bar with Stop and Go to Jobs, or Resume
	 * and Restart after a failed run). A run's progress by genome and step is on Jobs.
	 */
	const GENOME_TABLE = 'analyze:genome-table';

	/** On the cluster, your databases' state (the page's checklist says when a first run copies them). */
	$effect(() => {
		if (backend.cluster) ws.loadStores();
	});

	/** On the cluster, the licence terms are accepted once, here, before a first run. */
	const needsTerms = $derived(!!backend.cluster && ws.setup.some((r) => r.id === 'terms' && r.tone !== 'ok'));
	/** Folded until opened, like the other steps; the start button's note links here. */
	const LICENCE = 'analyze:licence';

	// ---------------------------------------------------------------- the run
	/** The annotation going now, if any. */
	const run = $derived(ws.active?.kind === 'annotate' ? ws.active : null);
	const p = $derived(run ? ws.progress : null);
	const pct = $derived(p ? p.fraction * 100 : (run?.progress ?? 0));
	const runText = $derived.by(() => {
		if (!p) return run?.progressText ?? '';
		const done = p.genomes.filter((g) => g.state === 'done').length;
		return `${done} of ${p.genomes.length} genomes${p.current ? ` | ${p.current}` : ''}${p.detail ? ` | ${p.detail}` : ''}`;
	});
	/** The last annotation, when it ended badly and nothing has run since. */
	const lastBad = $derived.by((): Run | null => {
		if (ws.running.length) return null;
		const last = ws.runs.filter((r) => r.kind === 'annotate').sort((a, b) => b.started.localeCompare(a.started))[0];
		return last && (last.status === 'failed' || last.status === 'cancelled') ? last : null;
	});
	let acting = $state(false);
	async function stopRun() {
		if (!run || !confirm('Stop this run now? What has finished is kept, and Resume picks up from there.')) return;
		await ws.stop(run.id);
	}
	async function resume(r: Run) {
		acting = true;
		if (await ws.resume(r)) ui.notify('Resumed', 'ok');
		acting = false;
	}
	async function restart(r: Run) {
		if (!confirm('Start this run again from the beginning, with the same genomes and tools?')) return;
		acting = true;
		if (await ws.restart(r)) ui.notify('Restarted', 'ok');
		acting = false;
	}

</script>

<div class="analyze">
<!-- The steps in one card, one row each (an-steps), the run under them. -->
<div class="an-steps">
<!-- ------------------------------------------------ 1. the genomes: their folder, files added here, the table -->
<section id="genomes" class="genomes" aria-label="Genomes">
	<GenomesBoard foldId={GENOME_TABLE} step={1} />
</section>

<!-- ------------------------------------------------ 2. gene calling, 3. annotation tools -->
<RunSteps />

<!-- ------------------------------------------------ once, before a first run: the licence terms (recorded on the cluster) -->
{#if needsTerms}
	<section class="card licbox" class:folded={ui.isFolded(LICENCE, true)} id="licence" aria-labelledby="lic-h">
		<header class="lichead">
			<span class="stepn">4</span>
			<h2 id="lic-h">Licence terms</h2>
			<span class="lic-need">Not accepted yet: needed once, before your first run</span>
			<span class="mg-grow"></span>
			<button type="button" class="mg-link quiet" aria-expanded={!ui.isFolded(LICENCE, true)} onclick={() => ui.toggleFold(LICENCE, true)}>{ui.isFolded(LICENCE, true) ? 'Show' : 'Hide'}</button>
		</header>
		{#if !ui.isFolded(LICENCE, true)}<Licence />{/if}
	</section>
{/if}
</div>

<!-- ------------------------------------------------ the run -->
<section class="card runcard" id="run">
	{#if run}
		<BuildBar percent={pct} label={p?.stage ?? 'Annotating'} text={runText} />
		<div class="acts">
			<a class="mg-link quiet" href={uiBase.to(`/jobs?job=${encodeURIComponent(run.id)}`)}>Log</a>
			<span class="mg-grow"></span>
			<a class="pill" href={uiBase.to(`/jobs?job=${encodeURIComponent(run.id)}`)} title="This job on the Jobs page: its progress by genome, its log and its command">Go to Jobs <ArrowRight size={13} strokeWidth={2.5} /></a>
			<button type="button" class="pill stop" onclick={stopRun}><Square size={12} strokeWidth={2.5} /> Stop</button>
		</div>
	{:else}
		{#if lastBad}
			<div class="bad" role="status">
				<p>
					<b>Last run {lastBad.status === 'cancelled' ? 'was stopped' : 'failed'}.</b>
					{#if lastBad.reason && lastBad.status === 'failed'}<span class="why" title={lastBad.reason}>{lastBad.reason}</span>{/if}
				</p>
				<div class="acts">
					<a class="mg-link quiet" href={uiBase.to(`/jobs?job=${encodeURIComponent(lastBad.id)}`)}>Log</a>
					<span class="mg-grow"></span>
					{#if backend.cluster}
						<button type="button" class="pill" disabled={acting} onclick={() => restart(lastBad as Run)}>Restart</button>
					{/if}
					<button
						type="button"
						class="pill solid"
						disabled={acting}
						title="Run the same genomes and tools again; what finished is reused, not run again"
						onclick={() => resume(lastBad as Run)}
					>
						<RotateCcw size={13} strokeWidth={2.5} /> Resume
					</button>
				</div>
			</div>
		{/if}
	{/if}
	<!-- Another run can start beside one that is going (each has its own folder). -->
	<RunAction />
</section>
</div>

<style>
	/* The steps one under another, a gutter apart. */
	.analyze {
		display: flex;
		flex-direction: column;
		gap: var(--cr-stack, 16px);
	}
	.card {
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		color: var(--mg-text);
		background: var(--cr-card, var(--mg-surface));
		box-shadow: var(--cr-card-shadow, none);
	}

	/* The steps: one card, a hairline between them, instead of a box each. */
	.an-steps {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		box-shadow: var(--cr-card-shadow, none);
	}
	.genomes {
		display: flex;
		flex-direction: column;
	}
	.an-steps :global(:is(.gb-board, .rs-box)),
	.an-steps .licbox {
		border: none;
		border-radius: 0;
		background: transparent;
		box-shadow: none;
	}
	.an-steps :global(.gb-board + .gb-board),
	.an-steps > :global(.rs-box),
	.an-steps > .licbox {
		border-top: 1px solid var(--mg-border);
	}
	/* The steps line up as columns: number | title | what it is set to, then its controls at the
	   right. Each title takes the same width (the longest, Annotation tools), and the gaps match. */
	.an-steps {
		--an-title: 9.5rem;
	}
	.an-steps :global(:is(.gb-board, .rs-box)),
	.an-steps .licbox {
		padding-left: 18px;
		padding-right: 18px;
	}
	.an-steps :global(:is(.gb-top, .rs-head)),
	.lichead {
		column-gap: 10px;
	}
	.an-steps :global(:is(.gb-colhead, .rs-head > h2)),
	.lichead h2 {
		flex: 0 0 var(--an-title);
		white-space: nowrap;
	}
	/* On a phone, a step's summary goes under its title, so its Show stays on the title's line. */
	@media (max-width: 640px) {
		.an-steps :global(:is(.gb-top, .rs-head)),
		.lichead {
			flex-wrap: wrap;
			row-gap: 2px;
		}
		.an-steps :global(:is(.gb-colhead, .rs-head > h2)),
		.lichead h2 {
			flex-basis: auto;
		}
		.an-steps :global(:is(.gb-count, .gb-sum, .rs-sum)),
		.lic-need {
			order: 10;
			flex-basis: 100%;
			padding-left: 32px;
		}
	}
	/* Files dragged over the genomes: their row lights, not a box. */
	.an-steps :global(.gb-board.over) {
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
		box-shadow: inset 3px 0 0 var(--mg-accent);
	}

	/* ---------------------------------------- the licence terms, once */
	.licbox {
		padding: 16px 18px;
	}
	.licbox.folded {
		padding-top: 10px;
		padding-bottom: 10px;
	}
	.lichead {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 8px;
	}
	.lichead h2 {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.lichead {
		margin-bottom: 0;
	}
	.licbox:has(.lic-need) .lichead + :global(*) {
		margin-top: 8px;
	}
	.lic-need {
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-warn);
	}
	.stepn {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: var(--mg-fs-xs);
		font-weight: 700;
	}


	/* ---------------------------------------- the run */
	.runcard {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: var(--cr-box-pad, 16px 18px);
	}
	.acts {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px;
	}
	.pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		height: 30px;
		padding: 0 14px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: transparent;
		color: var(--mg-accent-ink, var(--mg-accent));
		font: inherit;
		font-size: var(--mg-fs-sm);
		font-weight: 500;
		text-decoration: none;
		cursor: pointer;
	}
	.pill:hover:not(:disabled) {
		background: color-mix(in srgb, var(--mg-accent) 10%, transparent);
	}
	.pill.solid {
		border-color: transparent;
		background: var(--mg-accent);
		color: var(--mg-on-accent, #fff);
	}
	.pill.solid:hover:not(:disabled) {
		background: var(--mg-accent);
		filter: brightness(0.95);
	}
	.pill.stop {
		border-color: color-mix(in srgb, var(--mg-danger, #c0392b) 55%, var(--mg-border));
		color: var(--mg-danger, #c0392b);
	}
	.pill.stop:hover {
		background: color-mix(in srgb, var(--mg-danger, #c0392b) 10%, transparent);
	}
	.pill:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.bad {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid color-mix(in srgb, var(--mg-warn) 45%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-warn) 6%, transparent);
		font-size: var(--mg-fs-sm);
	}
	.bad p {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 0;
		min-width: 0;
	}
	.bad b {
		font-weight: 500;
	}
	.why {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
</style>
