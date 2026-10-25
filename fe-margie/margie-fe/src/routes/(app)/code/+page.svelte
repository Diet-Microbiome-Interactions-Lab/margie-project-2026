<script lang="ts">
	import '$lib/crisp/about.css';
	import hljs from 'highlight.js/lib/core';
	import python from 'highlight.js/lib/languages/python';
	import { Copy, Download, ExternalLink, FileCode } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, formatBytes } from '$lib/api';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * Code: the Python scripts behind MARGIE's own steps (consolidation to the fingerprint
	 * databases), read from the server's installed pipeline when opened (routers/code.py) and
	 * shown highlighted, with line numbers. Reached from the README's How does MARGIE work.
	 */
	hljs.registerLanguage('python', python);

	interface CodeFile {
		path: string;
		name: string;
		lines: number;
		bytes: number;
		summary: string;
	}
	interface Step {
		key: string;
		title: string;
		what: string;
		files: CodeFile[];
	}
	interface Source {
		path: string;
		name: string;
		text: string;
		lines: number;
		bytes: number;
		sha256: string;
	}

	const REPO = 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026';
	const BLOB = `${REPO}/blob/main/be-margie/bioinformatics_tools/workflow_tools/`;

	let steps = $state<Step[]>([]);
	let listError = $state('');
	let source = $state<Source | null>(null);
	let fileError = $state('');
	let loading = $state(false);

	const picked = $derived(page.url.searchParams.get('file') ?? steps[0]?.files[0]?.path ?? '');
	const pickedFile = $derived(steps.flatMap((s) => s.files).find((f) => f.path === picked));
	const pickedStep = $derived(steps.find((s) => s.files.some((f) => f.path === picked)));

	$effect(() => {
		api<{ steps: Step[] }>('/code').then(
			(r) => (steps = r.steps),
			(e) => (listError = e?.message ?? 'The list of scripts could not be read.')
		);
	});

	$effect(() => {
		const path = picked;
		if (!path || source?.path === path) return;
		loading = true;
		fileError = '';
		api<Source>(`/code/file?path=${encodeURIComponent(path)}`).then(
			(r) => {
				if (r.path === picked) source = r;
				loading = false;
			},
			(e) => {
				fileError = e?.message ?? `${path} could not be read.`;
				loading = false;
			}
		);
	});

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
		if (!source) return [];
		const html = hljs.highlight(source.text, { language: 'python', ignoreIllegals: true }).value;
		const lines = splitLines(html);
		// A file's final newline ends its last line rather than opening an empty one.
		return source.text.endsWith('\n') ? lines.slice(0, -1) : lines;
	});

	function pick(path: string) {
		goto(`?file=${encodeURIComponent(path)}`, { noScroll: true, keepFocus: true });
	}

	function copy() {
		if (!source) return;
		navigator.clipboard?.writeText(source.text).then(
			() => ui.notify(`${source?.name} is copied.`, 'ok'),
			() => {}
		);
	}

	function download() {
		if (!source) return;
		const url = URL.createObjectURL(new Blob([source.text], { type: 'text/x-python' }));
		const a = Object.assign(document.createElement('a'), { href: url, download: source.name });
		document.body.append(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 10_000);
	}
</script>

