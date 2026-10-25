<script lang="ts">
	import { ChevronRight, ExternalLink, FileCode } from 'lucide-svelte';
	import { api } from '$lib/api';
	import CodeBlock from './CodeBlock.svelte';
	import type { FaqCode } from './faq';

	/**
	 * One FAQ code preview: a toggle that reads the block from the server's pipeline the first time
	 * it opens (/v1/code/snippet), shown with its line numbers in the file.
	 */
	let { code }: { code: FaqCode } = $props();

	interface Snippet {
		path: string;
		start: number;
		end: number;
		text: string;
		listed: boolean;
	}

	const BLOB = 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026/blob/main/be-margie/bioinformatics_tools/workflow_tools/';
	const shown = $derived(code.symbol.replace(/^rule:/, 'rule '));

	let open = $state(false);
	let snippet = $state<Snippet | null>(null);
	let error = $state('');

	function toggle() {
		open = !open;
		if (open && !snippet && !error) {
			api<Snippet>(`/code/snippet?path=${encodeURIComponent(code.path)}&symbol=${encodeURIComponent(code.symbol)}`).then(
				(r) => (snippet = r),
				(e) => (error = e?.message ?? 'The code could not be read here.')
			);
		}
	}
</script>

<div class="fc" class:open>
	<button type="button" class="fc-toggle" aria-expanded={open} onclick={toggle}>
		<ChevronRight size={14} class="fc-chev" /><FileCode size={14} />
		<span class="mg-mono fc-sym">{shown}</span><span class="fc-in">in</span><span class="mg-mono fc-path">{code.path}</span>
	</button>
	{#if open}
		<div class="fc-body">
			<p class="fc-why">{code.why}</p>
			{#if snippet}
				<CodeBlock text={snippet.text} start={snippet.start} label="{shown} in {code.path}, lines {snippet.start} to {snippet.end}" maxHeight="420px" />
				<p class="fc-links">
					Lines {snippet.start} to {snippet.end} of {code.path}
					{#if snippet.listed}| <a class="mg-link" href="/code?file={encodeURIComponent(code.path)}">the whole file</a>{/if}
					| <a class="mg-link" href={BLOB + code.path} target="_blank" rel="noreferrer">on GitHub <ExternalLink size={11} /></a>
				</p>
			{:else if error}
				<p class="fc-why">{error} <a class="mg-link" href={BLOB + code.path} target="_blank" rel="noreferrer">{code.path} on GitHub</a>.</p>
			{:else}
				<p class="fc-why">Reading {shown}…</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.fc {
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
	}
	.fc-toggle {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		width: 100%;
		padding: 7px 10px;
		border: 0;
		background: none;
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
		text-align: left;
		cursor: pointer;
	}
	.fc-toggle:hover {
		background: var(--mg-surface-2);
	}
	.fc-toggle :global(.fc-chev) {
		transition: transform 150ms ease;
	}
	.fc.open .fc-toggle :global(.fc-chev) {
		transform: rotate(90deg);
	}
	.fc-sym {
		color: var(--mg-accent);
		font-weight: 600;
	}
	.fc-in {
		color: var(--mg-text-3);
	}
	.fc-path {
		color: var(--mg-text-2);
		overflow-wrap: anywhere;
	}
	.fc-body {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 0 10px 10px;
	}
	.fc-why,
	.fc-links {
		margin: 0;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
	}
	.fc-links :global(svg) {
		vertical-align: -1px;
	}
</style>
