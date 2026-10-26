<script lang="ts">
	import { Maximize, Minimize } from 'lucide-svelte';
	import ResultsBoard from '$lib/crisp/ResultsBoard.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import RefreshButton from '$lib/workspace/blocks/RefreshButton.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { page } from '$app/state';

	/** The genomes listed: one run's (?run=) or each genome's latest result. */
	const listed = $derived(ws.resultRuns.find((r) => r.name === page.url.searchParams.get('run'))?.organisms ?? ws.results);

	/** The genomes' results folder, opened in Files from the beta note. */
	const folder = $derived(ws.resultRoots.genomesDir || ws.resultRoots.outputRoot);

	/** The whole page on the whole screen, still scrolling both ways. */
	let pageEl = $state<HTMLElement | null>(null);
	let pageFull = $state(false);
	async function togglePage() {
		if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
		else await pageEl?.requestFullscreen().catch(() => {});
	}
</script>

<svelte:head><title>Results | MARGIE</title></svelte:head>
<svelte:document onfullscreenchange={() => (pageFull = !!pageEl && document.fullscreenElement === pageEl)} />

<div class="res-scroll" bind:this={pageEl}>
	<div class="cr-page fill" data-shade="page-results">
		<div class="cr-head">
			<h1 class="cr-title">Results</h1>
			<span class="cr-meta">{listed.length ? `${listed.filter((r) => r.final?.table).length} of ${listed.length} finished` : ''}</span>
			<div class="cr-head-acts">
				<button type="button" class="mg-btn small" title={pageFull ? 'Leave full screen (Esc)' : 'The whole page on the whole screen'} onclick={togglePage}>
					{#if pageFull}<Minimize size={14} /> Exit full screen{:else}<Maximize size={14} /> Full screen{/if}
				</button>
				<RefreshButton title="Read the results again" run={() => Promise.allSettled([ws.loadResults(), ws.loadRuns()])} />
			</div>
		</div>

		<p class="res-beta">
			<b>Results is in beta</b>, and its loading speed is being improved. When a genome takes long to load, its files are in your results
			folder ({#if folder}<a class="mg-link" href={uiBase.to(`/files?path=${encodeURIComponent(folder)}`)}>open it here</a>, or find it in
			{:else}find it in{/if} <a class="mg-link" href={uiBase.to('/files')}>Files</a>): download <span class="mg-mono">FINAL_ANNOTATION_WITH_CONFIDENCE.tsv</span>
			and its Excel copy, and <span class="mg-mono">FINAL_GENOME_VIEWER.html</span>, the interactive genome map, which opens in your browser.
		</p>

		<ResultsBoard />
	</div>
</div>

<style>
	.res-beta {
		margin: 0;
		padding: var(--cr-note-pad, 10px 18px);
		border: 1px solid var(--mg-border);
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
		line-height: 1.55;
	}
	.res-beta b {
		color: var(--mg-text);
	}
	.res-beta .mg-mono {
		font-size: 0.92em;
		overflow-wrap: anywhere;
	}
	/* The page is its own scroll area, both ways, with its scroll bars always shown: the map takes the
	   wheel while the pointer is on it, and the bars still reach every corner of the page. */
	.res-scroll {
		height: 100%;
		overflow: auto;
		scrollbar-width: auto;
		scrollbar-color: color-mix(in srgb, var(--mg-text) 30%, transparent) color-mix(in srgb, var(--mg-text) 6%, transparent);
	}
	.res-scroll::-webkit-scrollbar {
		width: 12px;
		height: 12px;
	}
	.res-scroll::-webkit-scrollbar-track {
		background: color-mix(in srgb, var(--mg-text) 6%, transparent);
	}
	.res-scroll::-webkit-scrollbar-thumb {
		border: 3px solid transparent;
		border-radius: 8px;
		background: color-mix(in srgb, var(--mg-text) 30%, transparent);
		background-clip: padding-box;
	}
	.res-scroll::-webkit-scrollbar-thumb:hover {
		background-color: color-mix(in srgb, var(--mg-text) 45%, transparent);
	}
	.res-scroll::-webkit-scrollbar-corner {
		background: transparent;
	}
	.res-scroll:fullscreen {
		background: var(--mg-bg);
	}
	/* The whole window's width, and room past the last row so the scroll reaches every edge. */
	.fill {
		max-width: none;
		min-height: 100%;
		padding-bottom: 32px;
	}
</style>
