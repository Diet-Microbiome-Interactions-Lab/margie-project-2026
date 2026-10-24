<script lang="ts">
	import { Check, Copy, Database, FolderOpen, PanelLeftClose, PanelLeftOpen, RotateCcw, RotateCw, Square, TextWrap } from 'lucide-svelte';
	import Resizer from '$lib/workspace/motion/Resizer.svelte';
	import JobCommand from '$lib/crisp/JobCommand.svelte';
	import ProgressGrid from '$lib/crisp/ProgressGrid.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import { page } from '$app/state';
	import { genomeList, stemOf } from '$lib/crisp/genomes';
	import { buildProgress, leftText, span, toolsOfRun, UNTIMED_FLOOR } from '$lib/crisp/progress-model';
	import type { ToolClock } from '$lib/workspace/data.svelte';
	import '$lib/workspace/viewers/tools.css';
	import { api, type Run } from '$lib/api';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ago, duration } from '$lib/workspace/format';
	import { countsByGenome, readSources, type SourceRow } from '$lib/crisp/cache-report';
	import { onDestroy, tick, untrack } from 'svelte';

	/**
	 * The Jobs page, one place per job: the list of jobs (name | id | status) beside the one
	 * picked (the running job by default): its actions, its progress in one bar, where its
	 * results came from and its details; then its progress by genome and step across the
	 * width, then its log, followed live while it goes.
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

	// ------------------------------------------------ the job picked
	// ?job=<id> opens that job (Analyze, and /jobs/<id>, send here).
	let picked = $state<string | null>(page.url.searchParams.get('job'));
	const shown = $derived(ws.runs.find((r) => r.id === picked) ?? ws.active ?? ws.runs[0] ?? null);
	/** The watched run: its log is in ws.log and its clock in ws.clock. */
	const live = $derived(!!shown && shown.id === ws.active?.id);

	// ------------------------------------------------ its log: the last part, then followed while it goes
	/** How much of a long log is read at first. */
	const TAIL = 200_000;
	/** Lines drawn; Copy copies all that was read. */
	const SHOWN = 20_000;
	let log = $state<{ id: string; text: string; offset: number; size: number; clock: ToolClock | null; step: string; error: string } | null>(null);
	let timer: ReturnType<typeof setTimeout> | null = null;
	let box = $state<HTMLElement | null>(null);
	let wrap = $state(true);
	async function follow(id: string, first: boolean) {
		try {
			const at = log?.id === id ? log.offset : 0;
			const d = await api<{ run: Run; step?: string; log: { text: string; offset: number; size: number }; clock?: ToolClock | null }>(
				first ? `/runs/${id}?tail=${TAIL}` : `/runs/${id}?offset=${at}`
			);
			if (shown?.id !== id) return;
			const atEnd = !box || box.scrollHeight - box.scrollTop - box.clientHeight < 40;
			const text = ((first ? '' : (log?.text ?? '')) + d.log.text).slice(-2_000_000);
			log = { id, text, offset: d.log.offset, size: d.log.size, clock: d.clock ?? null, step: d.step ?? '', error: '' };
			if (atEnd) tick().then(() => box && (box.scrollTop = box.scrollHeight));
		} catch (e) {
			if (shown?.id === id) log = { ...(log ?? { id, text: '', offset: 0, size: 0, clock: null, step: '' }), id, error: e instanceof Error ? e.message : String(e) };
		}
		if (shown?.id === id && shown.status === 'running') timer = setTimeout(() => follow(id, false), 2000);
	}
	$effect(() => {
		const id = shown?.id;
		if (!id) return;
		untrack(() => {
			if (timer) clearTimeout(timer);
			log = null;
			follow(id, true);
		});
		return () => {
			if (timer) clearTimeout(timer);
		};
	});
	onDestroy(() => timer && clearTimeout(timer));
	const logText = $derived(log && shown && log.id === shown.id ? log.text : '');
	const all = $derived(logText.replace(/\n$/, '').split('\n'));
	const lines = $derived(all.length > SHOWN ? all.slice(-SHOWN) : all);
	/** Only the end of a longer log is read. */
	const partial = $derived(!!log && log.size > log.text.length);
	const tone = (l: string) => (/error|failed|traceback|exception/i.test(l) ? 'err' : /warn/i.test(l) ? 'warn' : /\b(done|finished|completed)\b/i.test(l) ? 'ok' : '');
	let logEl = $state<HTMLElement | null>(null);
	/** Brings the log into view (a failed step's popup sends here). */
	function showLog() {
		logEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
		box?.focus();
	}

	// ------------------------------------------------ fresh or restored: the run's cache report
	/** Read again only when the run, its folder or its status changes (and every 30 s while it goes). */
	const reportKey = $derived(shown?.kind === 'annotate' && shown.outputDir ? `${shown.id}\n${shown.outputDir}\n${shown.status}` : '');
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
	const srcRows = $derived(sources && shown && sources.id === shown.id ? sources.rows : null);
	/** Rebuilt from the job log (a run from before reports): only its restores are listed. */
	const srcFromLog = $derived(!!srcRows && !!sources?.fromLog);
	/** The rows that say something (a step the run did not run is left out). */
	const srcShown = $derived((srcRows ?? []).filter((r) => r.source !== 'not run'));
	const srcDb = $derived(srcShown.find((r) => r.database)?.database ?? '');
	const srcTotals = $derived.by(() => {
		const t = { restoredGenome: 0, restoredProtein: 0, partly: 0, fresh: 0, kept: 0 };
		for (const c of countsByGenome(srcShown).values()) for (const k of Object.keys(t) as (keyof typeof t)[]) t[k] += c[k];
		return t;
	});

	// ------------------------------------------------ its progress
	const going = $derived(shown?.status === 'running');
	const clock = $derived(live ? (ws.logOf === shown?.id ? ws.clock : (log?.clock ?? null)) : (log && shown && log.id === shown.id ? log.clock : null));
	let tickAt = $state(Date.now());
	// Ticks each second while the job goes, so its elapsed time counts up live.
	$effect(() => {
		if (!going) return;
		const t = setInterval(() => (tickAt = Date.now()), 1000);
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
					log: live && ws.logOf === shown.id ? ws.log : logText,
					clock,
					now: tickAt + (clock ? clock.now - Date.now() : 0),
					results: ws.results,
					meta: new Map(ws.genomes.map((g) => [stemOf(g.name), g])),
					setting,
					outputRoot: ws.resultRoots.outputRoot,
					sources: srcRows
				})
			: null
	);
	/** The job's own bar for a job with no genome grid (setting up, installing). */
	const plainPct = $derived(!shown ? 0 : shown.status === 'completed' ? 100 : Math.max(0, Math.min(100, shown.progress ?? 0)));

	/** How long a genome has been going: from its first step's start (only while the job runs). */
	function elapsedOf(g: string): string {
		if (!going || !clock) return '';
		const starts = clock.started.filter((e) => e.genome === g || e.genome === '').map((e) => e.start);
		if (!starts.length) return '';
		return span((tickAt + (clock.now - Date.now()) - Math.min(...starts)) / 1000);
	}

	// ------------------------------------------------ its details (the facts its log names)
	function found(re: RegExp): string[] {
		const seen = new Set<string>();
		for (const m of logText.matchAll(re)) if (seen.size < 12) seen.add(m[1]);
		return [...seen];
	}
	const slurm = $derived(found(/(?:Submitted batch job|SLURM_JOB_ID[=:]?\s*|external jobid\s*'?|slurm[_ -]?job(?:[_ -]?id)?[=:\s]+)(\d{3,})/gi));
	const containers = $derived(found(/([\w.+-]+\.sif)\b/g));
	const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '');

	// ------------------------------------------------ the list's width: dragged, or folded away
	const LIST = 'jobs:list';
	const listShut = $derived(ui.isFolded(LIST));
	const listWidth = $derived(ui.size(LIST, 300));
	// The log's height: most of the window to start with, then as dragged at its bottom edge.
	const LOG = 'jobs:log';
	const logFallback = typeof innerHeight === 'number' ? Math.max(560, Math.round(innerHeight * 0.8)) : 640;
	const logHeight = $derived(ui.size(LOG, logFallback));

	// ------------------------------------------------ copying the log
	/** Copies the log as read. */
	async function copyLog() {
		const text = logText.trimEnd();
		if (!text) return;
		try {
			await navigator.clipboard.writeText(text);
			ui.notify('The log is copied.', 'ok');
		} catch {
			ui.notify('Could not reach the clipboard', 'error');
		}
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
		<div class="top" style="--list-w: {listShut ? '40px' : `${listWidth}px`}">
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
							<span class="mg-mono">{shown.id}</span> | <span class="st {shown.status}">{statusWord(shown)}</span> | started {ago(shown.started, tickAt)}{shown.finished ? ` | took ${duration(shown, tickAt)}` : ''}
						</span>
					</div>
					<div class="job-acts">
						{#if shown.outputDir}
							<a class="mg-btn small" href={folderHref(shown.outputDir)} title={shown.outputDir}><FolderOpen size={14} />Folder</a>
						{/if}
						{#if shown.status === 'running'}
							<button type="button" class="mg-btn small danger" onclick={() => ws.stop(shown.id)}><Square size={11} fill="currentColor" />Stop</button>
						{:else if again(shown)}
							<button type="button" class="mg-btn small" disabled={!!busy} onclick={() => relaunch(shown, 'restart')} title="Run it again from the start"><RotateCw size={14} />{busy === 'restart' ? 'Restarting…' : 'Restart'}</button>
							<button type="button" class="mg-btn small primary" disabled={!!busy} onclick={() => relaunch(shown, 'resume')} title="Pick up where it stopped; finished steps are kept"><RotateCcw size={14} />{busy === 'resume' ? 'Resuming…' : 'Resume'}</button>
						{/if}
					</div>
				</header>
				{#if shown.reason}<p class="why" title={shown.reason}>{shown.reason}</p>{/if}
				<div class="sum">
					{#if prog}
						<span class="bar" role="progressbar" aria-valuenow={prog.overall} aria-valuemin="0" aria-valuemax="100" aria-label="Progress"><span style="width: {prog.overall}%"></span></span>
						<span class="sum-line">
							<b>{prog.overall}%</b> | {prog.counts.done} of {prog.counts.all} steps | {going ? `${duration(shown, tickAt)} so far` : `took ${duration(shown, tickAt)}`}{going && leftText(prog.left, prog.unknown, UNTIMED_FLOOR) ? ` | ${leftText(prog.left, prog.unknown, UNTIMED_FLOOR)}` : ''}
						</span>
					{:else}
						<span class="bar" role="progressbar" aria-valuenow={plainPct} aria-valuemin="0" aria-valuemax="100" aria-label="Progress"><span style="width: {Math.max(going ? 3 : 0, plainPct)}%"></span></span>
						<span class="sum-line"><b>{plainPct}%</b> | {shown.progressText || log?.step || statusWord(shown)}</span>
					{/if}
				</div>
				{#if srcShown.length}
					<p class="srcs" title="Where its results came from (its cache report); a step's popup says more">
						<Database size={13} />
						{#if srcTotals.restoredGenome + srcTotals.restoredProtein}<span class="chip restored">{srcTotals.restoredGenome + srcTotals.restoredProtein} restored</span>{/if}
						{#if srcTotals.restoredGenome}<span class="src-n">{srcTotals.restoredGenome} genome level</span>{/if}
						{#if srcTotals.restoredProtein}<span class="src-n">{srcTotals.restoredProtein} protein level</span>{/if}
						{#if srcTotals.partly}<span class="chip partly">{srcTotals.partly} partly restored</span>{/if}
						{#if srcTotals.fresh}<span class="chip fresh">{srcTotals.fresh} run fresh</span>{/if}
						{#if srcTotals.kept}<span class="chip kept">{srcTotals.kept} kept</span>{/if}
						{#if srcDb}<span class="src-db mg-mono" title="The MARGIE database its caches are in: {srcDb}"><span dir="ltr">{srcDb}</span></span>{/if}
					</p>
				{/if}
				<details class="facts">
					<summary>Details</summary>
					<dl>
						<div><dt>Job ID</dt><dd class="mg-mono">{shown.id}</dd></div>
						<div><dt>Started</dt><dd>{when(shown.started)}</dd></div>
						<div><dt>{shown.finished ? 'Finished' : 'Running for'}</dt><dd>{shown.finished ? when(shown.finished) : duration(shown, tickAt)}</dd></div>
						{#if shown.exitCode != null}<div><dt>Exit code</dt><dd class:bad={shown.exitCode !== 0}>{shown.exitCode}</dd></div>{/if}
						{#if log?.step}<div><dt>Step</dt><dd>{log.step}</dd></div>{/if}
						{#if shown.outputDir}<div class="wide"><dt>Output folder</dt><dd><a class="mg-link mg-mono" href={folderHref(shown.outputDir)}>{shown.outputDir}</a></dd></div>{/if}
						{#if shown.files?.length}
							<div class="wide"><dt>Genomes <b>{shown.files.length}</b></dt><dd class="chips">{#each shown.files.slice(0, 24) as f (f)}<span class="mg-mono">{f}</span>{/each}{#if shown.files.length > 24}<span>+{shown.files.length - 24}</span>{/if}</dd></div>
						{/if}
						{#if shown.tools?.length}
							<div class="wide"><dt>Tools <b>{shown.tools.length}</b></dt><dd class="chips">{#each shown.tools as t (t)}<span class="mg-mono">{t}</span>{/each}</dd></div>
						{/if}
						{#if slurm.length}
							<div class="wide"><dt>SLURM jobs <b>{slurm.length}</b></dt><dd class="chips">{#each slurm as j (j)}<span class="mg-mono">{j}</span>{/each}</dd></div>
						{/if}
						{#if containers.length}
							<div class="wide"><dt>Containers <b>{containers.length}</b></dt><dd class="chips">{#each containers as c (c)}<span class="mg-mono">{c}</span>{/each}</dd></div>
						{/if}
					</dl>
				</details>
			{/if}
		</div>
		</div>
		{#if prog && shown}
			<ProgressGrid {prog} {going} runDir={shown.outputDir ?? ''} fromLog={srcFromLog} reported={!!srcRows} {elapsedOf} onLog={showLog} />
		{/if}
		<div class="term-wrap" style="height: {logHeight}px" bind:this={logEl}>
		<aside class="term" aria-label="Log of {shown ? title(shown) : 'the job'}">
			<div class="term-head">
				<span class="term-t">Log{shown ? ` of ${title(shown)}` : ''}</span>
				<span class="term-n">{logText ? `${all.length.toLocaleString('en-US')} lines${partial ? ' | the end of a longer log' : ''}${all.length > SHOWN ? `, the last ${SHOWN.toLocaleString('en-US')} shown` : ''}` : ''}</span>
				<span class="mg-grow"></span>
				{#if going}<span class="live"><i></i>Live</span>{/if}
				<button type="button" class="term-btn" aria-pressed={wrap} title="Wrap long lines" onclick={() => (wrap = !wrap)}><TextWrap size={13} />Wrap</button>
				<button type="button" class="term-btn" title="Copy the log as read (Ctrl or Cmd + C in the log does the same)" disabled={!logText.trim()} onclick={copyLog}><Copy size={13} />Copy</button>
			</div>
			{#if shown}<JobCommand run={shown} />{/if}
			{#if log?.error}<p class="term-err">{log.error}</p>{/if}
			<div class="out mg-mono" class:wrap role="textbox" aria-readonly="true" aria-multiline="true" tabindex="0" aria-label="Log text" onkeydown={logKey} bind:this={box}>{#if logText}{#each lines as l, k (k)}<span class="ln {tone(l)}">{l}</span>
{/each}{:else}<span class="dim">{shown ? (log ? 'Nothing in the log yet.' : 'Reading the log…') : ''}</span>{/if}{#if going}<span class="cursor" aria-hidden="true"></span>{/if}</div>
		</aside>
			<Resizer id={LOG} fallback={logFallback} min={260} max={2400} edge="bottom" label="Drag to make the log taller or shorter" />
		</div>
	</div>
{:else}
	<p class="empty">
		<strong>No jobs yet.</strong>
		<span>Start one on <a class="mg-link" href="/analyze">Analyze</a>. Jobs show up here with their detailed logs.</span>
	</p>
{/if}

<style>
	/* The jobs beside the picked one's line, its progress across the width, then its log.
	   Each part scrolls on its own; the page scrolls past them. */
	.board {
		display: flex;
		flex-direction: column;
		gap: 12px;
		color: var(--mg-text);
	}
	/* As tall as the job's lines need; a long list scrolls inside it. */
	.top {
		display: grid;
		grid-template-columns: var(--list-w, 300px) minmax(0, 1fr);
		grid-template-rows: minmax(0, 1fr);
		min-height: 150px;
		max-height: clamp(260px, 44vh, 520px);
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
		overflow: auto;
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


	/* One bar for the whole job, a line under it, then where its results came from. */
	.sum,
	.srcs,
	.facts {
		flex: none;
	}
	.sum {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px var(--mg-pad) 4px;
	}
	.bar {
		display: block;
		flex: 1 1 auto;
		height: 6px;
		overflow: hidden;
		border-radius: 99px;
		background: color-mix(in srgb, var(--mg-text) 10%, transparent);
	}
	.bar > span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: var(--mg-accent);
		transition: width 600ms ease;
	}
	.sum-line {
		flex: none;
		font-size: var(--mg-fs-sm);
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-2);
		white-space: nowrap;
	}
	.srcs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 8px;
		margin: 0;
		padding: 4px var(--mg-pad);
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.src-n {
		color: var(--mg-text-3);
	}
	.src-db {
		overflow: hidden;
		max-width: 46ch;
		text-overflow: ellipsis;
		white-space: nowrap;
		direction: rtl;
		color: var(--mg-text-3);
	}
	.chip {
		display: inline-block;
		padding: 1px 8px;
		border-radius: 999px;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		white-space: nowrap;
	}
	.chip.restored {
		background: color-mix(in srgb, var(--mg-accent) 15%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.chip.partly {
		background: color-mix(in srgb, var(--mg-accent) 8%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.chip.fresh {
		background: color-mix(in srgb, var(--mg-ok) 14%, transparent);
		color: var(--mg-ok);
	}
	.chip.kept {
		background: color-mix(in srgb, var(--mg-text) 8%, transparent);
		color: var(--mg-text-2);
	}
	/* Its details, folded under a line. */
	.facts {
		margin: 4px var(--mg-pad) 10px;
		font-size: var(--mg-fs-sm);
	}
	.facts summary {
		width: max-content;
		color: var(--mg-text-2);
		cursor: pointer;
	}
	.facts dl {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 8px 16px;
		margin: 8px 0 0;
	}
	.facts dl > div {
		min-width: 0;
	}
	.facts .wide {
		grid-column: 1 / -1;
	}
	.facts dt {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.facts dd {
		margin: 0;
		overflow-wrap: anywhere;
	}
	.facts dd.bad {
		color: var(--mg-danger);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}
	.chips span {
		padding: 1px 6px;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-text) 6%, transparent);
		font-size: var(--mg-fs-xs);
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
	.term-n {
		font-size: 11px;
		color: #8b949e;
		white-space: nowrap;
	}
	.live {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		font-size: 11px;
		color: color-mix(in srgb, var(--mg-ok) 75%, #fff);
	}
	.live i {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: currentColor;
	}
	.term-btn[aria-pressed='true'] {
		border-color: rgba(255, 255, 255, 0.34);
		color: #fff;
	}
	.term-err {
		margin: 0;
		padding: 4px var(--mg-pad);
		font-size: var(--mg-fs-xs);
		color: color-mix(in srgb, var(--mg-danger) 75%, #fff);
	}
	.out:not(.wrap) {
		white-space: pre;
		word-break: normal;
	}
	.ln {
		display: block;
	}
	.ln.warn {
		color: color-mix(in srgb, var(--mg-warn) 75%, #fff);
	}
	.dim {
		color: #8b949e;
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

	/* On a narrow screen the list sits above the job, and the card grows with both. */
	@media (max-width: 900px) {
		.top {
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: auto auto;
			max-height: none;
		}
		.list-pane {
			border-right: none;
			border-bottom: 1px solid var(--mg-border);
		}
		.list {
			max-height: 34vh;
		}
	}
</style>
