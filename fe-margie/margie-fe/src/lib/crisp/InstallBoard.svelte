<script lang="ts">
	import { tick } from 'svelte';
	import { Check } from 'lucide-svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws, type CheckRow, type SetupRow } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import SetupPage from '$lib/workspace/pages/SetupPage.svelte';
	import BuildBar from '$lib/workspace/blocks/BuildBar.svelte';

	/**
	 * The Install page: two boxes, what is ready (ring and checklist) beside what a run can use
	 * (the tools by phase), above SetupPage, which holds every control. A checklist line opens
	 * its card below or the page that puts it right.
	 */

	const o = $derived(ws.overview);
	const cluster = $derived(!!backend.cluster);
	const building = $derived(ws.active?.kind === 'build' || ws.active?.kind === 'setup' ? ws.active : null);
	// ------------------------------------------------ the ring
	const ready = $derived(ws.setupReady);
	const R = 44;
	const C = 2 * Math.PI * R;
	const frac = $derived(ready.total ? ready.ok / ready.total : 0);
	const allReady = $derived(!!o && ready.total > 0 && ready.ok === ready.total);

	// ------------------------------------------------ your databases (cluster): copied to scratch once
	$effect(() => {
		if (cluster) ws.loadStores();
	});
	const stores = $derived(cluster ? ws.stores : null);

	// ------------------------------------------------ the tools a run can use, by phase
	const phases = $derived.by(() => {
		const by = new Map<number | null, typeof ws.tools>();
		for (const t of ws.tools) by.set(t.phase ?? null, [...(by.get(t.phase ?? null) ?? []), t]);
		return [...by.entries()].sort((a, b) => (a[0] ?? 99) - (b[0] ?? 99));
	});

	// ------------------------------------------------ bringing a row of the detail into view
	let detail = $state<HTMLElement | null>(null);

	async function reveal(fold: string | null, find: (root: HTMLElement) => Element | null | undefined) {
		// Install's cards start folded, so one never opened counts as folded.
		const opening = !!fold && ui.isFolded(fold, true);
		if (opening && fold) ui.setFolded(fold, false);
		await tick();
		setTimeout(
			() => {
				const el = detail && find(detail);
				if (!(el instanceof HTMLElement)) return;
				const off = ui.motion === 'off';
				el.scrollIntoView({ behavior: off ? 'auto' : 'smooth', block: 'center' });
				if (off) return;
				const accent = getComputedStyle(el).getPropertyValue('--mg-accent').trim() || 'currentColor';
				el.animate([{ backgroundColor: `color-mix(in srgb, ${accent} 20%, transparent)` }, { backgroundColor: 'transparent' }], {
					duration: 1800,
					delay: ui.ms(300),
					easing: 'ease-out'
				});
			},
			opening ? ui.ms(440) : 0
		);
	}

	/** Where a line of the checklist is put right: a card below, or a page of its own. */
	const LOCAL: Record<string, { fold: string; shade: string } | string> = {
		runtime: { fold: 'setup:container-app', shade: 'container-app' },
		repo: { fold: 'setup:build-folder', shade: 'build-recipes' },
		images: { fold: 'setup:tools', shade: 'tools' },
		databases: { fold: 'setup:reference-data', shade: 'reference-data' },
		python: { fold: 'setup:python', shade: 'python' },
		licences: '/settings#licences',
		gtdbtk: '/settings#RUN_GTDBTK'
	};
	function target(r: SetupRow): { href: string } | { fold: string; find: (root: HTMLElement) => Element | null } | null {
		const href = r.href ?? (cluster ? undefined : typeof LOCAL[r.id] === 'string' ? (LOCAL[r.id] as string) : undefined);
		if (href && !href.startsWith('/setup')) return { href: uiBase.to(href) };
		if (href) {
			const id = href.split('#')[1];
			return id
				? { fold: `setup:${id}`, find: (root) => root.querySelector(`#${CSS.escape(id)}`) }
				: { fold: '', find: (root) => root };
		}
		const at = LOCAL[r.id];
		if (at && typeof at !== 'string') return { fold: at.fold, find: (root) => root.querySelector(`[data-shade="${at.shade}"]`) };
		return null;
	}
</script>

