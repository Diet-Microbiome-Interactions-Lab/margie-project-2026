<script lang="ts">
	/**
	 * Notices, in the top bar instead of on the page: a bell with a count of what needs
	 * attention (what blocks a run, a run that failed or was stopped) and a short list with
	 * a link to each fix; beside it, the latest message for a few seconds, which a click opens in
	 * full until it is closed. The bell keeps the recent messages too, each opening to its full
	 * text on a click. Clear all (or an item's ×) dismisses them; a dismissed notice stays away
	 * until it changes (a new failed run, another value), even after a reload.
	 */
	import { ArrowRight, Bell, X } from 'lucide-svelte';
	import { fade, fly } from 'svelte/transition';
	import { ago } from '$lib/workspace/format';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ui, type Toast } from '$lib/workspace/ui.svelte';

	let open = $state(false);
	/** The bar's message opened in full, and the list's items opened to their full text. */
	let full = $state<Toast | null>(null);
	let wide = $state<string[]>([]);
	const toggle = (key: string) => (wide = wide.includes(key) ? wide.filter((k) => k !== key) : [...wide, key]);

	// ------------------------------------------------ dismissed notices (kept in this browser)
	const DISMISSED = 'margie.notices.dismissed';
	let dismissed = $state<string[]>(
		(() => {
			try {
				const v = JSON.parse(localStorage.getItem(DISMISSED) ?? '[]');
				return Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(-200) : [];
			} catch {
				return [];
			}
		})()
	);
	function dismiss(...keys: string[]) {
		dismissed = [...new Set([...dismissed, ...keys])].slice(-200);
		try {
			localStorage.setItem(DISMISSED, JSON.stringify(dismissed));
		} catch {
			// kept for this visit only
		}
	}

	/** What stops a run, from the readiness rows that Install also shows. */
	const blocking = $derived(
		ws.overview
			? ws.setup
					.filter((r) => r.required && r.tone !== 'ok')
					.map((r) => ({ id: r.id, key: `setup:${r.id}:${r.value}`, text: `${r.label}: ${r.value.toLowerCase()}`, href: uiBase.to(r.href ?? '/install'), tone: r.tone }))
					.filter((b) => !dismissed.includes(b.key))
			: []
	);
	/** The newest annotation, when it failed or was stopped and nothing runs now. */
	const lastBad = $derived.by(() => {
		if (ws.active) return null;
		const r = ws.runs.find((x) => x.kind === 'annotate');
		return r && (r.status === 'failed' || r.status === 'cancelled') && !dismissed.includes(`run:${r.id}:${r.status}`) ? r : null;
	});
	const count = $derived(blocking.length + (lastBad ? 1 : 0));

	/** The messages of this visit, newest first (each also shows by the bell for a moment). */
	let recent = $state<(Toast & { at: number })[]>([]);
	$effect(() => {
		const seen = new Set(recent.map((t) => t.id));
		const fresh = ui.toasts.filter((t) => !seen.has(t.id)).map((t) => ({ ...t, at: Date.now() }));
		if (fresh.length) recent = [...fresh.reverse(), ...recent].slice(0, 8);
	});
	const live = $derived(ui.toasts.at(-1) ?? null);

	/** Clears the list: messages gone, notices dismissed until they change. */
	function clearAll() {
		dismiss(...blocking.map((b) => b.key), ...(lastBad ? [`run:${lastBad.id}:${lastBad.status}`] : []));
		recent = [];
		ui.toasts = [];
	}
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key !== 'Escape') return;
		open = false;
		full = null;
	}}
/>

