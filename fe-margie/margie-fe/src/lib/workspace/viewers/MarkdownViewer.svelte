<script lang="ts">
	import './tools.css';
	import { api } from '$lib/api';
	import Markdown from './Markdown.svelte';

	/** A Markdown file rendered as GitHub shows a README: headings, lists, tables, code and quotes. */
	let { path }: { path: string } = $props();

	let text = $state('');
	let truncated = $state(false);
	let error = $state('');
	let loading = $state(true);

	$effect(() => {
		const p = path;
		loading = true;
		api<{ content: string; binary: boolean; truncated: boolean }>(`/files/text?path=${encodeURIComponent(p)}`)
			.then((d) => {
				if (p !== path) return;
				truncated = d.truncated;
				text = d.content;
				error = '';
			})
			.catch((e) => (error = e instanceof Error ? e.message : String(e)))
			.finally(() => (loading = false));
	});
</script>

<div class="md vw-pane">
	{#if error}
		<p class="md-note bad">{error}</p>
	{:else if loading}
		<p class="md-note">Reading…</p>
	{:else}
		{#if truncated}<p class="md-note">The first megabyte only.</p>{/if}
		<Markdown source={text} />
	{/if}
</div>

<style>
	.md {
		height: 100%;
		min-height: 0;
		overflow: auto;
		padding: 20px 28px 32px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
	}
	.md-note {
		margin: 0 0 12px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-3);
	}
	.md-note.bad {
		color: var(--mg-danger);
	}
</style>
