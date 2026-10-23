<script lang="ts">
	import { untrack } from 'svelte';
	import { ArrowRight, Check, RotateCcw, Square, X } from 'lucide-svelte';
	import type { Run } from '$lib/api';
	import { genomeList, stemOf } from '$lib/crisp/genomes';
	import { buildProgress, leftText, span, UNTIMED_FLOOR } from '$lib/crisp/progress-model';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import BuildBar from '$lib/workspace/blocks/BuildBar.svelte';
	import Fold from '$lib/workspace/motion/Fold.svelte';
	import FoldTitle from '$lib/workspace/motion/FoldTitle.svelte';
	import FoldToggle from '$lib/workspace/motion/FoldToggle.svelte';
	import GenomesBoard from '$lib/crisp/GenomesBoard.svelte';
	import RunAction from '$lib/workspace/blocks/RunAction.svelte';
	import Licence from '$lib/cluster/Licence.svelte';
	import RunSteps from './RunSteps.svelte';
	import { readSources, sourceSay, type SourceRow } from '$lib/crisp/cache-report';

	/**
	 * The Analyze page, in the order a run is set up: 1 the genomes (folder, files, table),
	 * 2 gene calling and 3 the annotation tools (RunSteps), the licence terms once before a
	 * first run, then the start button (or the run's bar with Stop, or Resume and Restart
	 * after a failed run), and a foldable grid of genomes by tool, each cell a pie of that
	 * tool's progress. The grid scrolls and resizes for hundreds of genomes.
	 */
	let { tools }: { tools: string[] } = $props();

	const GRID = 'analyze:grid';
	const GENOME_TABLE = 'analyze:genome-table';

	/** On the cluster, your databases' state (the page's checklist says when a first run copies them). */
	$effect(() => {
		if (backend.cluster) ws.loadStores();
	});

	/** On the cluster, the licence terms are accepted once, here, before a first run. */
	const needsTerms = $derived(!!backend.cluster && ws.setup.some((r) => r.id === 'terms' && r.tone !== 'ok'));
	/** Folded until opened, like the other steps; the start button's note links here. */
	const LICENCE = 'analyze:licence';

	const genomes = $derived(genomeList());
	const inFolder = $derived(genomes.filter((g) => g.file));
	const n = $derived(ws.genomes.length);

	const setting = (key: string) => ws.settings.find((s) => s.key === key)?.value ?? '';

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

	// ---------------------------------------------------------------- genomes and progress
	/** The run whose steps are in view: the one going, else the last one that ended badly. */
	const shown = $derived(run ?? lastBad);
	$effect(() => {
		const r = lastBad;
		if (!run && r && ws.logOf !== r.id) untrack(() => ws.readLog(r.id));
	});
	/** Its log and clock, once they are the ones read. */
	const mine = $derived(!!shown && ws.logOf === shown.id);
	/** The run whose cache report the grid shows: the one in view, else the latest that finished. */
	const reportRun = $derived(
		shown ?? ws.runs.filter((r) => r.kind === 'annotate' && r.status === 'completed').sort((a, b) => b.started.localeCompare(a.started))[0] ?? null
	);
	/** Its cache report (fresh or restored, per step): read when the run changes, every 30 s while it goes. */
	const reportKey = $derived(reportRun?.outputDir ? `${reportRun.id}\n${reportRun.outputDir}\n${reportRun.status}` : '');
	let sources = $state<{ id: string; rows: SourceRow[] | null; fromLog: boolean } | null>(null);
	$effect(() => {
		const key = reportKey;
		if (!key) return;
		const [id, dir, status] = key.split('\n');
		let stop = false;
		const read = () =>
			readSources(dir, id).then((d) => {
				if (!stop) sources = { id, rows: d?.rows ?? null, fromLog: !!d?.fromLog };
			});
		untrack(read);
		if (status !== 'running') return () => (stop = true);
		const t = setInterval(read, 30_000);
		return () => {
			stop = true;
			clearInterval(t);
		};
	});

	/** The run's genomes while one goes; otherwise those in the input folder, by name. */
	const rows = $derived(
		run && p ? p.genomes.map((g) => g.name) : inFolder.map((g) => g.name).sort((a, b) => a.localeCompare(b))
	);
	const meta = $derived(new Map(ws.genomes.map((g) => [stemOf(g.name), g])));
	/* A clock for the pies of tools under way: the server's time, ticking here between polls. */
	let tickAt = $state(Date.now());
	let skew = 0;
	$effect(() => {
		if (ws.clock) skew = ws.clock.now - Date.now();
	});
	$effect(() => {
		if (!run) return;
		const t = setInterval(() => (tickAt = Date.now()), 2000);
		return () => clearInterval(t);
	});

	/** The report's rows for the run in view (null: none read, or a run from before reports were kept). */
	const srcRows = $derived(sources && reportRun && sources.id === reportRun.id ? sources.rows : null);
	/** Rebuilt from the job log (a run from before reports): it names restores only, so a finished step it leaves out ran in the job. */
	const srcFromLog = $derived(!!srcRows && !!sources?.fromLog);
	const srcLine = $derived.by(() => {
		if (!srcRows) return '';
		const on = srcRows.filter((r) => r.source !== 'not run');
		const restored = on.filter((r) => r.source === 'restored').length;
		const partly = on.filter((r) => r.source === 'partly restored').length;
		const fresh = on.filter((r) => r.source === 'fresh').length;
		return [restored && `${restored} restored from the database`, partly && `${partly} partly restored`, fresh && `${fresh} run fresh`].filter(Boolean).join(', ');
	});
	/** The grid, from the model the Jobs page reads too (lib/crisp/progress-model.ts). */
	const prog = $derived(
		buildProgress({
			run: shown,
			going: !!run,
			tools,
			offered: ws.tools.map((t) => t.name),
			genomes: rows,
			log: mine ? ws.log : '',
			clock: mine ? ws.clock : null,
			now: tickAt + skew,
			results: ws.results,
			meta,
			setting,
			outputRoot: ws.resultRoots.outputRoot,
			current: run && p?.current ? { genome: p.current, tool: p.detail } : null,
			sources: srcRows
		})
	);
	const phases = $derived(prog.phases);
	const cols = $derived(prog.cols);
	const firsts = $derived(prog.firsts);
	const matrix = $derived(prog.rows);
	const columns = $derived(prog.columns);
	const overall = $derived(prog.overall);
	const counts = $derived(prog.counts);

	// ---------------------------------------------------------------- the popup on a pie
	/** The pie clicked: its genome and step, and where to put the popup. */
	let pick = $state<{ g: string; t: string; x: number; y: number } | null>(null);
	const picked = $derived.by(() => {
		if (!pick) return null;
		const row = matrix.find((r) => r.g === pick!.g);
		const c = row?.cells.find((x) => x.t === pick!.t);
		return row && c ? { row, c } : null;
	});
	function openPop(g: string, t: string, e: MouseEvent) {
		const W = 300;
		const H = 250;
		const x = Math.min(Math.max(8, e.clientX - W / 2), window.innerWidth - W - 8);
		const y = e.clientY + H + 24 > window.innerHeight ? Math.max(8, e.clientY - H - 12) : e.clientY + 14;
		pick = pick?.g === g && pick?.t === t ? null : { g, t, x, y };
	}
	/** Mounts the popup at the interface's root, so no page transform moves it off the pie. */
	function toRoot(node: HTMLElement) {
		(node.closest('[data-mg-root]') ?? document.querySelector('[data-mg-root]') ?? document.body).appendChild(node);
		return { destroy: () => node.remove() };
	}
	const STATE_WORD: Record<string, string> = { done: 'Done', run: 'Running', wait: 'Running', failed: 'Failed', partial: 'Stopped before it finished', none: 'Not started', na: 'Not used' };
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
			<a class="mg-link quiet" href={uiBase.to(`/jobs/${run.id}`)}>Log</a>
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
					<a class="mg-link quiet" href={uiBase.to(`/jobs/${lastBad.id}`)}>Log</a>
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

