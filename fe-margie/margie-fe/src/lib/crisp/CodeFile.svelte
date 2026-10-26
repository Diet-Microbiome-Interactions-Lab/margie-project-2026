<script lang="ts">
	import { ChevronRight, Copy, Download, ExternalLink } from 'lucide-svelte';
	import { api, formatBytes } from '$lib/api';
	import { ui } from '$lib/workspace/ui.svelte';
	import CodeBlock from './CodeBlock.svelte';

	/**
	 * One script on the Code page, as the FAQ's code previews are: a toggle with the file's kind, name,
	 * path and what it does, which reads the whole file from the server's pipeline the first time it
	 * opens (/v1/code/file) and shows it with line numbers, a Copy and a Download button and a link
	 * to GitHub.
	 */
	interface CodeFile {
		path: string;
		name: string;
		lines: number;
		bytes: number;
		summary: string;
	}
	interface Source {
		path: string;
		name: string;
		text: string;
		lines: number;
		bytes: number;
		sha256: string;
	}

	let { file, open = $bindable() }: { file: CodeFile; open?: boolean } = $props();

	const BLOB = 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026/blob/main/be-margie/bioinformatics_tools/workflow_tools/';
	const kind = $derived(file.path.endsWith('.smk') ? 'SMK' : file.path.endsWith('.py') ? 'PY' : (file.path.split('.').pop() ?? '').toUpperCase());

	let source = $state<Source | null>(null);
	let error = $state('');

	$effect(() => {
		if (!open || source || error) return;
		api<Source>(`/code/file?path=${encodeURIComponent(file.path)}`).then(
			(r) => (source = r),
			(e) => (error = e?.message ?? `${file.name} could not be read here.`)
		);
	});

	function copy() {
		if (!source) return;
		navigator.clipboard?.writeText(source.text).then(
			() => ui.notify(`${file.name} is copied.`, 'ok'),
			() => {}
		);
	}

	function download() {
		if (!source) return;
		const url = URL.createObjectURL(new Blob([source.text], { type: 'text/plain' }));
		const a = Object.assign(document.createElement('a'), { href: url, download: file.name });
		document.body.append(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 10_000);
	}
</script>

<div class="cf" class:open id="file-{file.path.replace(/[^\w-]/g, '-')}">
	<button type="button" class="cf-toggle" aria-expanded={open} onclick={() => (open = !open)}>
		<span class="cf-kind">{kind}</span>
		<span class="cf-main">
			<span class="mg-mono cf-name">{file.name}</span>
			<span class="mg-mono cf-path">{file.path === file.name ? '' : `${file.path} | `}{file.lines.toLocaleString('en-US')} lines | {formatBytes(file.bytes)}</span>
			{#if file.summary}<span class="cf-what">{file.summary}</span>{/if}
		</span>
		<span class="cf-act">{open ? 'Hide code' : 'Show code'} <ChevronRight size={16} class="cf-chev" /></span>
	</button>
	{#if open}
		<div class="cf-body">
			{#if source}
				<div class="cf-tools">
					<span class="cf-sha">SHA-256 <span class="mg-mono">{source.sha256.slice(0, 16)}</span></span>
					<span class="mg-grow"></span>
					<button type="button" class="mg-btn small" onclick={copy}><Copy size={14} /> Copy</button>
					<button type="button" class="mg-btn small" onclick={download}><Download size={14} /> Download</button>
					<a class="mg-btn small" href={BLOB + file.path} target="_blank" rel="noreferrer"><ExternalLink size={14} /> On GitHub</a>
				</div>
				<div data-copy>
					<CodeBlock text={source.text} label="{file.name}, {source.lines} lines" maxHeight="70vh" />
				</div>
			{:else if error}
				<p class="cf-note">{error} <a class="mg-link" href={BLOB + file.path} target="_blank" rel="noreferrer">{file.path} on GitHub</a>.</p>
			{:else}
				<p class="cf-note">Reading {file.name}…</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	/* A script: a card with its name, path and what it does; it opens to the whole file. */
	.cf {
		overflow: hidden;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-radius: 3px;
		background: var(--rp-paper, var(--mg-surface));
		scroll-margin-top: 16px;
	}
	.cf-toggle {
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
	.cf-toggle:hover {
		background: var(--rp-stripe, var(--mg-surface-2));
	}
	.cf.open .cf-toggle {
		border-bottom: 1px solid var(--rp-line, var(--mg-border));
		background: var(--rp-pre, var(--mg-surface-2));
	}
	.cf-kind {
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
	.cf-main {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}
	.cf-name {
		color: var(--rp-link, var(--mg-accent));
		font-size: calc(var(--mg-fs) * 1.15);
		font-weight: 600;
		line-height: 1.3;
		overflow-wrap: anywhere;
	}
	.cf-path {
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
		overflow-wrap: anywhere;
	}
	.cf-what {
		margin-top: 4px;
		color: var(--mg-text-2);
		font-size: var(--rp-small, var(--mg-fs));
		line-height: 1.5;
	}
	.cf-act {
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
	.cf-act :global(.cf-chev) {
		transition: transform 150ms ease;
	}
	.cf.open .cf-act :global(.cf-chev) {
		transform: rotate(90deg);
	}
	.cf-body {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 12px 16px 16px;
	}
	.cf-tools {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}
	.cf-sha,
	.cf-note {
		margin: 0;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
	}
	@media (max-width: 640px) {
		.cf-toggle {
			flex-wrap: wrap;
		}
		.cf-act {
			margin-left: auto;
		}
	}
</style>
