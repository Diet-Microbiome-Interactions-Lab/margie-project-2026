<script lang="ts">
	import '$lib/crisp/about.css';
	import { Copy } from 'lucide-svelte';
	import { CITATION, CITE_URL, LAB, PEOPLE } from '$lib/crisp/about';
	import { ui } from '$lib/workspace/ui.svelte';

	/** Contributors: who made MARGIE, the lab it comes from, and how to cite it. */
	function copy(text: string) {
		navigator.clipboard?.writeText(text).then(
			() => ui.notify('The citation is copied.', 'ok'),
			() => {}
		);
	}
</script>

<svelte:head><title>Contributors | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-contributors">
	<div class="cr-head">
		<h1 class="cr-title">Contributors</h1>
		<p class="cr-lede">A product of the {LAB.name}. PI: {LAB.pi} (<a class="mg-link" href="mailto:{LAB.email}">{LAB.email}</a>).</p>
	</div>

	<div class="ab">
		<div class="ab-pair">
			<section class="ab-box">
				<h2>Contributors</h2>
				<ul class="people">
					{#each PEOPLE as p (p.name)}
						<li><b>{p.name}</b>{#if p.role}<span class="ab-lab">{p.role}</span>{/if}</li>
					{/each}
				</ul>
			</section>

			<section class="ab-box">
				<h2>The lab</h2>
				<p><b>{LAB.name}</b>, Purdue University</p>
				<p>PI: {LAB.pi}, <a class="mg-link" href="mailto:{LAB.email}">{LAB.email}</a></p>
				<p class="ab-lab">Questions, accounts for reviewers and collaborators, and requests go to the same address.</p>
			</section>
		</div>

		<section class="ab-box">
			<h2>How to cite MARGIE</h2>
			<p class="ab-cite">{CITATION}</p>
			<div class="acts">
				<button type="button" class="mg-btn small" onclick={() => copy(CITATION)}><Copy size={14} /> Copy the citation</button>
				<a class="mg-link" href={CITE_URL} target="_blank" rel="noreferrer">The repository</a>
			</div>
			<p class="ab-lab">
				Cite the version you ran: its number is on the repository's Releases. Please also cite each tool and database MARGIE ran for you;
				they are listed, with their references, under <a class="mg-link" href="/acknowledgements">Acknowledgements</a>.
			</p>
		</section>
	</div>
</div>

<style>
	.people {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 0;
		list-style: none;
	}
	.people li {
		display: flex;
		flex-direction: column;
	}
	.acts {
		display: flex;
		align-items: center;
		gap: 14px;
	}
</style>
