<script lang="ts">
	import '@fontsource/ibm-plex-sans/400.css';
	import '@fontsource/ibm-plex-sans/400-italic.css';
	import '@fontsource/ibm-plex-sans/500.css';
	import '@fontsource/ibm-plex-sans/600.css';
	import '@fontsource/ibm-plex-sans/700.css';
	import './about.css';
	import { onMount, type Snippet } from 'svelte';
	import { page } from '$app/state';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * The frame of the reading pages (Methods, FAQ, README, Contributors, Acknowledgements): a centred
	 * title block with a switch between the five pages, then one centred column of sections. Each
	 * `[data-toc]` element in the column is listed in the left margin (as chips on narrow screens),
	 * and the list marks the section being read. Text is set in IBM Plex Sans while Customize keeps
	 * its default face, and in the chosen face otherwise.
	 */
	let {
		title,
		lede = '',
		shade,
		actions,
		children
	}: { title: string; lede?: string; shade: string; actions?: Snippet; children: Snippet } = $props();

	const PAGES = [
		{ href: '/methods', label: 'Methods' },
		{ href: '/faq', label: 'FAQ' },
		{ href: '/readme', label: 'README' },
		{ href: '/contributors', label: 'Contributors' },
		{ href: '/acknowledgements', label: 'Acknowledgements' }
	];
	const font = $derived(ui.prefs.typeface === 'arial' ? '"IBM Plex Sans", system-ui, -apple-system, sans-serif' : 'var(--mg-font)');

	let main = $state<HTMLElement>();
	let sections = $state<{ id: string; label: string }[]>([]);
	let current = $state('');

	onMount(() => {
		const els = [...(main?.querySelectorAll<HTMLElement>('[data-toc][id]') ?? [])];
		sections = els.map((el) => ({ id: el.id, label: el.dataset.toc ?? el.id }));
		const seen = new Map<string, boolean>();
		const io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) seen.set(e.target.id, e.isIntersecting);
				current = sections.find((s) => seen.get(s.id))?.id ?? current;
			},
			{ rootMargin: '-15% 0px -60% 0px' }
		);
		els.forEach((el) => io.observe(el));
		return () => io.disconnect();
	});
</script>

<div class="cr-page rp" data-shade={shade} style="--rp-font: {font}">
	<header class="rp-hero">
		<nav class="rp-tabs" aria-label="About MARGIE">
			{#each PAGES as p (p.href)}
				<a href={p.href} aria-current={page.url.pathname === p.href ? 'page' : undefined}>{p.label}</a>
			{/each}
		</nav>
		<h1 class="rp-title">{title}</h1>
		{#if lede}<p class="rp-lede">{lede}</p>{/if}
		{#if actions}<div class="rp-acts">{@render actions()}</div>{/if}
		<span class="rp-rule" aria-hidden="true"></span>
		{#if sections.length > 2}
			<nav class="rp-chips" aria-label="On this page">
				{#each sections as s (s.id)}<a href="#{s.id}">{s.label}</a>{/each}
			</nav>
		{/if}
	</header>

	<div class="rp-grid">
		<div class="rp-main" bind:this={main}>{@render children()}</div>
		{#if sections.length > 2}
			<nav class="rp-toc" aria-label="On this page">
				<p>On this page</p>
				<ol>
					{#each sections as s (s.id)}
						<li><a href="#{s.id}" class:on={current === s.id}>{s.label}</a></li>
					{/each}
				</ol>
			</nav>
		{/if}
	</div>
</div>
