<script lang="ts">
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	/** Markdown text rendered as GitHub shows a README: headings, lists, tables, code and quotes. */
	let { source }: { source: string } = $props();
	const html = $derived(DOMPurify.sanitize(marked.parse(source, { async: false, gfm: true, breaks: false }) as string));
</script>

<article class="md-body">{@html html}</article>

<style>
	.md-body {
		max-width: 920px;
		color: var(--mg-text);
		font-size: 0.95rem;
		line-height: 1.6;
		overflow-wrap: break-word;
	}
	.md-body :global(> *:first-child) {
		margin-top: 0;
	}
	.md-body :global(h1),
	.md-body :global(h2) {
		padding-bottom: 0.3em;
		border-bottom: 1px solid var(--mg-border);
	}
	.md-body :global(h1) {
		margin: 1.2em 0 0.6em;
		font-size: 1.8em;
		font-weight: 650;
	}
	.md-body :global(h2) {
		margin: 1.4em 0 0.6em;
		font-size: 1.4em;
		font-weight: 650;
	}
	.md-body :global(h3) {
		margin: 1.2em 0 0.5em;
		font-size: 1.15em;
		font-weight: 650;
	}
	.md-body :global(h4),
	.md-body :global(h5),
	.md-body :global(h6) {
		margin: 1em 0 0.4em;
		font-size: 1em;
		font-weight: 650;
	}
	.md-body :global(p),
	.md-body :global(ul),
	.md-body :global(ol),
	.md-body :global(blockquote),
	.md-body :global(pre),
	.md-body :global(table) {
		margin: 0 0 1em;
	}
	.md-body :global(ul),
	.md-body :global(ol) {
		padding-left: 2em;
	}
	.md-body :global(ul) {
		list-style: disc;
	}
	.md-body :global(ol) {
		list-style: decimal;
	}
	.md-body :global(li + li) {
		margin-top: 0.25em;
	}
	.md-body :global(a) {
		color: var(--mg-accent-ink, var(--mg-accent));
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.md-body :global(code) {
		padding: 0.15em 0.4em;
		border-radius: 5px;
		background: var(--mg-surface-2);
		font-family: var(--mg-mono, ui-monospace, monospace);
		font-size: 0.86em;
	}
	.md-body :global(pre) {
		padding: 14px 16px;
		overflow: auto;
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
		line-height: 1.45;
	}
	.md-body :global(pre code) {
		padding: 0;
		background: none;
		font-size: 0.85em;
	}
	.md-body :global(blockquote) {
		padding: 0 1em;
		border-left: 4px solid var(--mg-border-strong);
		color: var(--mg-text-2);
	}
	.md-body :global(table) {
		display: block;
		width: max-content;
		max-width: 100%;
		overflow: auto;
		border-collapse: collapse;
	}
	.md-body :global(th),
	.md-body :global(td) {
		padding: 6px 13px;
		border: 1px solid var(--mg-border);
	}
	.md-body :global(th) {
		font-weight: 650;
	}
	.md-body :global(tr:nth-child(2n)) {
		background: var(--mg-surface-2);
	}
	.md-body :global(hr) {
		height: 2px;
		margin: 1.5em 0;
		border: 0;
		background: var(--mg-border);
	}
	.md-body :global(img) {
		max-width: 100%;
	}
</style>