{#snippet mark(status: CheckRow['status'] | 'ok' | 'warn' | 'none')}
	<span class="ib-badge {status}" aria-hidden="true">
		{#if status === 'ok'}<Check size={10} strokeWidth={4} />{:else if status === 'missing' || status === 'warn'}!{:else if status === 'unknown'}?{/if}
	</span>
{/snippet}

{#if building}
	<div class="ib-now" role="status">
		<span class="ib-spinner" aria-hidden="true"></span>
		<span class="ib-now-text">
			<strong>{building.label}</strong>
			<span class="mg-note">{ws.lastLine || 'Starting'}</span>
		</span>
		<span class="ib-now-bar"><BuildBar percent={building.progress ?? 0} /></span>
		<a class="mg-link" href={uiBase.to(`/jobs/${building.id}`)}>Log</a>
		<button type="button" class="mg-link quiet ib-stop" onclick={() => building && ws.stop(building.id)}>Stop</button>
	</div>
{/if}

<!-- Two boxes of one height, as on Home's drawing of the page: what is ready, and what a run can use. -->
<div class="ib-pair">
	<section class="ib-box" aria-labelledby="ib-ready">
		<header class="ib-head">
			<h2 id="ib-ready">Ready to run</h2>
			<span class="mg-note">{cluster ? `on ${backend.host || 'the cluster'}` : 'on this computer'}</span>
			<span class="mg-grow"></span>
			{#if !cluster}
				<button type="button" class="mg-link quiet" disabled={ws.checking} onclick={() => ws.loadCheck()}>{ws.checking ? 'Checking' : 'Check again'}</button>
			{/if}
		</header>
		<div class="ib-gauge">
			<svg viewBox="0 0 110 110" class="ib-ring" class:all={allReady} role="img" aria-label="{ready.ok} of {ready.total} ready">
				<circle class="bg" cx="55" cy="55" r={R} />
				<circle class="fg" cx="55" cy="55" r={R} stroke-dasharray="{C * frac} {C}" transform="rotate(-90 55 55)" />
				<text x="55" y="61" text-anchor="middle">{o ? `${ready.ok}/${ready.total}` : '…'}</text>
			</svg>
			<b>{allReady ? 'Ready to run' : o ? `${ready.total - ready.ok} to set up` : cluster ? 'Reaching the cluster' : 'Reading'}</b>
		</div>
		<ul class="ib-checks">
			{#each ws.setup as r (r.id)}
				{@const go = target(r)}
				<li class="ib-t-{r.tone}">
					{#if go && 'href' in go}
						<a class="ib-check" href={go.href} title={r.detail}>
							{@render mark(r.tone === 'ok' ? 'ok' : r.tone === 'neutral' ? 'none' : 'warn')}
							<span class="lbl">{r.label}</span><span class="val">{r.value}</span>
						</a>
					{:else}
						<button type="button" class="ib-check" title={r.detail} disabled={!go} onclick={() => go && reveal(go.fold, go.find)}>
							{@render mark(r.tone === 'ok' ? 'ok' : r.tone === 'neutral' ? 'none' : 'warn')}
							<span class="lbl">{r.label}</span><span class="val">{r.value}</span>
						</button>
					{/if}
				</li>
			{:else}
				<li class="mg-note">{cluster ? 'Reaching the cluster…' : 'Reading…'}</li>
			{/each}
			{#if stores}
				<!-- Your working copies of MARGIE's databases: a first run copies them, or set them up here first. -->
				<li class="ib-t-{stores.ready ? 'ok' : 'warn'}">
					{#if stores.ready || ws.storesBusy}
						<a class="ib-check" href={uiBase.to('/settings#databases')} title={stores.root}>
							{@render mark(stores.ready ? 'ok' : 'warn')}
							<span class="lbl">Your databases</span><span class="val">{stores.ready ? 'set up' : 'copying…'}</span>
						</a>
					{:else}
						<button type="button" class="ib-check" title="A one-time copy from your group's folder to your databases folder" onclick={() => ws.setupStores()}>
							{@render mark('warn')}
							<span class="lbl">Your databases</span><span class="val">not set up: set up now</span>
						</button>
					{/if}
				</li>
			{/if}
		</ul>
	</section>

	<section class="ib-box" aria-labelledby="ib-use">
		<header class="ib-head">
			<h2 id="ib-use">What a run can use</h2>
			<span class="mg-note">{ws.tools.length ? `${ws.tools.length} tools in ${phases.length} phase${phases.length === 1 ? '' : 's'}` : ''}</span>
		</header>
		<p class="mg-note mg-explain">The tools Analyze can add to a run, by the phase they run in. Gene calling and scoring are part of every run.</p>
		<ol class="ib-phases">
			{#each phases as [n, tools] (n)}
				<li>
					<span class="ib-ph">{n === null ? 'Other' : `Phase ${n}`}</span>
					<span class="ib-names">
						{#each tools as t (t.name)}<span class="ib-tool" class:off={t.gated} title={t.gated ? `${t.label ?? t.name}: off until its licence is accepted` : undefined}>{t.label ?? t.name}</span>{/each}
					</span>
				</li>
			{:else}
				<li class="mg-note">Reading the tools…</li>
			{/each}
		</ol>
	</section>
</div>

<div class="ib-detail" bind:this={detail}>
	<SetupPage />
</div>

<style>
	/* ---- two boxes of one height ---- */
	.ib-pair {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--cr-stack, 16px);
		align-items: stretch;
		color: var(--mg-text);
	}
	.ib-box {
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-width: 0;
		padding: var(--cr-box-pad, 16px 18px);
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
	}
	.ib-head {
		display: flex;
		align-items: baseline;
		gap: 10px;
	}
	.ib-head h2 {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.ib-box > .mg-note {
		margin: 0;
	}
	.ib-now {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px calc(var(--mg-pad) * 1.2);
		border: 1px solid color-mix(in srgb, var(--mg-accent) 35%, var(--mg-border));
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-accent) 8%, var(--cr-card, var(--mg-surface)));
		font-size: var(--mg-fs-sm);
	}
	.ib-now-text {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
	}
	.ib-now-text > * {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.ib-now-bar {
		flex: 0 1 260px;
		min-width: 140px;
	}
	.ib-spinner {
		flex: none;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 2.5px solid color-mix(in srgb, var(--mg-accent) 30%, transparent);
		border-top-color: var(--mg-accent);
		animation: ib-spin 900ms linear infinite;
	}

	/* ---- the marks ---- */
	.ib-badge {
		position: absolute;
		right: -3px;
		bottom: 0;
		display: grid;
		place-items: center;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 2px solid var(--mg-surface);
		background: var(--mg-text-3);
		color: #fff;
		font-size: 10px;
		font-weight: 800;
		line-height: 1;
	}
	.ib-badge.ok {
		background: var(--mg-ok);
	}
	.ib-badge.missing,
	.ib-badge.warn {
		background: var(--mg-warn);
	}
	.ib-badge.optional,
	.ib-badge.none {
		display: none;
	}

	.ib-gauge {
		display: flex;
		align-items: center;
		gap: 14px;
	}
	.ib-gauge b {
		font-size: var(--mg-fs-lg);
		font-weight: 650;
	}
	.ib-ring {
		flex: none;
		width: 64px;
		height: 64px;
	}
	.ib-ring .bg,
	.ib-ring .fg {
		fill: none;
		stroke-width: 10;
	}
	.ib-ring .bg {
		stroke: var(--mg-border);
	}
	.ib-ring .fg {
		stroke: var(--mg-warn);
		stroke-linecap: round;
		transition: stroke-dasharray var(--mo-3, 420ms) cubic-bezier(0.2, 0.7, 0.2, 1);
	}
	.ib-ring.all .fg {
		stroke: var(--mg-ok);
	}
	.ib-ring text {
		fill: var(--mg-text);
		font-family: var(--mg-font);
		font-size: 20px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.ib-checks {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 2px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.ib-check {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		min-height: 34px;
		padding: 4px 6px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-sm);
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}
	.ib-check:disabled {
		cursor: default;
	}
	.ib-check:hover:not(:disabled) {
		background: var(--mg-surface-2);
	}
	/* In the list the mark sits in line, before the name. */
	.ib-check .ib-badge {
		position: static;
		flex: none;
		border: none;
	}
	.ib-check .ib-badge.none {
		display: block;
		width: 16px;
		height: 16px;
		background: none;
		border: 2px solid var(--mg-border-strong);
	}
	.ib-check .lbl {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.ib-check .val {
		max-width: 50%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--mg-text-2);
		font-variant-numeric: tabular-nums;
	}
	.ib-t-warn .ib-check .val,
	.ib-t-danger .ib-check .val {
		color: var(--mg-warn);
	}
	/* ---- the tools by phase, one row each: the phase, then its tools ---- */
	.ib-phases {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.ib-phases > li {
		display: grid;
		grid-template-columns: 76px minmax(0, 1fr);
		align-items: baseline;
		gap: 12px;
		min-width: 0;
		padding: 9px 0;
		border-top: 1px solid var(--mg-border);
	}
	.ib-phases > li:first-child {
		border-top: none;
	}
	.ib-ph {
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-3);
		white-space: nowrap;
	}
	.ib-names {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		min-width: 0;
	}
	.ib-tool {
		padding: 1px 7px;
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
		font-size: var(--mg-fs-xs);
		white-space: nowrap;
	}
	.ib-tool.off {
		color: var(--mg-text-3);
		text-decoration: line-through;
	}

	/* ---- the detail below ---- */
	.ib-detail {
		display: flex;
		flex-direction: column;
	}
	.ib-stop {
		padding: 0;
		border: none;
		background: none;
		font: inherit;
		cursor: pointer;
	}

	@keyframes ib-spin {
		to {
			transform: rotate(360deg);
		}
	}
	:global([data-motion='off']) .ib-pair *,
	:global([data-motion='off']) .ib-now * {
		animation: none !important;
		transition: none !important;
	}

	@media (max-width: 900px) {
		.ib-pair {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
