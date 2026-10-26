<script lang="ts">
	import { tick } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';
	import CodeFile from '$lib/crisp/CodeFile.svelte';

	/**
	 * Code: the scripts behind MARGIE's steps, read from the server's installed pipeline
	 * (routers/code.py), step by step in run order. Each script opens in place, as the FAQ's code
	 * previews do, with its line numbers and Copy, Download and GitHub. ?file=<path> opens that
	 * script and brings it into view. Reached from Methods, the FAQ and the README.
	 */

	interface CodeFileInfo {
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
		files: CodeFileInfo[];
	}

	const REPO = 'https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026';

	let steps = $state<Step[]>([]);
	let listError = $state('');
	let open = $state<Record<string, boolean>>({});

	$effect(() => {
		api<{ steps: Step[] }>('/code').then(
			(r) => {
				open = Object.fromEntries(r.steps.flatMap((s) => s.files.map((f) => [f.path, false])));
				steps = r.steps;
			},
			(e) => (listError = e?.message ?? 'The list of scripts could not be read.')
		);
	});

	// A link to one script (Methods, the FAQ) opens it and brings it into view.
	$effect(() => {
		const path = page.url.searchParams.get('file');
		if (!path || !steps.some((s) => s.files.some((f) => f.path === path))) return;
		open[path] = true;
		tick().then(() => document.getElementById(`file-${path.replace(/[^\w-]/g, '-')}`)?.scrollIntoView({ block: 'start' }));
	});
</script>

<svelte:head><title>Code | MARGIE</title></svelte:head>

<ReadingPage
	title="Code"
	lede="The scripts behind MARGIE's steps, in run order, read from the pipeline this server runs."
	shade="page-code"
	crumbs={[{ href: '/methods', label: 'Methods' }]}
>
	{#if listError}
		<section class="rp-sec">
			<p>{listError}</p>
			<p class="rp-note">The same scripts are in the repository: <a href={`${REPO}/tree/main/be-margie/bioinformatics_tools/workflow_tools`} target="_blank" rel="noreferrer">workflow_tools on GitHub</a>.</p>
		</section>
	{:else if !steps.length}
		<p class="rp-note">Reading the list of scripts…</p>
	{:else}
		{#each steps as s (s.key)}
			<section class="rp-sec" id={s.key} data-toc={s.title}>
				<h2>{s.title}</h2>
				<p>{s.what}</p>
				<div class="cd-files">
					{#each s.files as f (f.path)}
						<CodeFile file={f} bind:open={open[f.path]} />
					{/each}
				</div>
			</section>
		{/each}
	{/if}
</ReadingPage>

<style>
	.cd-files {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-top: 12px;
	}
</style>
