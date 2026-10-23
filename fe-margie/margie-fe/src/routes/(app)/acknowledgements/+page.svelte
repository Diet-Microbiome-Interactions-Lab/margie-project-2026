<script lang="ts">
	import '$lib/crisp/about.css';
	import { onMount } from 'svelte';
	import { EXTRA_REFERENCES, LAB } from '$lib/crisp/about';
	import { fetchTerms, NOT_YET, type CatalogTool } from '$lib/license';

	/**
	 * Acknowledgements: the tools and databases MARGIE is built on, with their references,
	 * from the licence catalog (the steps running now) and the few it does not carry.
	 */
	let tools = $state<CatalogTool[]>([]);
	let error = $state('');
	onMount(async () => {
		try {
			tools = (await fetchTerms()).tools;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	});

	/** One reference per tool, in the order a run uses them; a catalog note ("Cite ...") gives way to the paper. */
	const refs = $derived(
		[
			...tools
				.filter((t) => !NOT_YET.has(t.id) && t.citation && !/^cite /i.test(t.citation))
				.map((t) => ({ phase: t.phase, what: t.name, text: t.citation as string })),
			...EXTRA_REFERENCES
		].sort((a, b) => a.phase - b.phase || a.what.localeCompare(b.what))
	);
</script>

<svelte:head><title>Acknowledgements | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-acknowledgements">
	<div class="cr-head">
		<h1 class="cr-title">Acknowledgements</h1>
		<p class="cr-lede">A product of the {LAB.name}. PI: {LAB.pi} (<a class="mg-link" href="mailto:{LAB.email}">{LAB.email}</a>).</p>
	</div>

	<div class="ab">
		<section class="ab-box">
			<h2>With thanks</h2>
			<p>
				MARGIE was built on databases and tools that others had already built. We humbly acknowledge everyone whose tools and databases
				we have used in MARGIE: without their work, and their choice to share it, MARGIE would not exist.
			</p>
			<p class="ab-lab">
				If you publish results from MARGIE, please cite the tools and databases it ran for you, below, as well as MARGIE itself
				(<a class="mg-link" href="/contributors">how to cite</a>).
			</p>
		</section>

		<section class="ab-box">
			<h2>References</h2>
			{#if error}
				<p class="ab-lab">The references could not be read: {error}</p>
			{:else if !tools.length}
				<p class="ab-lab">Reading…</p>
			{:else}
				<ol class="refs">
					{#each refs as r (r.what)}
						<li><b>{r.what}</b>. {r.text}</li>
					{/each}
				</ol>
			{/if}
		</section>
	</div>
</div>

<style>
	.refs li {
		padding-left: 4px;
	}
</style>
