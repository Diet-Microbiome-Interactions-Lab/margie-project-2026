<script lang="ts">
	import { ArrowRight, Check, RotateCcw, Square } from 'lucide-svelte';
	import type { Run } from '$lib/api';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import BuildBar from '$lib/workspace/blocks/BuildBar.svelte';
	import GenomesBoard from '$lib/crisp/GenomesBoard.svelte';
	import RunAction from '$lib/workspace/blocks/RunAction.svelte';
	import Licence from '$lib/cluster/Licence.svelte';
	import Fold from '$lib/workspace/motion/Fold.svelte';
	import FoldTitle from '$lib/workspace/motion/FoldTitle.svelte';
	import FoldToggle from '$lib/workspace/motion/FoldToggle.svelte';
	import RunSteps from './RunSteps.svelte';
	import WorkingFolderSetup from './WorkingFolderSetup.svelte';

	/**
	 * The Analyze page, in the order a run is set up, one box each as on Install: the genomes
	 * (folders, files, table), gene calling and the annotation tools (RunSteps), the licence terms
	 * once before a first run, then the start button (or the run's bar with Stop and Go to Jobs, or
	 * Resume and Restart after a failed run). A run's progress by genome and step is on Jobs.
	 *
	 * On the cluster these are five steps, taken one after another: the working folder, the
	 * genomes, gene calling and the tools, the licence terms, the run. The step to take is open;
	 * a step done folds to one line (a click opens it again); the steps after it wait, greyed.
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

	// ---------------------------------------------------------------- the steps (on the cluster)
	type StepId = 'folder' | 'genomes' | 'tools' | 'licence' | 'run';
	type Step = { id: StepId; title: string; done: boolean; summary: string };
	const stepped = $derived(!!backend.cluster);
	$effect(() => {
		if (backend.cluster && !ws.firstSetup) void ws.loadSetup();
	});
	/** The working folder comes first: the genomes, results and databases folders go in it. */
	const needsWorking = $derived(!!backend.cluster && (ws.configMissing || (!!ws.firstSetup && !ws.firstSetup.working_folder)));
	const working = $derived(ws.setting('margie_sb.working_folder') || ws.firstSetup?.working_folder || '');
	const genomeFolder = $derived(ws.genomeFolder || ws.setting('USER_INPUT_DIR') || '');
	/** An account that has run before has seen the tools. */
	const ranBefore = $derived(ws.runs.some((r) => r.kind === 'annotate'));
	const lastName = (p: string) => p.replace(/\/+$/, '').split('/').pop() || p;
	const steps = $derived.by((): Step[] => {
		const n = ws.genomes.length;
		const t = ws.chosenTools.length;
		return [
			{ id: 'folder', title: 'Working folder', done: !needsWorking, summary: working },
			{ id: 'genomes', title: 'Genomes', done: n > 0, summary: `${n} genome${n === 1 ? '' : 's'}${genomeFolder ? ` in ${lastName(genomeFolder)}` : ''}` },
			{ id: 'tools', title: 'Gene calling and tools', done: ui.prefs.toolsChecked || ranBefore, summary: t ? `${t} tool${t === 1 ? '' : 's'}` : 'gene calling only' },
			{ id: 'licence', title: 'Licence terms', done: !needsTerms, summary: 'accepted' },
			{ id: 'run', title: 'Run', done: false, summary: '' }
		];
	});
	/** The step to take: the first not done (the run, once the others are). */
	const current = $derived(Math.max(0, steps.findIndex((x) => !x.done)));
	/** Steps done that were opened again. */
	let reopened = $state<Partial<Record<StepId, boolean>>>({});
	const stateOf = (i: number) => (i < current ? 'done' : i === current ? 'current' : 'later');
	const isOpen = (i: number, id: StepId) => i === current || (i < current && !!reopened[id]);
	/** The genomes' box opens with its step. */
	$effect(() => {
		if (stepped && isOpen(1, 'genomes') && ui.isFolded(GENOME_TABLE, true)) ui.toggleFold(GENOME_TABLE, true);
	});

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

