<script lang="ts">
	import '$lib/crisp/about.css';
	import { Copy } from 'lucide-svelte';
	import { BASE_BIBTEX, BASE_CITATIONS, CITATION, CITE_URL, LAB, PEOPLE, THESIS_BIBTEX, THESIS_CITATION, THESIS_DOI } from '$lib/crisp/about';
	import { ui } from '$lib/workspace/ui.svelte';

	/** Contributors: who made MARGIE, the lab she comes from, and how to cite her. */
	function copy(text: string, what = 'The citation') {
		navigator.clipboard?.writeText(text).then(
			() => ui.notify(`${what} is copied.`, 'ok'),
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
			<p class="ab-lab">This pipeline:</p>
			<p class="ab-cite">{CITATION}</p>
			<div class="acts">
				<button type="button" class="mg-btn small" onclick={() => copy(CITATION)}><Copy size={14} /> Copy the citation</button>
				<a class="mg-link" href={CITE_URL} target="_blank" rel="noreferrer">The repository</a>
			</div>
			<p class="ab-lab">Thesis, in which MARGIE was first built:</p>
			<p class="ab-cite">{THESIS_CITATION}</p>
			<div class="acts">
				<button type="button" class="mg-btn small" onclick={() => copy(THESIS_CITATION)}><Copy size={14} /> Copy the citation</button>
				<button type="button" class="mg-btn small" onclick={() => copy(THESIS_BIBTEX, 'The BibTeX')}><Copy size={14} /> Copy BibTeX</button>
				<a class="mg-link" href={THESIS_DOI} target="_blank" rel="noreferrer">The thesis</a>
			</div>
			<p class="ab-lab">Base architecture on which MARGIE was built, by Dane Deemer:</p>
			{#each BASE_CITATIONS as b (b.href)}
				<p class="ab-cite">{b.text}</p>
				<p class="ab-lab">{b.what}</p>
				<div class="acts">
					<button type="button" class="mg-btn small" onclick={() => copy(b.text)}><Copy size={14} /> Copy the citation</button>
					<a class="mg-link" href={b.href} target="_blank" rel="noreferrer">The repository</a>
				</div>
			{/each}
			<div class="acts">
				<button type="button" class="mg-btn small" onclick={() => copy(BASE_BIBTEX, 'The BibTeX')}><Copy size={14} /> Copy BibTeX for both</button>
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
