<script lang="ts">
	import { Check, ChevronRight, Copy, ExternalLink, FolderOpen, PanelLeftClose, PanelLeftOpen, RotateCcw, RotateCw, Square, X } from 'lucide-svelte';
	import Resizer from '$lib/workspace/motion/Resizer.svelte';
	import JobCommand from '$lib/crisp/JobCommand.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import { span } from '$lib/crisp/progress-model';
	import { page } from '$app/state';
	import { genomeList, stemOf } from '$lib/crisp/genomes';
	import { buildProgress, leftText, toolsOfRun, UNTIMED_FLOOR } from '$lib/crisp/progress-model';
	import type { ToolClock } from '$lib/workspace/data.svelte';
	import '$lib/workspace/viewers/tools.css';
	import { api, type Run } from '$lib/api';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ago, duration } from '$lib/workspace/format';

	/**
	 * The Jobs page: a narrow list of jobs, one line each (name | id | status), beside the
	 * selected one (the running job by default): its actions, its progress by genome, and
	 * its log, which takes most of the height.
	 */

	const TYPE: Record<string, string> = { annotate: 'Annotate', setup: 'Set up', build: 'Install' };
	const STATUS: Record<string, string> = { running: 'running', completed: 'finished', failed: 'failed', cancelled: 'stopped' };

	/** "Annotate 6 genomes", "Install pfam, kegg +3". */
	function title(r: Run): string {
		const label = r.label.replace(/ with .*$/, '');
		if (r.kind === 'annotate' && r.files?.length) return `Annotate ${r.files.length === 1 ? r.files[0] : `${r.files.length} genomes`}`;
		return label;
	}
	function toolsLine(r: Run): string {
		if (r.tools?.length) return r.tools.length > 3 ? `${r.tools.slice(0, 3).join(', ')} +${r.tools.length - 3}` : r.tools.join(', ');
		if (r.kind === 'annotate') return r.args.includes('--genes-only') ? 'gene caller only' : 'all tools';
		return '';
	}
	/** One word, and how far a running job has got. */
	function statusWord(r: Run): string {
		const word = STATUS[r.status] ?? r.status;
		return r.status === 'running' && typeof r.progress === 'number' ? `${word} ${Math.round(r.progress)}%` : word;
	}
	/** A job's id as the list shows it: the first block of a long one. */
	const shortId = (id: string) => (id.length > 12 ? id.split('-')[0] : id);
	/** A failed or stopped annotation can be picked up where it stopped, or run again from the start. */
	const again = (r: Run) => r.kind === 'annotate' && (r.status === 'failed' || r.status === 'cancelled');
	let busy = $state('');
	async function relaunch(r: Run, how: 'resume' | 'restart') {
		busy = how;
		const ok = how === 'resume' ? await ws.resume(r) : await ws.restart(r);
		busy = '';
		if (ok) picked = null;
	}
	const folderHref = (dir: string) => `${uiBase.path}/files?path=${encodeURIComponent(dir)}`;

	// ------------------------------------------------ the log beside the list
	// ?job=<id> (from Analyze's popup) opens that job.
	let picked = $state<string | null>(page.url.searchParams.get('job'));
	const shown = $derived(ws.runs.find((r) => r.id === picked) ?? ws.active ?? ws.runs[0] ?? null);
	/** The watched run's log is already in ws.log; any other is read once. */
	const live = $derived(!!shown && shown.id === ws.active?.id);
	let fetched = $state<{ id: string; text: string; clock?: ToolClock | null } | null>(null);
	$effect(() => {
		const r = shown;
		if (!r || live || fetched?.id === r.id) return;
		const id = r.id;
		fetched = { id, text: 'Reading the log…' };
		api<{ log: { text: string }; clock?: ToolClock | null }>(`/runs/${id}?tail=12000`)
			.then((d) => {
				if (fetched?.id === id) fetched = { id, text: d.log.text || 'Nothing in the log.', clock: d.clock ?? null };
			})
			.catch(() => {
				if (fetched?.id === id) fetched = { id, text: 'The log could not be read.' };
			});
	});
	const logText = $derived(live ? ws.log.slice(-12000) : fetched && shown && fetched.id === shown.id ? fetched.text : '');
	const lines = $derived(logText.trimEnd().split('\n').slice(-60));
	let term = $state<HTMLElement | null>(null);
	$effect(() => {
		void lines;
		if (term) term.scrollTop = term.scrollHeight;
	});

	// ------------------------------------------------ the job's progress, beside its log
	const going = $derived(shown?.status === 'running');
	const clock = $derived(live ? (ws.logOf === shown?.id ? ws.clock : null) : (fetched && shown && fetched.id === shown.id ? (fetched.clock ?? null) : null));
	let tickAt = $state(Date.now());
	$effect(() => {
		if (!going) return;
		const t = setInterval(() => (tickAt = Date.now()), 2000);
		return () => clearInterval(t);
	});
	const setting = (key: string) => ws.settings.find((x) => x.key === key)?.value ?? '';
	/** Its genomes: those its jobs name, and while it goes those in the input folder too. */
	const jobGenomes = $derived.by(() => {
		const named = new Set((clock?.started ?? []).map((e) => e.genome).filter(Boolean));
		if (going || !named.size) for (const g of genomeList()) if (g.file) named.add(g.name);
		return [...named].sort((a, b) => a.localeCompare(b));
	});
	const prog = $derived(
		shown?.kind === 'annotate'
			? buildProgress({
					run: shown,
					going,
					tools: toolsOfRun(shown, ws.tools.map((t) => t.name)),
					offered: ws.tools.map((t) => t.name),
					genomes: jobGenomes,
					log: live ? ws.log : logText,
					clock,
					now: tickAt + (clock ? clock.now - Date.now() : 0),
					results: ws.results,
					meta: new Map(ws.genomes.map((g) => [stemOf(g.name), g])),
					setting,
					outputRoot: ws.resultRoots.outputRoot
				})
			: null
	);
	let expanded = $state(new Set<string>());
	function toggleRow(g: string) {
		const next = new Set(expanded);
		if (next.has(g)) next.delete(g);
		else next.add(g);
		expanded = next;
	}
	const ROW_WORD: Record<string, string> = { done: 'done', failed: 'failed', running: 'running', stopped: 'stopped', queued: 'not started' };

	/** How long a genome has been going: from its first step's start (only while the job runs). */
	function elapsedOf(g: string): string {
		if (!going || !clock) return '';
		const starts = clock.started.filter((e) => e.genome === g || e.genome === '').map((e) => e.start);
		if (!starts.length) return '';
		return span((tickAt + (clock.now - Date.now()) - Math.min(...starts)) / 1000);
	}

	// ------------------------------------------------ the list's width: dragged, or folded away
	const LIST = 'jobs:list';
	const listShut = $derived(ui.isFolded(LIST));
	const listWidth = $derived(ui.size(LIST, 300));
	// The log's height: most of the window to start with, then as dragged at its bottom edge.
	const LOG = 'jobs:log';
	const logFallback = typeof innerHeight === 'number' ? Math.max(560, Math.round(innerHeight * 0.8)) : 640;
	const logHeight = $derived(ui.size(LOG, logFallback));

	// ------------------------------------------------ copying the log
	/** Copies the log as read (its last 12,000 characters); the full one is on its own page. */
	async function copyLog() {
		const text = logText.trimEnd();
		if (!text) return;
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			const range = document.createRange();
			if (term) range.selectNodeContents(term);
			getSelection()?.removeAllRanges();
			getSelection()?.addRange(range);
			document.execCommand('copy');
			getSelection()?.removeAllRanges();
		}
		ui.notify('The log is copied.', 'ok');
	}
	/** Ctrl or Cmd + C in the log: the selection if there is one, otherwise the whole log. */
	function logKey(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'c' && !getSelection()?.toString()) {
			e.preventDefault();
			copyLog();
		}
	}