<svelte:head><title>{source ? `${source.name} | ` : ''}Code | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-code">
	<div class="cr-head">
		<h1 class="cr-title">Code</h1>
		<p class="cr-lede">
			The Python scripts behind MARGIE's own steps, read from the pipeline this server runs each time you open one. The
			<a class="mg-link" href="/methods">Methods</a> describe what each step does.
		</p>
	</div>

	{#if listError}
		<section class="ab-box">
			<p>{listError}</p>
			<p class="ab-lab">The same scripts are in the repository: <a class="mg-link" href={`${REPO}/tree/main/be-margie/bioinformatics_tools/workflow_tools`} target="_blank" rel="noreferrer">workflow_tools on GitHub</a>.</p>
		</section>
	{:else}
		<div class="cd">
			<nav class="ab-box cd-steps" aria-label="Steps and their scripts">
				{#each steps as s (s.key)}
					<div class="cd-step">
						<h2>{s.title}</h2>
						<p class="ab-lab cd-what">{s.what}</p>
						<ul>
							{#each s.files as f (f.path)}
								<li>
									<button
										type="button"
										class="cd-file"
										class:on={f.path === picked}
										aria-current={f.path === picked ? 'page' : undefined}
										title={f.summary || f.path}
										onclick={() => pick(f.path)}
									>
										<FileCode size={14} /><span class="mg-mono">{f.name}</span><span class="cd-n">{f.lines}</span>
									</button>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</nav>

			<section class="ab-box cd-view">
				{#if pickedFile}
					<div class="cd-top">
						<div class="cd-id">
							<span class="ab-lab cd-crumb">{pickedStep?.title} | workflow_tools/{pickedFile.path}</span>
							<b class="mg-mono cd-name">{pickedFile.name}</b>
							{#if pickedFile.summary}<span class="cd-sum">{pickedFile.summary}</span>{/if}
						</div>
						<div class="cd-acts">
							<button type="button" class="mg-btn small" onclick={copy} disabled={!source}><Copy size={14} /> Copy</button>
							<button type="button" class="mg-btn small" onclick={download} disabled={!source}><Download size={14} /> Download</button>
							<a class="mg-btn small" href={BLOB + pickedFile.path} target="_blank" rel="noreferrer"><ExternalLink size={14} /> On GitHub</a>
						</div>
					</div>
					{#if source && source.path === picked}
						<p class="ab-lab cd-meta">
							{source.lines} lines | {formatBytes(source.bytes)} | SHA-256 <span class="mg-mono" title={source.sha256}>{source.sha256.slice(0, 12)}</span>
						</p>
					{/if}
					{#if fileError}
						<p>{fileError}</p>
					{:else if source && source.path === picked}
						<pre class="cd-src" aria-label="{source.name}, {source.lines} lines"><code>{#each rows as r, i (i)}<span class="cd-row"><span class="cd-ln" aria-hidden="true">{i + 1}</span><span class="cd-t">{@html r || ' '}</span></span>{/each}</code></pre>
					{:else if loading}
						<p class="ab-lab">Reading {pickedFile.name}…</p>
					{/if}
				{:else if steps.length}
					<p class="ab-lab">That script is not on the list; pick one from the list.</p>
				{:else}
					<p class="ab-lab">Reading the list of scripts…</p>
				{/if}
			</section>
		</div>
	{/if}
</div>

<style>
	.cd {
		/* Syntax colours on the code box (light); the dark theme's are below. */
		--cd-kw: #0b57d0;
		--cd-str: #0a7d38;
		--cd-com: #6b7280;
		--cd-num: #b54708;
		--cd-fn: #7c3aed;
		--cd-bi: #0e7490;
		--cd-meta: #a1450e;
		--cd-ln: #9aa3af;
		display: grid;
		grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
		gap: var(--cr-gutter, 16px);
		align-items: start;
		max-width: 1400px;
	}
	:global(.crisp[data-theme='dark']) .cd {
		--cd-kw: #8ab4f8;
		--cd-str: #81c995;
		--cd-com: #9aa0a6;
		--cd-num: #fcad70;
		--cd-fn: #c58af9;
		--cd-bi: #78d9ec;
		--cd-meta: #f6aea9;
		--cd-ln: #6b7280;
	}
	.cd-steps {
		position: sticky;
		top: 12px;
		gap: 14px;
		max-height: calc(100vh - 140px);
		overflow: auto;
	}
	.cd-step h2 {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.cd-what {
		margin: 2px 0 6px;
		font-size: var(--mg-fs-xs);
		line-height: 1.45;
	}
	.cd-step ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.cd-file {
		display: flex;
		align-items: center;
		gap: 7px;
		width: 100%;
		padding: 4px 8px;
		border: 0;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text);
		font-size: var(--mg-fs-xs);
		text-align: left;
		cursor: pointer;
	}
	.cd-file:hover {
		background: var(--mg-surface-2);
	}
	.cd-file.on {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent);
		font-weight: 600;
	}
	.cd-file .mg-mono {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.cd-n {
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.cd-view {
		min-width: 0;
	}
	.cd-top {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 10px;
	}
	.cd-id {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.cd-crumb {
		font-size: var(--mg-fs-xs);
		overflow-wrap: anywhere;
	}
	.cd-name {
		font-size: var(--mg-fs);
	}
	.cd-sum {
		color: var(--mg-text-2);
	}
	.cd-acts {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.cd-meta {
		font-size: var(--mg-fs-xs);
	}
	.cd-src {
		margin: 0;
		padding: 10px 0;
		overflow: auto;
		max-height: calc(100vh - 260px);
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-family: var(--mg-mono);
		font-size: 12.5px;
		line-height: 1.55;
		tab-size: 4;
	}
	.cd-src code {
		display: block;
		min-width: max-content;
	}
	.cd-row {
		display: flex;
	}
	.cd-row:hover {
		background: var(--mg-surface-2);
	}
	.cd-ln {
		flex: 0 0 auto;
		width: 4.5ch;
		padding-right: 1.5ch;
		color: var(--cd-ln);
		text-align: right;
		user-select: none;
	}
	.cd-t {
		padding-right: 16px;
		white-space: pre;
	}
	.cd-src :global(.hljs-keyword),
	.cd-src :global(.hljs-literal) {
		color: var(--cd-kw);
	}
	.cd-src :global(.hljs-string),
	.cd-src :global(.hljs-doctag) {
		color: var(--cd-str);
	}
	.cd-src :global(.hljs-comment) {
		color: var(--cd-com);
		font-style: italic;
	}
	.cd-src :global(.hljs-number) {
		color: var(--cd-num);
	}
	.cd-src :global(.hljs-title),
	.cd-src :global(.hljs-title.function_),
	.cd-src :global(.hljs-title.class_) {
		color: var(--cd-fn);
		font-weight: 600;
	}
	.cd-src :global(.hljs-built_in),
	.cd-src :global(.hljs-type) {
		color: var(--cd-bi);
	}
	.cd-src :global(.hljs-meta) {
		color: var(--cd-meta);
	}
	.cd-src :global(.hljs-subst) {
		color: var(--mg-text);
	}
	@media (max-width: 900px) {
		.cd {
			grid-template-columns: minmax(0, 1fr);
		}
		.cd-steps {
			position: static;
			max-height: none;
		}
		.cd-src {
			max-height: 70vh;
		}
	}
</style>