{#snippet runCard()}
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
{/snippet}

{#snippet body(id: StepId)}
	{#if id === 'folder'}
		<div class="card step-card"><WorkingFolderSetup bare /></div>
	{:else if id === 'genomes'}
		<p class="step-lead">
			Add your genome FASTA files (.fna, .fa, .fasta): drop them on the box below and they are copied into
			<span class="mg-mono" title={genomeFolder}>{genomeFolder ? lastName(genomeFolder) : 'margie-input'}</span>, or, when they are already on
			the cluster, point the genomes folder at them with Change folders.
		</p>
		<GenomesBoard foldId={GENOME_TABLE} />
	{:else if id === 'tools'}
		<p class="step-lead">The recommended gene calling and tools are set. Unlock a box to change it; a run uses what is saved.</p>
		<RunSteps />
		{#if stateOf(2) === 'current'}
			<div class="step-go">
				<button type="button" class="pill solid" onclick={() => ui.update({ toolsChecked: true })}>Continue <ArrowRight size={13} strokeWidth={2.5} /></button>
			</div>
		{/if}
	{:else if id === 'licence'}
		<div class="card step-card"><Licence /></div>
	{:else}
		{@render runCard()}
	{/if}
{/snippet}

<div class="analyze">
{#if stepped}
	<ol class="steps" aria-label="A run, step by step">
		{#each steps as st, i (st.id)}
			{@const state = stateOf(i)}
			<li class="step {state}" aria-current={state === 'current' ? 'step' : undefined}>
				{#if state === 'done'}
					<button type="button" class="step-head" aria-expanded={!!reopened[st.id]} onclick={() => (reopened = { ...reopened, [st.id]: !reopened[st.id] })}>
						<span class="step-num" aria-hidden="true"><Check size={13} strokeWidth={3} /></span>
						<b>{st.title}</b>
						<span class="step-sum" title={st.summary}>{st.summary}</span>
						<span class="mg-grow"></span>
						<span class="step-change">{reopened[st.id] ? 'Close' : 'Change'}</span>
					</button>
				{:else}
					<div class="step-head">
						<span class="step-num" aria-hidden="true">{i + 1}</span>
						<b>{st.title}</b>
						{#if state === 'later'}<span class="step-sum">after {steps[i - 1].title.toLowerCase()}</span>{/if}
					</div>
				{/if}
				{#if isOpen(i, st.id)}
					<div class="step-body">{@render body(st.id)}</div>
				{/if}
			</li>
		{/each}
	</ol>
{:else}

<!-- ------------------------------------------------ the genomes: their folders, files added here, the table -->
<GenomesBoard foldId={GENOME_TABLE} />

<!-- ------------------------------------------------ gene calling, annotation tools -->
<RunSteps />

<!-- ------------------------------------------------ once, before a first run: the licence terms (recorded on the cluster) -->
{#if needsTerms}
	<section class="mg-card" data-shade="licence" id="licence" aria-labelledby="lic-h">
		<header class="mg-card-head">
			<FoldTitle id={LICENCE} closed headingId="lic-h">Licence terms</FoldTitle>
			<span class="lic-need">Not accepted yet: needed once, before your first run</span>
			<span class="mg-grow"></span>
			<FoldToggle id={LICENCE} closed />
		</header>
		<Fold id={LICENCE} closed><div class="lic-body"><Licence /></div></Fold>
	</section>
{/if}

<!-- ------------------------------------------------ the run -->
{@render runCard()}
{/if}
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

	/* ---------------------------------------- the steps (on the cluster) */
	.steps {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.step {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.step-head {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		min-height: 42px;
		padding: 8px 14px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text);
		font: inherit;
		text-align: left;
	}
	button.step-head {
		cursor: pointer;
	}
	button.step-head:hover {
		border-color: var(--mg-border-strong);
	}
	.step.current > .step-head {
		border-color: color-mix(in srgb, var(--mg-accent) 55%, var(--mg-border));
	}
	.step-num {
		display: inline-flex;
		flex: none;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		border: 1px solid var(--mg-border-strong);
		border-radius: 50%;
		font-size: var(--mg-fs-sm);
		font-weight: 650;
	}
	.step.current .step-num {
		border-color: transparent;
		background: var(--mg-accent);
		color: var(--mg-on-accent, #fff);
	}
	.step.done .step-num {
		border-color: color-mix(in srgb, var(--mg-ok) 55%, var(--mg-border));
		color: var(--mg-ok);
	}
	.step.later .step-head {
		opacity: 0.55;
	}
	.step-sum {
		min-width: 0;
		overflow: hidden;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.step-change {
		flex: none;
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: var(--mg-fs-sm);
	}
	.step-body {
		display: flex;
		flex-direction: column;
		gap: var(--cr-stack, 16px);
	}
	.step-lead {
		margin: 0;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
	}
	.step-card {
		padding: var(--cr-box-pad, 16px 18px);
	}
	.step-go {
		display: flex;
		justify-content: flex-end;
	}

	/* The licence terms, once: their body pads like the head. */
	.lic-body {
		padding: var(--cr-pad, 16px 18px);
	}
	.lic-need {
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-warn);
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
