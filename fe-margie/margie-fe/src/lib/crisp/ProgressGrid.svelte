<script lang="ts">
	import { Check, X } from 'lucide-svelte';
	import { cachedOn, sourceSay } from '$lib/crisp/cache-report';
	import { formatBytes } from '$lib/api';
	import { leftText, span, type Progress, type RowProgress } from '$lib/crisp/progress-model';
	import { uiBase } from '$lib/workspace/base.svelte';
	import Resizer from '$lib/workspace/motion/Resizer.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import Fold from '$lib/workspace/motion/Fold.svelte';
	import FoldToggle from '$lib/workspace/motion/FoldToggle.svelte';

	/**
	 * A run's progress, genome by step: a pie per step (done, running, failed, not started, not
	 * used), a dot on the ones restored from the MARGIE database. A pie opens what is known about
	 * that step (its state, where its results came from, its times, its folder); a genome's name,
	 * that genome's. Scrolls both ways for hundreds of genomes.
	 */
	let {
		prog,
		going,
		runDir = '',
		fromLog = false,
		reported = true,
		elapsedOf = () => '',
		onLog
	}: {
		prog: Progress;
		/** Whether the run is still going (times left, steps under way). */
		going: boolean;
		/** The run's folder; a genome's results are in <runDir>/<genome>. */
		runDir?: string;
		/** Its sources were rebuilt from its log (a run from before reports). */
		fromLog?: boolean;
		/** Whether the run kept a cache report or a log that says where results came from. */
		reported?: boolean;
		/** How long a genome has been going ('' when not going). */
		elapsedOf?: (g: string) => string;
		/** Shows the run's log, for a step that failed. */
		onLog?: () => void;
	} = $props();

	const STATE_WORD: Record<string, string> = { done: 'Done', run: 'Running', wait: 'Running', failed: 'Failed', partial: 'Stopped before it finished', none: 'Not started', na: 'Not chosen' };
	const ROW_WORD: Record<RowProgress['state'], string> = { done: 'Done', running: 'Running', failed: 'Failed', stopped: 'Stopped before it finished', queued: 'Not started' };

	/** The pie or genome clicked, and where it was clicked (the popup is placed by fit). */
	let pick = $state<{ g: string; t: string; x: number; y: number } | null>(null);
	const picked = $derived.by(() => {
		if (!pick) return null;
		const row = prog.rows.find((r) => r.g === pick!.g);
		if (!row) return null;
		const c = pick.t ? row.cells.find((x) => x.t === pick!.t) : undefined;
		return { row, c };
	});
	function open(g: string, t: string, e: MouseEvent) {
		const W = 340;
		const x = Math.min(Math.max(8, e.clientX - W / 2), window.innerWidth - W - 8);
		pick = pick?.g === g && pick?.t === t ? null : { g, t, x, y: e.clientY };
	}
	/**
	 * Keeps the popup inside the window as its content changes: below the click when it fits, else
	 * above it, else from the top with its own scroll (max-height in the styles).
	 */
	function fit(node: HTMLElement, y: number) {
		const place = () => {
			const h = node.offsetHeight;
			const room = window.innerHeight;
			let top = y + 14;
			if (top + h > room - 8) top = y - h - 12 >= 8 ? y - h - 12 : Math.max(8, room - h - 8);
			node.style.top = `${top}px`;
		};
		const watch = new ResizeObserver(place);
		watch.observe(node);
		window.addEventListener('resize', place);
		place();
		return {
			update(next: number) {
				y = next;
				place();
			},
			destroy() {
				watch.disconnect();
				window.removeEventListener('resize', place);
			}
		};
	}
	/** Mounts the popup at the interface's root, so no page transform moves it off the pie. */
	function toRoot(node: HTMLElement) {
		(node.closest('[data-mg-root]') ?? document.querySelector('[data-mg-root]') ?? document.body).appendChild(node);
		return { destroy: () => node.remove() };
	}
	/** A genome's steps by where their results came from. */
	function sourcesOf(row: RowProgress) {
		const on = row.cells.filter((c) => c.state !== 'na' && c.src && c.src.source !== 'not run');
		return {
			restored: on.filter((c) => c.src!.source === 'restored').length,
			partly: on.filter((c) => c.src!.source === 'partly restored').length,
			fresh: on.filter((c) => c.src!.source === 'fresh').length,
			kept: on.filter((c) => c.src!.source === 'kept').length
		};
	}
	/** The grid's height: room for 50 genomes (26 px rows under about 152 px of headings and totals), then as dragged. */
	const GRID = 'jobs:grid';
	/** The section folds away with Hide (remembered). */
	const FOLD = 'jobs:progress';
	const GRID_FALLBACK = 152 + 50 * 26;
	const gridMax = $derived(ui.size(GRID, GRID_FALLBACK));
	const folderOf = (g: string) => (runDir ? uiBase.to(`/files?path=${encodeURIComponent(`${runDir.replace(/\/$/, '')}/${g}`)}`) : '');