<!-- ------------------------------------------------ genomes and progress: once there is a run to show -->
{#if run || reportRun}
<section class="card gridcard" class:folded={ui.isFolded(GRID, true)}>
	<header class="ghead">
		<FoldTitle id={GRID} closed>{run ? 'Progress' : 'Last run'}</FoldTitle>
		<span class="count">{rows.length ? `${rows.length} genome${rows.length === 1 ? '' : 's'}` : ''}{counts.all ? ` | ${counts.done} of ${counts.all} steps done` : ''}{srcLine ? ` | ${srcLine}` : ''}</span>
		<span class="mg-grow"></span>
		{#if !ui.isFolded(GRID, true)}
		<ul class="key" aria-label="Key">
			<li><span class="pie done" style="--p: 100"><Check size={9} strokeWidth={3.5} /></span>done</li>
			<li><span class="pie run" style="--p: 40"></span>running</li>
			<li><span class="pie failed"><X size={9} strokeWidth={3.5} /></span>failed</li>
			<li><span class="pie none"></span>not started</li>
			<li><span class="pie na"></span>not used</li>
			<li title="Its results came from the MARGIE database: the whole output (genome level) or every protein (protein level); a paler dot, only some proteins"><span class="pie done fromdb" style="--p: 100"><Check size={9} strokeWidth={3.5} /></span>restored</li>
		</ul>
		{/if}
		<FoldToggle id={GRID} closed />
	</header>
	<Fold id={GRID} closed>
		{#if rows.length && cols.length}
			<div class="scroller">
				<table class="pgrid" aria-label="Results in, by genome and tool">
					<thead>
						<tr class="phases">
							<th class="corner" rowspan="2" scope="col">Genome</th>
							{#each phases as g (g.label)}<th colspan={g.cols.length} scope="colgroup">{g.label}</th>{/each}
						</tr>
						<tr class="tools">
							{#each phases as g (g.label)}
								{#each g.cols as t, i (t)}<th scope="col" class:first={i === 0}><span>{t}</span></th>{/each}
							{/each}
						</tr>
						<!-- each tool across every genome -->
						<tr class="totals">
							<th scope="row" class="gname" title="All genomes: {overall}% of their steps done">
								<span class="gn">
									<span class="pie big" class:done={overall === 100} style="--p: {overall}" aria-hidden="true">
										{#if overall === 100}<Check size={9} strokeWidth={3.5} />{/if}
									</span>
									<span class="nm">All genomes</span>
									<span class="gpct">{overall}%</span>
								</span>
							</th>
							{#each columns as c (c.t)}
								{@const st = c.pct === null ? 'na' : c.pct === 100 ? 'done' : c.failed ? 'failed' : c.pct > 0 ? 'run' : 'none'}
								<th
									class:first={firsts.has(c.t)}
									title={c.pct === null
										? `${c.t}: not used`
										: `${c.t}: ${c.pct}% overall | ${c.done} of ${c.of} genome${c.of === 1 ? '' : 's'} done${c.failed ? ` | ${c.failed} failed` : ''}`}
								>
									<span class="pie {st === 'failed' ? 'run hurt' : st}" style="--p: {c.pct ?? 0}">
										{#if st === 'done'}<Check size={9} strokeWidth={3.5} />{/if}
									</span>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each matrix as row (row.g)}
							<tr>
								<th scope="row" class="gname" title="{row.g}: {row.pct}% of its steps done">
									<span class="gn">
										<span class="pie big" class:done={row.pct === 100} style="--p: {row.pct}" aria-hidden="true">
											{#if row.pct === 100}<Check size={9} strokeWidth={3.5} />{/if}
										</span>
										<span class="nm">{row.g}</span>
										<span class="gpct">{row.pct}%</span>
									</span>
								</th>
								{#each row.cells as c (c.t)}
									{@const mark = c.state === 'done' ? 'tick' : c.state === 'failed' ? 'cross' : ''}
									<td class:first={firsts.has(c.t)} title="{row.g} | {c.t}: {c.say}{c.state === 'na' ? '' : ' | click for details'}">
										{#if c.state === 'na'}
											<span class="pie na" style="--p: 0"></span>
										{:else}
											<button
												type="button"
												class="cellink"
												aria-label="{row.g} {c.t}: {c.say}"
												aria-expanded={pick?.g === row.g && pick?.t === c.t}
												onclick={(e) => openPop(row.g, c.t, e)}
											>
												<span class="pie {c.state}" class:fromdb={c.src?.source === 'restored'} class:partdb={c.src?.source === 'partly restored'} style="--p: {c.pct ?? 0}">
													{#if mark === 'tick'}<Check size={9} strokeWidth={3.5} />{:else if mark === 'cross'}<X size={9} strokeWidth={3.5} />{/if}
												</span>
											</button>
										{/if}
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else}
			<p class="mg-note empty">
				{n ? 'Choose tools to see a column for each.' : 'No genomes yet.'}
				{#if !n}<a class="mg-link" href={'#genomes'}>Add FASTA files</a>{/if}
			</p>
		{/if}
	</Fold>
</section>
{/if}
</div>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (pick = null)} />
{#if picked && pick}
	{@const c = picked.c}
	{@const row = picked.row}
	<div class="popwrap" use:toRoot>
		<button type="button" class="pop-scrim" aria-label="Close" onclick={() => (pick = null)}></button>
		<div class="pop" role="dialog" aria-label="{c.t} on {row.g}" style="left: {pick.x}px; top: {pick.y}px">
			<header class="pop-head">
				<span class="pie {c.state}" style="--p: {c.pct ?? 0}">
					{#if c.state === 'done'}<Check size={9} strokeWidth={3.5} />{:else if c.state === 'failed'}<X size={9} strokeWidth={3.5} />{/if}
				</span>
				<span class="pop-title"><b>{c.t}</b><span class="mg-mono" title={row.g}>{row.g}</span></span>
				<button type="button" class="pop-x" aria-label="Close" onclick={() => (pick = null)}><X size={14} /></button>
			</header>
			<dl class="pop-rows">
				<dt>This step</dt>
				<dd>{STATE_WORD[c.state] ?? c.state}{c.state === 'run' && c.pct !== null ? `, ${Math.round(c.pct)}%` : ''}</dd>
				{#if c.src && c.src.source !== 'not run'}
					<dt>Results</dt>
					<dd>{sourceSay(c.src)}{c.src.stage ? ` (${c.src.stage})` : ''}</dd>
					{#if c.src.database}
						<dt>Database</dt>
						<dd class="mg-mono pop-db" title={c.src.database}>{c.src.database}</dd>
					{/if}
				{:else if c.state === 'done' && reportRun && (srcFromLog || !srcRows)}
					<dt>Results</dt>
					<dd>
						{srcFromLog
							? 'Run in this job: its log shows no restore from the database for this step.'
							: 'This run kept no record, in a report or its log, of whether this ran here or came back from the database.'}
					</dd>
				{/if}
				{#if c.so !== undefined}
					<dt>Time so far</dt>
					<dd>{span(c.so)}{c.usual ? ` of about ${span(c.usual)}` : ''}</dd>
				{:else if c.usual && c.state === 'none'}
					<dt>Usually takes</dt>
					<dd>about {span(c.usual)}</dd>
				{/if}
				{#if run && (c.state === 'run' || c.state === 'wait' || c.state === 'none')}
					<dt>Left</dt>
					<dd>{c.left === null ? `at least ${span(UNTIMED_FLOOR)} (no earlier run of this tool to go by)` : `about ${span(c.left)}`}</dd>
				{/if}
				<dt>This genome</dt>
				<dd>{row.pct}%, {row.done} of {row.of} steps{run && leftText(row.left, row.unknown) ? `, ${leftText(row.left, row.unknown)}` : ''}</dd>
				<dt>Whole job</dt>
				<dd>{overall}%, {counts.done} of {counts.all} steps{run && leftText(prog.left, prog.unknown, UNTIMED_FLOOR) ? `, ${leftText(prog.left, prog.unknown, UNTIMED_FLOOR)}` : ''}</dd>
			</dl>
			<div class="pop-acts">
				{#if c.href}<a class="mg-btn small" href={c.href} onclick={() => (pick = null)}>{c.state === 'failed' ? 'Open the log' : 'Open its folder'}</a>{/if}
				{#if shown}<a class="mg-link quiet" href={uiBase.to(`/jobs?job=${encodeURIComponent(shown.id)}`)} onclick={() => (pick = null)}>All details on Jobs</a>{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	/* The steps one under another, a gutter apart. */
	.analyze {
		display: flex;
		flex-direction: column;
		gap: var(--cr-gutter, 16px);
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
	/* On a phone, a step's summary goes under its title, so its Show stays on the title's line. */
	@media (max-width: 640px) {
		.an-steps :global(:is(.gb-top, .rs-head)),
		.lichead {
			flex-wrap: wrap;
			row-gap: 2px;
		}
		.an-steps :global(:is(.gb-sum, .rs-sum)),
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
		padding: var(--mg-pad) calc(var(--mg-pad) * 1.2);
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

	/* ---------------------------------------- genomes and progress */
	.gridcard {
		overflow: hidden;
	}
	.ghead {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px 12px;
		min-height: 44px;
		padding: 6px var(--mg-pad);
		border-bottom: 1px solid var(--mg-border);
	}
	.gridcard.folded .ghead {
		border-bottom-color: transparent;
	}
	.ghead :global(.mo-fold-title) {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 500;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.count {
		font-size: var(--mg-fs-sm);
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-2);
	}
	.key {
		display: flex;
		gap: 14px;
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.key li {
		display: inline-flex;
		align-items: center;
		gap: 5px;
	}
	/* Scrolls both ways; pull its corner to make it taller. */
	.scroller {
		max-height: 60vh;
		min-height: 160px;
		overflow: auto;
		resize: vertical;
	}
	/* The full width of the card: few tools give wider columns, many give narrow ones. */
	.pgrid {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		font-size: var(--mg-fs-xs);
	}
	/* Three pinned rows of fixed height: phases (26), tool names (96), totals (30). */
	.pgrid thead th {
		box-sizing: border-box;
		position: sticky;
		z-index: 2;
		background: var(--cr-card, var(--mg-surface));
		font-weight: 500;
		color: var(--mg-text-3);
	}
	.phases th {
		top: 0;
		height: 26px;
		padding: 0 6px;
		border-bottom: 1px solid var(--mg-border);
		border-left: 1px solid var(--mg-border);
		text-align: left;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		white-space: nowrap;
	}
	.tools th {
		top: 26px;
		height: 96px;
		padding: 4px 0;
		border-bottom: 1px solid var(--mg-border);
		vertical-align: bottom;
	}
	.tools th span {
		display: inline-block;
		writing-mode: vertical-rl;
		transform: rotate(180deg);
		white-space: nowrap;
		color: var(--mg-text-2);
	}
	/* The row of totals stays in view under the tool names. */
	.totals th {
		top: 122px;
		height: 30px;
		border-bottom: 1px solid var(--mg-border);
		text-align: center;
	}
	.totals .gname {
		z-index: 3;
		color: var(--mg-text-2);
	}
	.pie.hurt {
		border-color: var(--mg-danger, #c0392b);
	}
	/* Restored from the database: a small dot on the pie's corner (paler when only partly). */
	.pie.fromdb,
	.pie.partdb {
		position: relative;
	}
	.pie.fromdb::after,
	.pie.partdb::after {
		content: '';
		position: absolute;
		right: -3px;
		bottom: -3px;
		width: 7px;
		height: 7px;
		border: 1.5px solid var(--cr-card, var(--mg-surface));
		border-radius: 50%;
		background: var(--mg-accent-ink, var(--mg-accent));
	}
	.pie.partdb::after {
		background: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-surface));
	}
	.pop-db {
		overflow-wrap: anywhere;
		font-size: var(--mg-fs-xs);
	}
	.cellink {
		display: inline-grid;
		place-items: center;
		padding: 0;
		border: none;
		border-radius: 50%;
		background: none;
		cursor: pointer;
	}
	.cellink[aria-expanded='true'] .pie {
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-accent) 35%, transparent);
	}
	/* ---------------------------------------- the popup on a pie */
	.pop-scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
		border: none;
		background: transparent;
		cursor: default;
	}
	.pop {
		position: fixed;
		z-index: 61;
		width: 300px;
		padding: 12px 14px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: var(--cr-pop-shadow, 0 8px 24px rgba(16, 24, 40, 0.14));
		color: var(--mg-text);
		font-family: var(--mg-font);
		font-size: var(--cr-fs-meta, 13px);
	}
	.pop-head {
		display: flex;
		align-items: center;
		gap: 9px;
		margin-bottom: 10px;
	}
	.pop-title {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
		line-height: 1.25;
	}
	.pop-title b {
		font-size: var(--cr-fs-body, 14px);
	}
	.pop-title span {
		overflow: hidden;
		color: var(--mg-text-2);
		font-size: 0.92em;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.pop-x {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		padding: 0;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		cursor: pointer;
	}
	.pop-x:hover {
		background: color-mix(in srgb, var(--mg-text) 7%, transparent);
	}
	.pop-rows {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 5px 12px;
		margin: 0;
	}
	.pop-rows dt {
		color: var(--mg-text-3);
	}
	.pop-rows dd {
		margin: 0;
	}
	.pop-acts {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 12px;
		margin-top: 12px;
	}
	.cellink:hover .pie {
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-accent) 25%, transparent);
	}
	.cellink:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: 1px;
	}
	.pgrid .corner {
		left: 0;
		z-index: 3;
		width: 240px;
		min-width: 240px;
		padding: 0 var(--mg-pad);
		border-bottom: 1px solid var(--mg-border);
		text-align: left;
		vertical-align: bottom;
		padding-bottom: 8px;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
	.gname {
		position: sticky;
		left: 0;
		z-index: 1;
		width: 240px;
		max-width: 240px;
		height: 26px;
		padding: 0 var(--mg-pad);
		background: var(--cr-card, var(--mg-surface));
		font-weight: 400;
		text-align: left;
		color: var(--mg-text);
	}
	.gn {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}
	.nm {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.pgrid td {
		min-width: 24px;
		height: 26px;
		padding: 0;
		text-align: center;
	}
	.pgrid .first {
		border-left: 1px solid var(--mg-border);
	}
	.pgrid tbody tr:hover th,
	.pgrid tbody tr:hover td {
		background: color-mix(in srgb, var(--mg-accent) 5%, var(--cr-card, var(--mg-surface)));
	}
	.empty {
		margin: 0;
		padding: var(--mg-pad);
	}

	/* ---------------------------------------- the pies, as Finder draws a copy */
	@property --p {
		syntax: '<number>';
		inherits: false;
		initial-value: 0;
	}
	.pie {
		--p: 0;
		display: inline-grid;
		place-items: center;
		flex: none;
		width: 15px;
		height: 15px;
		border-radius: 50%;
		border: 1.5px solid color-mix(in srgb, var(--mg-accent) 55%, var(--mg-border));
		background: conic-gradient(var(--mg-accent) calc(var(--p) * 1%), transparent 0);
		color: var(--mg-on-accent, #fff);
		vertical-align: middle;
		transition: --p 600ms ease;
	}
	.pie.big {
		width: 16px;
		height: 16px;
	}
	/* Done: full, with a tick. */
	.pie.done {
		border-color: var(--mg-accent);
		background: var(--mg-accent);
	}
	/* Failed: a cross on the danger colour. */
	.pie.failed {
		border-color: var(--mg-danger, #c0392b);
		background: var(--mg-danger, #c0392b);
	}
	/* Under way: filled as far as its own tool has got. */
	.pie.run {
		border-color: var(--mg-accent);
		transition: --p 2s linear;
	}
	/* Under way with nothing to estimate from: its ring breathes, and it fills no further than the truth. */
	.pie.wait {
		border-color: var(--mg-accent);
		animation: breathe 2.4s ease-in-out infinite;
	}
	@keyframes breathe {
		50% {
			border-color: color-mix(in srgb, var(--mg-accent) 25%, transparent);
		}
	}
	.pie.partial {
		border-style: dashed;
		border-color: var(--mg-warn);
	}
	.pie.none {
		border-style: dotted;
		border-color: var(--mg-border-strong);
	}
	/* Not used here (off, not chosen, not in this pipeline): a quiet grey disc, unlike any step that runs. */
	.pie.na {
		border-color: transparent;
		background: color-mix(in srgb, var(--mg-text-3) 14%, transparent);
	}
	.gpct {
		margin-left: auto;
		padding-left: 8px;
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-3);
	}

	.table {
		max-height: 44vh;
		overflow: auto;
		resize: vertical;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
	}

	:global([data-motion='off']) .pie {
		animation: none !important;
		transition: none !important;
	}

	@media (max-width: 700px) {
		.key {
			display: none;
		}
	}
</style>
