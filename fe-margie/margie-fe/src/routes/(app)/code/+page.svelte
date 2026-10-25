<script lang="ts">
	import '$lib/crisp/about.css';
	import { Copy, Download, ExternalLink, FileCode } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, formatBytes } from '$lib/api';
	import { ui } from '$lib/workspace/ui.svelte';
	import CodeBlock from '$lib/crisp/CodeBlock.svelte';

	/**
	 * Code: the Python scripts behind MARGIE's own steps (consolidation to the fingerprint
	 * databases), read from the server's installed pipeline when opened (routers/code.py) and
	 * shown highlighted, with line numbers (CodeBlock). Reached from the README's How does MARGIE work.
	 */

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
						<CodeBlock text={source.text} label="{source.name}, {source.lines} lines" />
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
		display: grid;
		grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
		gap: var(--cr-gutter, 16px);
		align-items: start;
		max-width: 1400px;
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
	@media (max-width: 900px) {
		.cd {
			grid-template-columns: minmax(0, 1fr);
		}
		.cd-steps {
			position: static;
			max-height: none;
		}
	}
</style>