<span class="flash-wrap">
	{#if live}
		{#key live.id}
			<button type="button" class="flash {live.tone}" aria-live="polite" aria-expanded={full?.id === live.id} title="Click to read it all" transition:fade={{ duration: ui.ms(150) }} onclick={() => (full = full?.id === live.id ? null : live)}>{live.text}</button>
		{/key}
	{/if}
	{#if full}
		<div class="full {full.tone}" role="status" transition:fly={{ y: -6, duration: ui.ms(140) }}>
			<p>{full.text}</p>
			<button type="button" class="x" aria-label="Close" title="Close" onclick={() => (full = null)}><X size={12} /></button>
		</div>
	{/if}
</span>

<span class="relative">
	<button
		type="button"
		class="btn-icon btn-icon-lg {open ? 'preset-tonal-primary' : 'hover:preset-tonal'}"
		aria-label={count ? `${count} notice${count === 1 ? '' : 's'}` : 'Notices'}
		title={count ? `${count} thing${count === 1 ? '' : 's'} need${count === 1 ? 's' : ''} your attention` : 'Notices'}
		aria-expanded={open}
		onclick={() => (open = !open)}
	>
		<Bell />
		{#if count}<span class="badge" class:danger={blocking.some((b) => b.tone === 'danger') || lastBad?.status === 'failed'}>{count}</span>{/if}
	</button>
	{#if open}
		<button type="button" class="fixed inset-0 z-40 cursor-default" aria-label="Close the notices" onclick={() => (open = false)}></button>
		<div class="panel" role="dialog" aria-label="Notices" transition:fly={{ y: -6, duration: ui.ms(140) }}>
			<header>
				<b>Notices</b>
				<span class="grow"></span>
				{#if count || recent.length}<button type="button" class="clear" onclick={clearAll}>Clear all</button>{/if}
				<button type="button" class="btn-icon hover:preset-tonal" aria-label="Close" onclick={() => (open = false)}><X size={16} /></button>
			</header>
			{#if !count && !recent.length}
				<p class="none">Nothing needs your attention.</p>
			{/if}
			{#if blocking.length}
				<p class="h">Before a run</p>
				<ul>
					{#each blocking as b (b.id)}
						<li class={b.tone}>
							<span class="dot" aria-hidden="true"></span>
							<button type="button" class="t" class:wide={wide.includes(b.key)} aria-expanded={wide.includes(b.key)} onclick={() => toggle(b.key)}>{b.text}</button>
							<a href={b.href} onclick={() => (open = false)}>Fix <ArrowRight size={13} /></a>
							<button type="button" class="x" aria-label="Dismiss" title="Dismiss" onclick={() => dismiss(b.key)}><X size={12} /></button>
						</li>
					{/each}
				</ul>
			{/if}
			{#if lastBad}
				<p class="h">Last run</p>
				<ul>
					<li class={lastBad.status === 'failed' ? 'danger' : 'warn'}>
						<span class="dot" aria-hidden="true"></span>
						<button type="button" class="t" class:wide={wide.includes('last')} aria-expanded={wide.includes('last')} onclick={() => toggle('last')}>{lastBad.status === 'failed' ? 'Failed' : 'Stopped'} {ago(lastBad.started)}{lastBad.reason ? `: ${lastBad.reason}` : ''}</button>
						<a href={uiBase.to(`/jobs?job=${encodeURIComponent(lastBad.id)}`)} onclick={() => (open = false)}>Open <ArrowRight size={13} /></a>
						<button type="button" class="x" aria-label="Dismiss" title="Dismiss" onclick={() => lastBad && dismiss(`run:${lastBad.id}:${lastBad.status}`)}><X size={12} /></button>
					</li>
				</ul>
			{/if}
			{#if recent.length}
				<p class="h">Messages</p>
				<ul>
					{#each recent as m (m.id)}
						<li class={m.tone === 'error' ? 'danger' : m.tone === 'ok' ? 'ok' : 'info'}>
							<span class="dot" aria-hidden="true"></span>
							<button type="button" class="t" class:wide={wide.includes(`m${m.id}`)} aria-expanded={wide.includes(`m${m.id}`)} onclick={() => toggle(`m${m.id}`)}>{m.text}</button>
							<span class="when">{ago(new Date(m.at).toISOString())}</span>
							<button type="button" class="x" aria-label="Dismiss" title="Dismiss" onclick={() => (recent = recent.filter((x) => x.id !== m.id))}><X size={12} /></button>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/if}
</span>

<style>
	.relative {
		position: relative;
	}
	.grow {
		flex: 1;
	}
	.clear {
		padding: 2px 8px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-xs);
		cursor: pointer;
	}
	.clear:hover {
		border-color: var(--mg-accent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.x {
		display: inline-grid;
		flex: none;
		place-items: center;
		width: 20px;
		height: 20px;
		padding: 0;
		border: none;
		border-radius: 50%;
		background: none;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.x:hover {
		background: var(--mg-surface-2);
		color: var(--mg-text);
	}
	/* The count: small and round on the bell, amber for something to fix, red for a failure. */
	.badge {
		position: absolute;
		top: 4px;
		right: 2px;
		display: grid;
		place-items: center;
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: 9px;
		background: var(--color-warning-500, #e0a100);
		color: #1a1300;
		font-size: 11px;
		font-weight: 700;
		line-height: 1;
		box-shadow: 0 0 0 2px var(--color-surface-100-900);
	}
	.badge.danger {
		background: var(--mg-danger);
		color: #fff;
	}
	/* The latest message, in the bar for a few seconds. */
	.flash {
		max-width: min(32vw, 360px);
		overflow: hidden;
		padding: 4px 10px;
		border: none;
		border-radius: 999px;
		font-family: inherit;
		cursor: pointer;
		background: color-mix(in oklab, var(--mg-accent) 12%, var(--mg-surface));
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.flash.ok {
		background: color-mix(in oklab, var(--mg-ok) 16%, var(--mg-surface));
	}
	.flash.error {
		background: color-mix(in oklab, var(--mg-danger) 16%, var(--mg-surface));
		color: var(--mg-danger);
	}
	/* The bar's message in full, under it until closed. */
	.flash-wrap {
		position: relative;
		display: inline-flex;
	}
	.full {
		position: absolute;
		top: calc(100% + 8px);
		right: 0;
		z-index: 50;
		display: flex;
		align-items: flex-start;
		gap: 8px;
		width: min(420px, 90vw);
		padding: 10px 10px 10px 14px;
		border: 1px solid var(--mg-border);
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: 0 10px 30px rgb(0 0 0 / 0.16);
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
		line-height: 1.5;
	}
	.full.ok {
		border-left-color: var(--mg-ok);
	}
	.full.error {
		border-left-color: var(--mg-danger);
	}
	.full p {
		flex: 1;
		margin: 0;
		overflow-wrap: anywhere;
	}
	.panel {
		position: absolute;
		top: calc(100% + 8px);
		right: 0;
		z-index: 50;
		width: min(360px, 90vw);
		max-height: 70vh;
		overflow: auto;
		padding: 8px 10px 10px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: 0 10px 30px rgb(0 0 0 / 0.16);
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
	}
	.panel header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 2px 2px 6px;
	}
	.h {
		margin: 8px 2px 4px;
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.none {
		margin: 6px 2px;
		color: var(--mg-text-3);
	}
	ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 4px;
		border-radius: var(--mg-r-sm);
	}
	li:hover {
		background: var(--mg-surface-2);
	}
	.dot {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--mg-accent);
	}
	li.warn .dot {
		background: var(--color-warning-500, #e0a100);
	}
	li.danger .dot {
		background: var(--mg-danger);
	}
	li.ok .dot {
		background: var(--mg-ok);
	}
	/* An item's text on one line; a click opens it to its full text. */
	.t {
		flex: 1;
		min-width: 0;
		padding: 0;
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		cursor: pointer;
	}
	.t.wide {
		overflow: visible;
		white-space: normal;
		overflow-wrap: anywhere;
	}
	li:has(.t.wide) {
		align-items: flex-start;
	}
	li a {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		flex: none;
		color: var(--mg-accent-ink);
		font-weight: 600;
	}
	.when {
		flex: none;
		font-size: 11px;
		color: var(--mg-text-3);
	}
	@media (max-width: 980px) {
		.flash {
			display: none;
		}
	}
</style>
