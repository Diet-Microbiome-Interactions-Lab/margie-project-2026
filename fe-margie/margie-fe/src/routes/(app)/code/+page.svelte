<script lang="ts">
	import '$lib/crisp/about.css';
	import { Copy, Download, ExternalLink } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, formatBytes } from '$lib/api';
	import { ui } from '$lib/workspace/ui.svelte';
	import CodeBlock from '$lib/crisp/CodeBlock.svelte';

	/**
	 * Code: the Python scripts behind MARGIE's own steps (consolidation to the fingerprint
	 * databases), read from the server's installed pipeline when opened (routers/code.py) and
	 * shown highlighted, with line numbers (CodeBlock), in the reading pages' document look. Reached from
	 * Methods and the README.
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

	let view = $state<HTMLElement>();
	function pick(path: string) {
		goto(`?file=${encodeURIComponent(path)}`, { noScroll: true, keepFocus: true });
		// On a narrow screen the list sits above the code, so the code comes into view.
		if (matchMedia('(max-width: 900px)').matches) view?.scrollIntoView({ block: 'start', behavior: ui.motion === 'off' ? 'auto' : 'smooth' });
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

<div class="cr-page rp" data-shade="page-code">
	<div class="rp-paper">
		<nav class="rp-crumbs" aria-label="Breadcrumb">
			<ol>
				<li><a href="/">Home</a></li>
				<li><a href="/methods">Methods</a></li>
				<li aria-current="page">Code</li>
			</ol>
		</nav>
		<h1 class="rp-title">Code</h1>
		<p class="rp-lede">The Python scripts behind MARGIE's own steps, read from the pipeline this server runs each time you open one.</p>

		{#if listError}
			<div class="cd-msg">
				<p>{listError}</p>
				<p class="rp-note">The same scripts are in the repository: <a href={`${REPO}/tree/main/be-margie/bioinformatics_tools/workflow_tools`} target="_blank" rel="noreferrer">workflow_tools on GitHub</a>.</p>
			</div>
		{:else}
			<div class="cd">
				<nav class="cd-nav" aria-label="Steps and their scripts">
					{#each steps as s (s.key)}
						<div class="cd-step">
							<h2>{s.title}</h2>
							<p class="cd-what">{s.what}</p>
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
											<span class="mg-mono">{f.name}</span><span class="cd-n">{f.lines}</span>
										</button>
									</li>
								{/each}
							</ul>
						</div>
					{/each}
				</nav>

				<article class="cd-view" bind:this={view}>
					{#if pickedFile}
						<header class="cd-top">
							<p class="cd-path">workflow_tools » {pickedFile.path.split('/').join(' » ')}</p>
							<div class="cd-head">
								<h2 class="mg-mono">{pickedFile.name}</h2>
								<div class="cd-acts">
									<button type="button" class="mg-btn small" onclick={copy} disabled={!source}><Copy size={14} /> Copy</button>
									<button type="button" class="mg-btn small" onclick={download} disabled={!source}><Download size={14} /> Download</button>
									<a class="mg-btn small" href={BLOB + pickedFile.path} target="_blank" rel="noreferrer"><ExternalLink size={14} /> On GitHub</a>
								</div>
							</div>
							{#if pickedFile.summary}<p class="cd-sum">{pickedFile.summary}</p>{/if}
							{#if source && source.path === picked}
								<p class="cd-meta">
									{pickedStep?.title} | {source.lines} lines | {formatBytes(source.bytes)} | SHA-256 <span class="mg-mono" title={source.sha256}>{source.sha256.slice(0, 12)}</span>
								</p>
							{/if}
						</header>
						{#if fileError}
							<p class="cd-msg">{fileError}</p>
						{:else if source && source.path === picked}
							<CodeBlock text={source.text} label="{source.name}, {source.lines} lines" />
						{:else if loading}
							<p class="rp-note">Reading {pickedFile.name}…</p>
						{/if}
					{:else if steps.length}
						<p class="rp-note">Pick a script from the list.</p>
					{:else}
						<p class="rp-note">Reading the list of scripts…</p>
					{/if}
				</article>
			</div>
		{/if}
	</div>
</div>

<style>
	.cd {
		display: grid;
		grid-template-columns: minmax(220px, 270px) minmax(0, 1fr);
		gap: 36px;
		align-items: start;
		margin-top: 24px;
	}
	/* The scripts, by step, as a contents list. */
	.cd-nav {
		position: sticky;
		top: 14px;
		display: flex;
		flex-direction: column;
		gap: 18px;
		max-height: calc(100vh - 120px);
		overflow: auto;
		padding-right: 6px;
	}
	.cd-step h2 {
		margin: 0;
		color: var(--rp-head);
		font-family: var(--rp-head-font);
		font-size: calc(var(--mg-fs) * 1.1);
		font-weight: 700;
	}
	.cd-what {
		margin: 3px 0 8px;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
		line-height: 1.45;
	}
	.cd-step ul {
		margin: 0;
		padding: 0;
		border-left: 1px solid var(--rp-line);
		list-style: none;
	}
	.cd-file {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		margin-left: -1px;
		padding: 6px 10px 6px 12px;
		border: 0;
		border-left: 2px solid transparent;
		background: none;
		color: var(--rp-link);
		font-size: calc(var(--mg-fs) * 0.98);
		text-align: left;
		cursor: pointer;
	}
	.cd-file:hover {
		background: var(--rp-stripe);
	}
	.cd-file.on {
		border-left-color: var(--rp-link);
		background: var(--rp-stripe);
		color: var(--rp-head);
		font-weight: 700;
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
		font-size: var(--mg-fs-xs);
		font-variant-numeric: tabular-nums;
	}
	/* The open script: its path, name, what it does, and the code. */
	.cd-view {
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-width: 0;
	}
	.cd-top {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding-bottom: 14px;
		border-bottom: 1px solid var(--rp-line);
	}
	.cd-path {
		margin: 0;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
		overflow-wrap: anywhere;
	}
	.cd-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 10px 16px;
	}
	.cd-head h2 {
		margin: 0;
		color: var(--rp-head);
		font-size: calc(var(--mg-fs) * 1.6);
		font-weight: 600;
		overflow-wrap: anywhere;
	}
	.cd-acts {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.cd-sum {
		margin: 0;
		font-size: var(--rp-body);
		line-height: 1.55;
	}
	.cd-meta {
		margin: 0;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
	}
	.cd-msg {
		margin-top: 20px;
	}
	@media (max-width: 900px) {
		.cd {
			grid-template-columns: minmax(0, 1fr);
			gap: 22px;
		}
		.cd-nav {
			position: static;
			max-height: none;
		}
	}
</style>
