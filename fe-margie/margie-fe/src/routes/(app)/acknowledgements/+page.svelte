<script lang="ts">
	import '$lib/crisp/about.css';
	import { onMount } from 'svelte';
	import { EXTRA_REFERENCES, LAB, SOFTWARE } from '$lib/crisp/about';
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
			<p>
				Sajal Bhattarai gratefully acknowledges Dane Deemer (<a class="mg-link" href="https://github.com/wintermutant" target="_blank" rel="noreferrer"
					>wintermutant</a
				>) for his mentoring, and for the design and development of the engine and GUI orchestration platform,
				<a class="mg-link" href="https://github.com/wintermutant/bioinformatics-tools" target="_blank" rel="noreferrer">BSP</a>, on which MARGIE was built.
				Special thanks go to Dr. {LAB.pi} for his vision, supervision and support throughout its development, and to the members of the
				{LAB.name} for their feedback and ideas. We thank Purdue RCAC for the research computing environment that supports this work.
			</p>
			<p class="ab-lab">
				If you publish results from MARGIE, please cite the tools and databases it ran for you, below, as well as MARGIE itself
				(<a class="mg-link" href="/contributors">how to cite</a>).
			</p>
		</section>

		<section class="ab-box">
			<h2>Software it is built with</h2>
			<p class="ab-lab">MARGIE runs on open-source software that others write and share. Thank you to every one of these projects.</p>
			<div class="sw">
				{#each SOFTWARE as g (g.group)}
					<div class="sw-g">
						<h3>{g.group}</h3>
						<ul>
							{#each g.items as it (it.name)}
								<li><a class="mg-link" href={it.href} target="_blank" rel="noreferrer">{it.name}</a> <span>{it.what}</span></li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>
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
	.sw {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
		gap: 16px 28px;
		margin-top: 12px;
	}
	.sw-g h3 {
		margin: 0 0 6px;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.sw-g ul {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.sw-g li {
		font-size: var(--mg-fs-sm);
	}
	.sw-g li span {
		color: var(--mg-text-3);
	}
</style>
