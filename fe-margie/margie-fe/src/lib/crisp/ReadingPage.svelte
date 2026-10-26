<script lang="ts">
	import './about.css';
	import { onMount, type Snippet } from 'svelte';
	import { page } from '$app/state';
	import { LAB } from './about';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * The frame of the reading pages (Methods, README, FAQ, Contributors, Acknowledgements): one white
	 * document with a breadcrumb, the title and the sections, and Previous and Next at its foot. Each
	 * `[data-toc]` element is listed beside the text (above it on narrow screens), the list marks the
	 * section being read, and each section heading gets a ¶ link. Text is set in Lato with Roboto Slab
	 * headings while Customize keeps its default face, and in the chosen face otherwise. The text is
	 * for reading here: citations, reference lists and `[data-copy]` parts select and copy, the rest
	 * does not.
	 */
	let {
		title,
		lede = '',
		shade,
		actions,
		crumbs = [],
		children
	}: {
		title: string;
		lede?: string;
		shade: string;
		actions?: Snippet;
		/** Pages between Home and this one in the breadcrumb. */
		crumbs?: { href: string; label: string }[];
		children: Snippet;
	} = $props();

	/** In the sidebar's order. */
	const PAGES = [
		{ href: '/methods', label: 'Methods' },
		{ href: '/readme', label: 'README' },
		{ href: '/faq', label: 'FAQ' },
		{ href: '/contributors', label: 'Contributors' },
		{ href: '/acknowledgements', label: 'Acknowledgements' }
	];
	const at = $derived(PAGES.findIndex((p) => p.href === page.url.pathname));
	const prev = $derived(at > 0 ? PAGES[at - 1] : null);
	const next = $derived(at >= 0 && at < PAGES.length - 1 ? PAGES[at + 1] : null);
	const font = $derived(ui.prefs.typeface === 'arial' ? undefined : 'var(--mg-font)');

	let doc = $state<HTMLElement>();

	/** The parts of a page that copy: citations, reference lists and BibTeX. */
	const COPYABLE = '.rp-cite, .rp-refs, .fq-refs, .fq-all, [data-copy], input, textarea';
	const host = (n: Node | null) => (n instanceof Element ? n : (n?.parentElement ?? null))?.closest(COPYABLE);
	function guard(e: ClipboardEvent) {
		const sel = getSelection();
		if (!doc || !sel || sel.isCollapsed || !sel.rangeCount) return;
		if (document.activeElement?.matches('input, textarea')) return;
		const range = sel.getRangeAt(0);
		if (!range.intersectsNode(doc)) return;
		const a = host(range.startContainer);
		if (a && a === host(range.endContainer) && doc.contains(a)) return;
		e.preventDefault();
		ui.notify('Citations and BibTeX copy from their boxes and Copy buttons.', 'info');
	}
	let sections = $state<{ id: string; label: string }[]>([]);
	let current = $state('');

	onMount(() => {
		const seen = new Map<string, boolean>();
		let io: IntersectionObserver | undefined;
		const collect = () => {
			const els = [...(doc?.querySelectorAll<HTMLElement>('[data-toc][id]') ?? [])];
			const found = els.map((el) => ({ id: el.id, label: el.dataset.toc ?? el.id }));
			if (io && found.map((s) => `${s.id}|${s.label}`).join() === sections.map((s) => `${s.id}|${s.label}`).join()) return;
			sections = found;
			for (const el of els) {
				const h = el.querySelector(':scope > h2, :scope > header h2');
				if (h && !h.querySelector('.rp-anchor')) {
					const a = Object.assign(document.createElement('a'), { className: 'rp-anchor', href: `#${el.id}`, textContent: '¶', title: 'Link to this section' });
					h.append(a);
				}
			}
			io?.disconnect();
			io = new IntersectionObserver(
				(entries) => {
					for (const e of entries) seen.set(e.target.id, e.isIntersecting);
					current = sections.find((s) => seen.get(s.id))?.id ?? current;
				},
				{ rootMargin: '-15% 0px -60% 0px' }
			);
			els.forEach((el) => io?.observe(el));
		};
		collect();
		// Sections a page adds once its content loads join the list.
		let queued = 0;
		const mo = new MutationObserver(() => {
			cancelAnimationFrame(queued);
			queued = requestAnimationFrame(collect);
		});
		if (doc) mo.observe(doc, { childList: true, subtree: true });
		return () => {
			mo.disconnect();
			io?.disconnect();
			cancelAnimationFrame(queued);
		};
	});
</script>

<svelte:document oncopy={guard} oncut={guard} />

<div class="cr-page rp" data-shade={shade} style={font ? `--rp-font: ${font}` : undefined}>
	<div class="rp-paper">
		<div class="rp-grid" class:rp-solo={sections.length <= 2}>
			<article class="rp-doc" bind:this={doc}>
				<nav class="rp-crumbs" aria-label="Breadcrumb">
					<ol>
						<li><a href="/">Home</a></li>
						{#each crumbs as c (c.href)}<li><a href={c.href}>{c.label}</a></li>{/each}
						<li aria-current="page">{title}</li>
					</ol>
					{#if actions}<div class="rp-acts">{@render actions()}</div>{/if}
				</nav>
				<h1 class="rp-title">{title}</h1>
				{#if lede}<p class="rp-lede">{lede}</p>{/if}
				{#if sections.length > 2}
					<nav class="rp-chips" aria-label="On this page">
						<b>On this page:</b>
						{#each sections as s (s.id)}<a href="#{s.id}">{s.label}</a>{/each}
					</nav>
				{/if}

				<div class="rp-main">{@render children()}</div>

				<nav class="rp-pager" aria-label="Previous and next pages">
					{#if prev}<a class="prev" href={prev.href}><span>Previous</span><b>« {prev.label}</b></a>{/if}
					{#if next}<a class="next" href={next.href}><span>Next</span><b>{next.label} »</b></a>{/if}
				</nav>
				<p class="rp-foot">MARGIE | {LAB.name}, Purdue University</p>
			</article>

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
</div>