</script>

{#if ws.runs.length}
	<div class="board">
		<div class="top" style="grid-template-columns: {listShut ? '40px' : `${listWidth}px`} minmax(0, 1fr)">
		<div class="list-pane" class:shut={listShut}>
			{#if listShut}
				<button type="button" class="pane-btn" title="Show the job list" aria-label="Show the job list" onclick={() => ui.toggleFold(LIST)}><PanelLeftOpen size={16} /></button>
				<span class="shut-count">{ws.runs.length} jobs</span>
			{:else}
				<div class="list-head">
					<span>{ws.runs.length} job{ws.runs.length === 1 ? '' : 's'}</span>
					<button type="button" class="pane-btn" title="Fold the job list away" aria-label="Fold the job list away" onclick={() => ui.toggleFold(LIST)}><PanelLeftClose size={16} /></button>
				</div>
		<ul class="list" aria-label="Jobs">
			{#each ws.runs as r (r.id)}
				<li>
					<button type="button" class="row {r.status}" aria-pressed={shown?.id === r.id} onclick={() => (picked = r.id)} title="{title(r)} | {r.id} | {statusWord(r)}{r.started ? ` | started ${ago(r.started)}` : ''}">
						<span class="dot" aria-hidden="true"></span>
						<span class="r-name">{title(r)}</span>
						<span class="sep" aria-hidden="true">|</span>
						<span class="r-id mg-mono">{shortId(r.id)}</span>
						<span class="sep" aria-hidden="true">|</span>
						<span class="r-st">{statusWord(r)}</span>
					</button>
				</li>
			{/each}
		</ul>
				<Resizer id={LIST} fallback={300} min={220} max={620} edge="right" label="Drag to widen or narrow the job list" />
			{/if}
		</div>

		<div class="side">
			{#if shown}
				<header class="job">
					<div class="job-what">
						<span class="job-name">{title(shown)}</span>
						<span class="job-meta">
							<span class="mg-mono">{shown.id}</span> | <span class="st {shown.status}">{statusWord(shown)}</span> | {ago(shown.started)}{shown.finished ? ` | took ${duration(shown)}` : ` | running for ${duration(shown)}`}{toolsLine(shown) ? ` | ${toolsLine(shown)}` : ''}
						</span>
					</div>
					<div class="job-acts">
						{#if shown.outputDir}
							<a class="mg-btn small" href={folderHref(shown.outputDir)} title={shown.outputDir}><FolderOpen size={14} />Folder</a>
						{/if}
						<a class="mg-btn small" href={uiBase.to(`/jobs/${shown.id}`)} title="The whole log on its own page"><ExternalLink size={14} />Full log</a>
						{#if shown.status === 'running'}
							<button type="button" class="mg-btn small danger" onclick={() => ws.stop(shown.id)}><Square size={11} fill="currentColor" />Stop</button>
						{:else if again(shown)}
							<button type="button" class="mg-btn small" disabled={!!busy} onclick={() => relaunch(shown, 'restart')} title="Run it again from the start"><RotateCw size={14} />{busy === 'restart' ? 'Restarting' : 'Restart'}</button>
							<button type="button" class="mg-btn small primary" disabled={!!busy} onclick={() => relaunch(shown, 'resume')} title="Pick up where it stopped; finished steps are not run again"><RotateCcw size={14} />{busy === 'resume' ? 'Resuming' : 'Resume'}</button>
						{/if}
					</div>
				</header>
				{#if shown.reason}<p class="why" title={shown.reason}>{shown.reason}</p>{/if}
			{/if}
			{#if prog && shown}
				<section class="status" aria-label="Progress of {title(shown)}">
					<div class="st-head">
						<span class="st-sum">
							<b>{prog.overall}%</b> | {prog.counts.done} of {prog.counts.all} steps | {going ? `${duration(shown)} so far` : `took ${duration(shown)}`}{going && leftText(prog.left, prog.unknown, UNTIMED_FLOOR) ? ` | ${leftText(prog.left, prog.unknown, UNTIMED_FLOOR)}` : ''}
						</span>
						<span class="st-bar" role="progressbar" aria-valuenow={prog.overall} aria-valuemin="0" aria-valuemax="100"><span style="width: {prog.overall}%"></span></span>
					</div>
					{#if prog.rows.length}
						<div class="orgs-wrap">
							<table class="orgs">
								<thead>
									<tr><th scope="col">Genome</th><th scope="col">Progress</th><th scope="col">Now</th><th scope="col">Steps</th><th scope="col">Elapsed</th><th scope="col">Left</th></tr>
								</thead>
								<tbody>
									{#each prog.rows as r (r.g)}
										<tr class="org {r.state}">
											<td class="o-name">
												<button type="button" aria-expanded={expanded.has(r.g)} onclick={() => toggleRow(r.g)} title={r.g}>
													<ChevronRight size={13} class="chev" /><span>{r.g}</span>
												</button>
											</td>
											<td class="o-bar">
												<span class="bar-s" class:done={r.state === 'done'} class:failed={r.state === 'failed'}><span style="width: {r.pct}%"></span></span>
												<span class="o-pct">{r.pct}%</span>
											</td>
											<td class="o-now" title={r.running.join(', ')}>{r.running.length ? r.running.join(', ') : ROW_WORD[r.state]}</td>
											<td class="o-steps">{r.done}/{r.of}</td>
											<td class="o-el">{elapsedOf(r.g)}</td>
											<td class="o-left" title={r.unknown ? 'Some steps have never run here, so this is a lower bound' : ''}>{going && r.state !== 'done' ? leftText(r.left, r.unknown).replace(/ left$/, '') : ''}</td>
										</tr>
										{#if expanded.has(r.g)}
											<tr class="o-detail">
												<td colspan="6">
													{#each prog.phases as ph (ph.label)}
														{@const cs = r.cells.filter((c) => ph.cols.includes(c.t) && c.state !== 'na')}
														{#if cs.length}
															<div class="ph">
																<span class="ph-name">{ph.label}</span>
																<span class="ph-steps">
																	{#each cs as c (c.t)}
																		<span class="step" title="{c.t}: {c.say}">
																			<span class="pie {c.state}" style="--p: {c.pct ?? 0}">
																				{#if c.state === 'done'}<Check size={8} strokeWidth={3.5} />{:else if c.state === 'failed'}<X size={8} strokeWidth={3.5} />{/if}
																			</span>
																			<span>{c.t}{c.state === 'run' && c.pct !== null ? ` ${Math.round(c.pct)}%` : ''}</span>
																		</span>
																	{/each}
																</span>
															</div>
														{/if}
													{/each}
												</td>
											</tr>
										{/if}
									{/each}
								</tbody>
							</table>
						</div>
					{:else}
						<p class="st-empty">No genomes in view yet: they appear as the run's jobs start.</p>
					{/if}
				</section>
			{/if}

		</div>
		</div>
		<div class="term-wrap" style="height: {logHeight}px">
		<aside class="term" aria-label="Log of {shown ? title(shown) : 'the job'}">
			<div class="term-head">
				<span class="term-t">Log{shown ? ` of ${title(shown)}` : ''}</span>
				<span class="mg-grow"></span>
				<button type="button" class="term-btn" title="Copy the log (Ctrl or Cmd + C in the log does the same)" disabled={!logText.trim()} onclick={copyLog}><Copy size={13} />Copy</button>
				{#if shown}<a class="term-btn" href={uiBase.to(`/jobs/${shown.id}`)}><ExternalLink size={13} />Full log</a>{/if}
			</div>
			{#if shown}<JobCommand run={shown} />{/if}
			<div class="out mg-mono" role="textbox" aria-readonly="true" aria-multiline="true" tabindex="0" aria-label="Log text" onkeydown={logKey} bind:this={term}>{#each lines as l, k (k)}<span class="ln" class:err={/error|failed|traceback/i.test(l)} class:ok={/\b(done|finished|completed)\b/i.test(l)}>{l}</span>
{/each}{#if live}<span class="cursor" aria-hidden="true"></span>{/if}</div>
		</aside>
			<Resizer id={LOG} fallback={logFallback} min={260} max={2400} edge="bottom" label="Drag to make the log taller or shorter" />
		</div>
	</div>
{:else}
	<p class="empty">
		<strong>No jobs yet.</strong>
		<span>Start one on <a class="mg-link" href="/analyze">Analyze</a>; every job shows up here with its log.</span>
	</p>
{/if}

<style>
	/* Two rows: the jobs beside the picked one's progress, then its log across the width.
	   Each part scrolls on its own; the page scrolls past them. */
	.board {
		display: flex;
		flex-direction: column;
		gap: 12px;
		color: var(--mg-text);
	}
	.top {
		display: grid;
		grid-template-rows: minmax(0, 1fr);
		height: clamp(380px, 52vh, 620px);
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		overflow: hidden;
	}

	/* ---- the list: its own pane, dragged wider or narrower, or folded to a strip ---- */
	.list-pane {
		position: relative;
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		border-right: 1px solid var(--mg-border);
	}
	.list-pane.shut {
		align-items: center;
		gap: 10px;
		padding-top: 6px;
	}
	.list-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 6px 2px 14px;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.pane-btn {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		cursor: pointer;
	}
	.pane-btn:hover {
		background: color-mix(in oklab, var(--mg-text) 7%, transparent);
		color: var(--mg-text);
	}
	.shut-count {
		writing-mode: vertical-rl;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	/* ---- the list: one line per job ---- */
	.list {
		min-width: 0;
		min-height: 0;
		margin: 0;
		padding: 4px 6px 6px;
		overflow: auto;
	}
	.row {
		display: flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		height: 26px;
		padding: 0 8px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-sm);
		text-align: left;
		white-space: nowrap;
		cursor: pointer;
	}
	.row:hover {
		background: color-mix(in oklab, var(--mg-text) 6%, transparent);
	}
	.row[aria-pressed='true'] {
		background: var(--mg-accent-soft);
		color: var(--mg-text);
	}
	.row:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: -2px;
	}
	.dot {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--mg-text-3);
	}
	.row.running .dot {
		background: var(--mg-accent);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-accent) 22%, transparent);
	}
	.row.completed .dot {
		background: var(--mg-ok);
	}
	.row.failed .dot {
		background: var(--mg-danger);
	}
	.r-name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		font-weight: 600;
		color: var(--mg-text);
	}
	.sep {
		flex: none;
		color: var(--mg-text-3);
	}
	.r-id {
		flex: none;
		font-size: 0.92em;
		color: var(--mg-text-3);
	}
	.r-st {
		flex: none;
	}
	.row.failed .r-st {
		color: var(--mg-danger);
	}
	.row.running .r-st {
		color: var(--mg-accent-ink);
	}

	/* ---- the job picked: its line, actions, progress, and log ---- */
	.side {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
	}
	/* The job's line and its failure reason keep their height above the table. */
	.job,
	.why {
		flex: none;
	}
	.job {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px 12px;
		padding: 8px var(--mg-pad);
		border-bottom: 1px solid var(--mg-border);
	}
	.job-what {
		display: flex;
		flex-direction: column;
		flex: 1 1 260px;
		min-width: 0;
	}
	.job-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 700;
	}
	.job-meta {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.st.failed {
		color: var(--mg-danger);
	}
	.st.running {
		color: var(--mg-accent-ink);
	}
	.st.completed {
		color: var(--mg-ok);
	}
	.job-acts {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.job-acts :global(.mg-btn) {
		gap: 6px;
	}
	.why {
		margin: 0;
		padding: 4px var(--mg-pad);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		color: var(--mg-danger);
		border-bottom: 1px solid var(--mg-border);
	}

	/* Progress: a line and a bar, then the genomes in a short scrolling table. */
	.status {
		flex: 1 1 auto;
		display: flex;
		flex-direction: column;
		min-height: 0;
		padding: 6px var(--mg-pad) 4px;
		border-bottom: 1px solid var(--mg-border);
		font-size: var(--mg-fs-xs);
	}
	.st-head {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 4px;
	}
	.st-sum {
		flex: none;
		color: var(--mg-text-2);
		white-space: nowrap;
	}
	.st-bar,
	.bar-s {
		display: block;
		overflow: hidden;
		border-radius: 99px;
		background: color-mix(in srgb, var(--mg-text) 10%, transparent);
	}
	.st-bar {
		flex: 1 1 auto;
		height: 6px;
	}
	.st-bar > span,
	.bar-s > span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: var(--mg-accent);
		transition: width 600ms ease;
	}
	.bar-s {
		flex: 1;
		height: 5px;
		min-width: 50px;
	}
	.bar-s.failed > span {
		background: var(--mg-danger);
	}
	.orgs-wrap {
		min-height: 0;
		overflow: auto;
	}
	.orgs {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
	}
	.orgs th {
		position: sticky;
		top: 0;
		z-index: 1;
		padding: 2px 6px;
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text-3);
		font-weight: 500;
		text-align: left;
	}
	.orgs th:nth-child(1) { width: 32%; }
	.orgs th:nth-child(2) { width: 22%; }
	.orgs th:nth-child(4) { width: 8%; }
	.orgs th:nth-child(5) { width: 11%; }
	.orgs th:nth-child(6) { width: 13%; }
	.o-el {
		color: var(--mg-text-2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.orgs td {
		padding: 2px 6px;
		border-top: 1px solid var(--mg-border);
		vertical-align: middle;
	}
	.o-name button {
		display: flex;
		align-items: center;
		gap: 3px;
		max-width: 100%;
		padding: 0;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}
	.o-name button span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.o-name button[aria-expanded='true'] :global(.chev) {
		transform: rotate(90deg);
	}
	.o-bar {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.o-pct {
		min-width: 3ch;
		color: var(--mg-text-2);
		font-variant-numeric: tabular-nums;
	}
	.o-now,
	.o-left {
		overflow: hidden;
		color: var(--mg-text-2);
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.o-steps {
		font-variant-numeric: tabular-nums;
	}
	.org.done .o-now {
		color: var(--mg-ok);
	}
	.org.failed .o-now {
		color: var(--mg-danger);
	}
	.org.stopped .o-now {
		color: var(--mg-warn);
	}
	.o-detail td {
		padding: 4px 6px 8px 20px;
		border-top: none;
	}
	.ph {
		display: grid;
		grid-template-columns: 70px minmax(0, 1fr);
		gap: 6px;
		padding: 2px 0;
	}
	.ph-name {
		color: var(--mg-text-3);
	}
	.ph-steps {
		display: flex;
		flex-wrap: wrap;
		gap: 3px 12px;
	}
	.step {
		display: inline-flex;
		align-items: center;
		gap: 5px;
	}
	.st-empty {
		color: var(--mg-text-3);
	}
	/* The same pies as the Analyze grid. */
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
		width: 13px;
		height: 13px;
		border-radius: 50%;
		border: 1.5px solid color-mix(in srgb, var(--mg-accent) 55%, var(--mg-border));
		background: conic-gradient(var(--mg-accent) calc(var(--p) * 1%), transparent 0);
		color: var(--mg-on-accent, #fff);
		transition: --p 600ms ease;
	}
	.pie.done {
		border-color: var(--mg-accent);
		background: var(--mg-accent);
	}
	.pie.failed {
		border-color: var(--mg-danger);
		background: var(--mg-danger);
	}
	.pie.run,
	.pie.wait {
		border-color: var(--mg-accent);
	}
	.pie.wait {
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

	/* The log: dark in either theme, most of the window tall, and taller or shorter by its bottom edge. */
	.term-wrap {
		position: relative;
		min-width: 0;
	}
	.term {
		--tm-ink: #e4e8ec;
		display: flex;
		flex-direction: column;
		height: 100%;
		min-width: 0;
		border-radius: var(--mg-r);
		background: #14171b;
		color: var(--tm-ink);
		overflow: hidden;
	}
	.term-head {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px 6px var(--mg-pad);
		border-bottom: 1px solid rgba(255, 255, 255, 0.09);
	}
	.term-t {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: #c9d0d6;
	}
	.term-btn {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		height: 26px;
		padding: 0 10px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: var(--mg-r-sm);
		background: none;
		color: #c9d0d6;
		font: inherit;
		font-size: 12px;
		cursor: pointer;
	}
	.term-btn:hover:not(:disabled) {
		border-color: rgba(255, 255, 255, 0.3);
		color: #fff;
	}
	.term-btn:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.out:focus-visible {
		outline: 2px solid color-mix(in srgb, var(--mg-accent) 70%, #fff);
		outline-offset: -2px;
	}
	.out {
		flex: 1 1 auto;
		min-height: 120px;
		margin: 0;
		padding: 8px var(--mg-pad) 14px;
		overflow: auto;
		font-size: 11.5px;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
		color: color-mix(in srgb, var(--tm-ink) 85%, transparent);
	}
	.ln.ok {
		color: color-mix(in srgb, var(--mg-ok) 70%, #fff);
	}
	.ln.err {
		color: color-mix(in srgb, var(--mg-danger) 75%, #fff);
	}
	.cursor {
		display: inline-block;
		width: 8px;
		height: 14px;
		vertical-align: text-bottom;
		background: var(--mg-ok);
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: calc(var(--mg-gap) * 2) var(--mg-pad);
		text-align: center;
		color: var(--mg-text-3);
	}
	.empty strong {
		color: var(--mg-text-2);
		font-size: var(--mg-fs);
	}
	:global([data-motion='off']) .board * {
		animation: none !important;
	}

	@media (max-width: 900px) {
		.top {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto minmax(0, 1fr);
			height: auto;
		}
		.list {
			max-height: 34vh;
			border-right: none;
			border-bottom: 1px solid var(--mg-border);
		}
	}
</style>
