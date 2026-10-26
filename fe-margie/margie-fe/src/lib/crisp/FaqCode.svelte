<script lang="ts">
	import { ChevronRight, ExternalLink } from 'lucide-svelte';
	import { api } from '$lib/api';
	import CodeBlock from './CodeBlock.svelte';
	import CodeUnlock from './CodeUnlock.svelte';
	import { isCodeLocked } from '$lib/cluster/code-key';
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
	const kind = $derived(code.path.endsWith('.smk') ? 'SMK' : code.path.endsWith('.py') ? 'PY' : (code.path.split('.').pop() ?? '').toUpperCase());

	let open = $state(false);
	let snippet = $state<Snippet | null>(null);
	let error = $state('');
	/** The server keeps the code behind its password, and this visit has not given it yet. */
	let locked = $state(false);

	function load() {
		locked = false;
		api<Snippet>(`/code/snippet?path=${encodeURIComponent(code.path)}&symbol=${encodeURIComponent(code.symbol)}`).then(
			(r) => (snippet = r),
			(e) => (isCodeLocked(e) ? (locked = true) : (error = e?.message ?? 'The code could not be read here.'))
		);
	}

	function toggle() {
		open = !open;
		if (open && !snippet && !error) load();
	}
</script>

<div class="fc" class:open>
	<button type="button" class="fc-toggle" aria-expanded={open} onclick={toggle}>
		<span class="fc-kind">{kind}</span>
		<span class="fc-main">
			<span class="mg-mono fc-sym">{shown}</span>
			<span class="mg-mono fc-path">{code.path}</span>
			<span class="fc-why">{code.why}</span>
		</span>
		<span class="fc-act">{open ? 'Hide code' : 'Show code'} <ChevronRight size={16} class="fc-chev" /></span>
	</button>
	{#if open}
		<div class="fc-body">
			{#if snippet}
				<CodeBlock text={snippet.text} start={snippet.start} label="{shown} in {code.path}, lines {snippet.start} to {snippet.end}" maxHeight="480px" />
				<p class="fc-links">
					Lines {snippet.start} to {snippet.end} of {code.path}
					{#if snippet.listed}| <a class="mg-link" href="/code?file={encodeURIComponent(code.path)}">the whole file</a>{/if}
					| <a class="mg-link" href={BLOB + code.path} target="_blank" rel="noreferrer">on GitHub <ExternalLink size={12} /></a>
				</p>
			{:else if locked}
				<CodeUnlock onopen={load} />
			{:else if error}
				<p class="fc-links">{error} <a class="mg-link" href={BLOB + code.path} target="_blank" rel="noreferrer">{code.path} on GitHub</a>.</p>
			{:else}
				<p class="fc-links">Reading {shown}…</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	/* A code link: a card with the function, its file and what it does; it opens to the code. */
	.fc {
		overflow: hidden;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-radius: 3px;
		background: var(--rp-paper, var(--mg-surface));
	}
	.fc-toggle {
		display: flex;
		align-items: flex-start;
		gap: 14px;
		width: 100%;
		padding: 14px 16px;
		border: 0;
		background: none;
		color: var(--mg-text);
		text-align: left;
		cursor: pointer;
	}
	.fc-toggle:hover {
		background: var(--rp-stripe, var(--mg-surface-2));
	}
	.fc.open .fc-toggle {
		border-bottom: 1px solid var(--rp-line, var(--mg-border));
		background: var(--rp-pre, var(--mg-surface-2));
	}
	.fc-kind {
		flex: 0 0 auto;
		margin-top: 2px;
		padding: 3px 8px;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-radius: 2px;
		background: var(--rp-stripe, var(--mg-surface-2));
		color: var(--rp-text, var(--mg-text));
		font-family: var(--mg-mono);
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		letter-spacing: 0.06em;
	}
	.fc-main {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}
	.fc-sym {
		color: var(--rp-link, var(--mg-accent));
		font-size: calc(var(--mg-fs) * 1.15);
		font-weight: 600;
		line-height: 1.3;
		overflow-wrap: anywhere;
	}
	.fc-path {
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
		overflow-wrap: anywhere;
	}
	.fc-why {
		margin-top: 4px;
		color: var(--mg-text-2);
		font-size: var(--rp-small, var(--mg-fs));
		line-height: 1.5;
	}
	.fc-act {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
		margin-top: 2px;
		padding: 6px 12px;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-radius: 3px;
		background: var(--rp-stripe, var(--mg-surface-2));
		box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.08);
		color: var(--rp-text, var(--mg-text));
		font-size: var(--mg-fs-sm);
		font-weight: 600;
		white-space: nowrap;
	}
	.fc-act :global(.fc-chev) {
		transition: transform 150ms ease;
	}
	.fc.open .fc-act :global(.fc-chev) {
		transform: rotate(90deg);
	}
	.fc-body {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 16px 16px;
	}
	.fc-links {
		margin: 0;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
	}
	.fc-links :global(svg) {
		vertical-align: -1px;
	}
	@media (max-width: 640px) {
		.fc-toggle {
			flex-wrap: wrap;
		}
		.fc-act {
			margin-left: auto;
		}
	}
</style>
