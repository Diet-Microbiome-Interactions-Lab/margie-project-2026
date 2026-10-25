<script lang="ts">
	import hljs from 'highlight.js/lib/core';
	import python from 'highlight.js/lib/languages/python';

	/**
	 * Python (or Snakemake) source, highlighted, one row per line with its number. `start` numbers a
	 * snippet from its line in the file. Used by the Code page and the FAQ's code previews.
	 */
	let { text, start = 1, label, maxHeight = 'calc(100vh - 260px)' }: { text: string; start?: number; label: string; maxHeight?: string } = $props();

	if (!hljs.getLanguage('python')) hljs.registerLanguage('python', python);

	/** Splits highlight.js HTML into lines: a span open at a line's end is closed there and reopened on the next. */
	function splitLines(html: string): string[] {
		const out: string[] = [];
		const open: string[] = [];
		let line = '';
		for (const part of html.split(/(<span[^>]*>|<\/span>|\n)/)) {
			if (part === '\n') {
				out.push(line + '</span>'.repeat(open.length));
				line = open.join('');
			} else if (part.startsWith('<span')) {
				open.push(part);
				line += part;
			} else if (part === '</span>') {
				open.pop();
				line += part;
			} else line += part;
		}
		out.push(line + '</span>'.repeat(open.length));
		return out;
	}

	const rows = $derived.by(() => {
		const lines = splitLines(hljs.highlight(text, { language: 'python', ignoreIllegals: true }).value);
		// A final newline ends the last line rather than opening an empty one.
		return text.endsWith('\n') ? lines.slice(0, -1) : lines;
	});
</script>

<pre class="cb" style="max-height: {maxHeight}" aria-label={label}><code>{#each rows as r, i (i)}<span class="cb-row"><span class="cb-ln" aria-hidden="true">{start + i}</span><span class="cb-t">{@html r || ' '}</span></span>{/each}</code></pre>

<style>
	.cb {
		/* Syntax colours (light); the dark theme's are below. */
		--cb-kw: #0b57d0;
		--cb-str: #0a7d38;
		--cb-com: #6b7280;
		--cb-num: #b54708;
		--cb-fn: #7c3aed;
		--cb-bi: #0e7490;
		--cb-meta: #a1450e;
		--cb-ln: #9aa3af;
		margin: 0;
		padding: 10px 0;
		overflow: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-family: var(--mg-mono);
		font-size: max(13px, var(--mg-fs-sm));
		line-height: 1.55;
		tab-size: 4;
	}
	:global(.crisp[data-theme='dark']) .cb {
		--cb-kw: #8ab4f8;
		--cb-str: #81c995;
		--cb-com: #9aa0a6;
		--cb-num: #fcad70;
		--cb-fn: #c58af9;
		--cb-bi: #78d9ec;
		--cb-meta: #f6aea9;
		--cb-ln: #6b7280;
	}
	.cb code {
		display: block;
		min-width: max-content;
	}
	.cb-row {
		display: flex;
	}
	.cb-row:hover {
		background: var(--mg-surface-2);
	}
	.cb-ln {
		flex: 0 0 auto;
		width: 5ch;
		padding-right: 1.5ch;
		color: var(--cb-ln);
		text-align: right;
		user-select: none;
	}
	.cb-t {
		padding-right: 16px;
		white-space: pre;
	}
	.cb :global(.hljs-keyword),
	.cb :global(.hljs-literal) {
		color: var(--cb-kw);
	}
	.cb :global(.hljs-string),
	.cb :global(.hljs-doctag) {
		color: var(--cb-str);
	}
	.cb :global(.hljs-comment) {
		color: var(--cb-com);
		font-style: italic;
	}
	.cb :global(.hljs-number) {
		color: var(--cb-num);
	}
	.cb :global(.hljs-title),
	.cb :global(.hljs-title.function_),
	.cb :global(.hljs-title.class_) {
		color: var(--cb-fn);
		font-weight: 600;
	}
	.cb :global(.hljs-built_in),
	.cb :global(.hljs-type) {
		color: var(--cb-bi);
	}
	.cb :global(.hljs-meta) {
		color: var(--cb-meta);
	}
	.cb :global(.hljs-subst) {
		color: var(--mg-text);
	}
</style>