</script>

<section class="card gridcard" aria-label="Progress by genome and step">
	<header class="ghead">
		<h2>Progress</h2>
		<span class="count">{prog.rows.length} genome{prog.rows.length === 1 ? '' : 's'} | {prog.counts.done} of {prog.counts.all} steps done</span>
		<span class="mg-grow"></span>
		<ul class="key" aria-label="Key">
			<li><span class="pie done" style="--p: 100"><Check size={9} strokeWidth={3.5} /></span>done</li>
			<li><span class="pie run" style="--p: 40"></span>running</li>
			<li><span class="pie failed"><X size={9} strokeWidth={3.5} /></span>failed</li>
			<li><span class="pie none"></span>not started</li>
			<li><span class="pie na"></span>not chosen</li>
			<li title="Its results came from the MARGIE database: the whole output (genome level) or every protein (protein level); a paler dot, only some proteins"><span class="pie done fromdb" style="--p: 100"><Check size={9} strokeWidth={3.5} /></span>restored</li>
		</ul>
		<FoldToggle id={FOLD} />
	</header>
	<Fold id={FOLD}>
	{#if prog.rows.length && prog.cols.length}
		<div class="gwrap">
		<div class="scroller" style="max-height: {gridMax}px">
			<table class="pgrid" aria-label="Progress, by genome and step">
				<thead>
					<tr class="phases">
						<th class="corner" rowspan="2" scope="col">Genome</th>
						{#each prog.phases as g (g.label)}<th colspan={g.cols.length} scope="colgroup">{g.label}</th>{/each}
					</tr>
					<tr class="tools">
						{#each prog.phases as g (g.label)}
							{#each g.cols as t, i (t)}<th scope="col" class:first={i === 0}><span>{t}</span></th>{/each}
						{/each}
					</tr>
					<!-- each step across every genome -->
					<tr class="totals">
						<th scope="row" class="gname" title="All genomes: {prog.overall}% of their steps done">
							<span class="gn">
								<span class="pie big" class:done={prog.overall === 100} style="--p: {prog.overall}" aria-hidden="true">
									{#if prog.overall === 100}<Check size={9} strokeWidth={3.5} />{/if}
								</span>
								<span class="nm">All genomes</span>
								<span class="gpct">{prog.overall}%</span>
							</span>
						</th>
						{#each prog.columns as c (c.t)}
							{@const st = c.pct === null ? 'na' : c.pct === 100 ? 'done' : c.failed ? 'failed' : c.pct > 0 ? 'run' : 'none'}
							<th
								class:first={prog.firsts.has(c.t)}
								title={c.pct === null
									? `${c.t}: not chosen`
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
					{#each prog.rows as row (row.g)}
						<tr>
							<th scope="row" class="gname">
								<button type="button" class="gn rowlink" title="{row.g}: {row.pct}% of its steps done | click for details" aria-expanded={pick?.g === row.g && !pick?.t} onclick={(e) => open(row.g, '', e)}>
									<span class="pie big" class:done={row.pct === 100} class:failed={row.state === 'failed'} style="--p: {row.pct}" aria-hidden="true">
										{#if row.pct === 100}<Check size={9} strokeWidth={3.5} />{:else if row.state === 'failed'}<X size={9} strokeWidth={3.5} />{/if}
									</span>
									<span class="nm">{row.g}</span>
									<span class="gpct">{row.pct}%</span>
								</button>
							</th>
							{#each row.cells as c (c.t)}
								{@const mark = c.state === 'done' ? 'tick' : c.state === 'failed' ? 'cross' : ''}
								<td class:first={prog.firsts.has(c.t)} title="{row.g} | {c.t}: {c.say}{c.state === 'na' ? '' : ' | click for details'}">
									{#if c.state === 'na'}
										<span class="pie na" style="--p: 0"></span>
									{:else}
										<button
											type="button"
											class="cellink"
											aria-label="{row.g} {c.t}: {c.say}"
											aria-expanded={pick?.g === row.g && pick?.t === c.t}
											onclick={(e) => open(row.g, c.t, e)}
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
			<Resizer id={GRID} fallback={GRID_FALLBACK} min={200} max={8000} edge="bottom" label="Drag to show more or fewer genomes" />
		</div>
	{:else}
		<p class="mg-note empty">No genomes in view yet: they appear as the run's jobs start.</p>
	{/if}
	</Fold>
</section>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (pick = null)} />
{#if picked && pick}
	{@const row = picked.row}
	{@const c = picked.c}
	<div class="popwrap" use:toRoot>
		<button type="button" class="pop-scrim" aria-label="Close" onclick={() => (pick = null)}></button>
		<div class="pop" role="dialog" aria-label={c ? `${c.t} on ${row.g}` : row.g} style="left: {pick.x}px" use:fit={pick.y}>
			{#if c}
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
					{#if c.jobs?.length}
						<dt>SLURM job{c.jobs.length === 1 ? '' : 's'}</dt>
						<dd class="pop-jobs">
							{#each c.jobs as j (j.id)}<span><span class="mg-mono">{j.id}</span> {j.rule} | {j.status}</span>{/each}
						</dd>
					{/if}
					{#if c.store}
						<dt>Results file</dt>
						<dd class="pop-file">{#if c.store.file}<span class="mg-mono">{c.store.file.name}</span>, {formatBytes(c.store.file.size)}{:else}being written{/if}</dd>
						<dt>In the database</dt>
						<dd class:pop-yes={c.store.loaded}>{c.store.loaded ? 'yes, loaded into the MARGIE database (SQLite)' : 'waiting to be loaded'}</dd>
					{/if}
					{#if c.src && c.src.source !== 'not run'}
						<dt>Results</dt>
						<dd>{sourceSay(c.src)}</dd>
						{#if c.src.stage}<dt>Stage</dt><dd>{c.src.stage}</dd>{/if}
						{#if c.src.database}
							<dt>Database</dt>
							<dd class="mg-mono pop-db" title={c.src.database}>{c.src.database}</dd>
						{/if}
					{:else if c.state === 'done' && (fromLog || !reported)}
						<dt>Results</dt>
						<dd>
							{fromLog
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
					{#if going && (c.state === 'run' || c.state === 'wait' || c.state === 'none')}
						<dt>Left</dt>
						<dd>{c.left === null ? 'its first run here: timed once it has run' : `about ${span(c.left)}`}</dd>
					{/if}
					<dt>This genome</dt>
					<dd>{row.pct}%, {row.done} of {row.of} steps{going && leftText(row.left, row.untimed) ? `, ${leftText(row.left, row.untimed)}` : ''}</dd>
					<dt>Whole job</dt>
					<dd>{prog.overall}%, {prog.counts.done} of {prog.counts.all} steps{going && leftText(prog.left, prog.untimed) ? `, ${leftText(prog.left, prog.untimed)}` : ''}</dd>
				</dl>
				<div class="pop-acts">
					{#if c.state === 'failed' && onLog}
						<button type="button" class="mg-btn small" onclick={() => { pick = null; onLog?.(); }}>Show the log</button>
					{:else if c.href}
						<a class="mg-btn small" href={c.href} onclick={() => (pick = null)}>Open its folder</a>
					{/if}
				</div>
			{:else}
				{@const from = sourcesOf(row)}
				<header class="pop-head">
					<span class="pie big" class:done={row.pct === 100} style="--p: {row.pct}">
						{#if row.pct === 100}<Check size={9} strokeWidth={3.5} />{/if}
					</span>
					<span class="pop-title"><b>This genome</b><span class="mg-mono" title={row.g}>{row.g}</span></span>
					<button type="button" class="pop-x" aria-label="Close" onclick={() => (pick = null)}><X size={14} /></button>
				</header>
				<dl class="pop-rows">
					<dt>Progress</dt>
					<dd>{ROW_WORD[row.state]}, {row.pct}% | {row.done} of {row.of} steps</dd>
					{#if row.running.length}<dt>Running now</dt><dd>{row.running.join(' | ')}</dd>{/if}
					{#if elapsedOf(row.g)}<dt>Time so far</dt><dd>{elapsedOf(row.g)}</dd>{/if}
					{#if going && row.state !== 'done' && leftText(row.left, row.untimed)}<dt>Left</dt><dd>{leftText(row.left, row.untimed)}</dd>{/if}
					{#if from.restored + from.partly + from.fresh + from.kept}
						<dt>Results</dt>
						<dd>
							{[
								from.restored && `${from.restored} restored from the database`,
								from.partly && `${from.partly} partly restored`,
								from.kept && `${from.kept} kept from an earlier attempt`,
								from.fresh && `${from.fresh} run fresh`
							]
								.filter(Boolean)
								.join(' | ')}
						</dd>
					{/if}
				</dl>
				{#if folderOf(row.g)}
					<div class="pop-acts"><a class="mg-btn small" href={folderOf(row.g)} onclick={() => (pick = null)}>Open its folder</a></div>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.card {
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		color: var(--mg-text);
		background: var(--cr-card, var(--mg-surface));
		box-shadow: var(--cr-card-shadow, none);
	}
	/* A genome's name opens its popup. */
	.rowlink {
		width: 100%;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.rowlink:hover .nm {
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.rowlink:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: -2px;
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
	.ghead h2 {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
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
	.pop-jobs {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	/* Scrolls both ways; as tall as dragged at its bottom edge (room for 50 genomes to start with). */
	.gwrap {
		position: relative;
	}
	.scroller {
		min-height: 160px;
		overflow: auto;
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
		max-height: calc(100vh - 16px);
		overflow-y: auto;
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
	/* Under way: amber, unlike done's blue, filled as far as its own tool has got (a pale disc when
	   there is nothing to estimate from), glowing and pulsing while SLURM runs it. */
	.pie.run,
	.pie.wait {
		--run: #f59e0b;
		border-color: var(--run);
		background: conic-gradient(var(--run) calc(var(--p) * 1%), color-mix(in srgb, var(--run) 32%, transparent) 0);
		animation: glow 1.6s ease-in-out infinite;
	}
	.pie.run {
		transition: --p 2s linear;
	}
	@keyframes glow {
		0%,
		100% {
			box-shadow: 0 0 0 0 color-mix(in srgb, var(--run) 0%, transparent);
			filter: brightness(1);
		}
		50% {
			box-shadow: 0 0 7px 2px color-mix(in srgb, var(--run) 75%, transparent);
			filter: brightness(1.18);
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
