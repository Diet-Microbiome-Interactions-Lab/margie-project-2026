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
	/* A literal block: pale grey, ruled, with a gutter of line numbers and classic syntax colours. */
	.cb {
		--cb-bg: #f8f8f8;
		--cb-gutter: #f0f2f3;
		--cb-line: #e1e4e5;
		--cb-text: #333333;
		--cb-kw: #007020;
		--cb-str: #4070a0;
		--cb-com: #408090;
		--cb-num: #208050;
		--cb-fn: #06287e;
		--cb-bi: #007020;
		--cb-meta: #555555;
		--cb-ln: #9a9a9a;
		margin: 0;
		padding: 0;
		overflow: auto;
		border: 1px solid var(--cb-line);
		background: var(--cb-bg);
		color: var(--cb-text);
		font-family: var(--mg-mono);
		font-size: max(13px, calc(var(--mg-fs) * 0.96));
		line-height: 1.6;
		tab-size: 4;
	}
	:global(.crisp[data-theme='dark']) .cb {
		--cb-bg: color-mix(in srgb, var(--mg-text) 5%, var(--mg-surface));
		--cb-gutter: color-mix(in srgb, var(--mg-text) 9%, var(--mg-surface));
		--cb-line: color-mix(in srgb, var(--mg-text) 16%, transparent);
		--cb-text: var(--mg-text);
		--cb-kw: #8ab4f8;
		--cb-str: #81c995;
		--cb-com: #9aa0a6;
		--cb-num: #fcad70;
		--cb-fn: #c58af9;
		--cb-bi: #78d9ec;
		--cb-meta: #f6aea9;
		--cb-ln: #7b8494;
	}
	.cb code {
		display: block;
		min-width: max-content;
		padding: 0;
	}
	.cb-row {
		display: flex;
	}
	.cb-row:first-child > * {
		padding-top: 8px;
	}
	.cb-row:last-child > * {
		padding-bottom: 8px;
	}
	.cb-row:hover .cb-t {
		background: color-mix(in srgb, var(--cb-fn) 6%, transparent);
	}
	.cb-ln {
		flex: 0 0 auto;
		width: 4ch;
		margin-right: 1.5ch;
		padding: 0 1.2ch 0 1ch;
		border-right: 1px solid var(--cb-line);
		background: var(--cb-gutter);
		color: var(--cb-ln);
		text-align: right;
		-webkit-user-select: none;
		user-select: none;
	}
	.cb-t {
		flex: 1;
		padding-right: 18px;
		white-space: pre;
	}
	.cb :global(.hljs-keyword),
	.cb :global(.hljs-literal) {
		color: var(--cb-kw);
		font-weight: 700;
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
		font-weight: 700;
	}
	.cb :global(.hljs-built_in),
	.cb :global(.hljs-type) {
		color: var(--cb-bi);
	}
	.cb :global(.hljs-meta) {
		color: var(--cb-meta);
		font-weight: 700;
	}
	.cb :global(.hljs-subst) {
		color: var(--cb-text);
	}
</style>
