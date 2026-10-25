<script lang="ts">
	import { ChevronRight, Copy, Download, FlaskConical, Mail, UserRound } from 'lucide-svelte';
	import { BASE_BIBTEX, BASE_CITATIONS, CITATION, CITE_URL, COMPUTING, LAB, PEOPLE, THESIS_BIBTEX, THESIS_CITATION, THESIS_DOI, THESIS_RECORDS, THESIS_RECORDS_BIBTEX } from '$lib/crisp/about';
	import { CITED_SOFTWARE, RUN_TOOLS, citedPapers, downloadBibtex } from '$lib/crisp/bibtex';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';
	import { ui } from '$lib/workspace/ui.svelte';

	/** Contributors: who made MARGIE, the lab MARGIE comes from, and how to cite MARGIE. */
	function copy(text: string, what = 'The citation') {
		navigator.clipboard?.writeText(text).then(
			() => ui.notify(`${what} is copied.`, 'ok'),
			() => {}
		);
	}
</script>

<svelte:head><title>Contributors | MARGIE</title></svelte:head>

<ReadingPage title="Contributors" lede="The people and the lab behind MARGIE, and the citations for work that uses MARGIE." shade="page-contributors">
	<section class="rp-sec" id="people" data-toc="People and lab">
		<h2>People and lab</h2>
		<div class="rp-trio">
			{#each PEOPLE as p (p.name)}
				<div class="rp-tile"><UserRound size={22} /><b>{p.name}</b>{#if p.role}<span>{p.role}</span>{/if}</div>
			{/each}
		</div>
		<div class="ct-lab">
			<span class="rp-link-icon"><FlaskConical size={24} /></span>
			<div>
				<b>{LAB.name}</b>, Purdue University
				<p class="rp-note">PI: {LAB.pi}. Questions, accounts for reviewers and collaborators, and requests go to the lab.</p>
			</div>
			<a class="mg-btn small" href="mailto:{LAB.email}"><Mail size={14} /> {LAB.email}</a>
		</div>
	</section>

	<section class="rp-sec" id="cite" data-toc="Cite MARGIE">
		<h2>Cite MARGIE</h2>
		<div class="rp-row">
			<button type="button" class="mg-btn primary small" onclick={downloadBibtex}><Download size={14} /> Download the citations (BibTeX)</button>
			<span class="rp-note">MARGIE, the thesis, the base architecture, the research computing and the {citedPapers().length} papers of the tools and software MARGIE runs.</span>
		</div>
		<h3>This pipeline</h3>
		<p class="rp-cite">{CITATION}</p>
		<div class="rp-row">
			<button type="button" class="mg-btn small" onclick={() => copy(CITATION)}><Copy size={14} /> Copy the citation</button>
			<a href={CITE_URL} target="_blank" rel="noreferrer">The repository</a>
		</div>
		<h3>The thesis in which MARGIE was first built</h3>
		<p class="rp-cite">{THESIS_CITATION}</p>
		<div class="rp-row">
			<button type="button" class="mg-btn small" onclick={() => copy(THESIS_CITATION)}><Copy size={14} /> Copy the citation</button>
			<button type="button" class="mg-btn small" onclick={() => copy(THESIS_BIBTEX, 'The BibTeX')}><Copy size={14} /> Copy BibTeX</button>
			<a href={THESIS_DOI} target="_blank" rel="noreferrer">The thesis</a>
		</div>
		<p class="rp-note">Cite the version you ran: its number is on the repository's Releases.</p>
	</section>

	<section class="rp-sec" id="thesis-records" data-toc="Thesis code and data">
		<h2>Thesis code and data</h2>
		<p class="rp-note">The code and data as the thesis used and cites them.</p>
		<ol class="rp-refs">
			{#each THESIS_RECORDS as r (r.href)}
				<li>{r.text} <span class="rp-note">({r.what})</span></li>
			{/each}
		</ol>
		<div class="rp-row">
			<button type="button" class="mg-btn small" onclick={() => copy(THESIS_RECORDS_BIBTEX, 'The BibTeX')}><Copy size={14} /> Copy BibTeX for these</button>
		</div>
	</section>

	<section class="rp-sec" id="base" data-toc="Base architecture">
		<h2>Base architecture</h2>
		<p class="rp-note">The platform MARGIE was built on, by Dane Deemer.</p>
		{#each BASE_CITATIONS as b (b.href)}
			<div class="ct-base">
				<p class="rp-cite">{b.text}</p>
				<div class="rp-row">
					<span class="rp-note">{b.what}</span>
					<button type="button" class="mg-btn small" onclick={() => copy(b.text)}><Copy size={14} /> Copy</button>
					<a href={b.href} target="_blank" rel="noreferrer">The repository</a>
				</div>
			</div>
		{/each}
		<div class="rp-row">
			<button type="button" class="mg-btn small" onclick={() => copy(BASE_BIBTEX, 'The BibTeX')}><Copy size={14} /> Copy BibTeX for both</button>
		</div>
	</section>

	<section class="rp-sec" id="computing" data-toc="Research computing">
		<h2>Research computing</h2>
		<ol class="rp-refs">
			{#each COMPUTING.refs as r (r.id)}
				<li>{r.apa} <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a></li>
			{/each}
		</ol>
	</section>

	<section class="rp-sec" id="cite-with" data-toc="Cite with MARGIE">
		<h2>Cite with MARGIE</h2>
		<p>
			Results from MARGIE rest on the tools, databases and software she runs. Cite those whose output you used; the BibTeX file above
			holds each one, and <a href="/acknowledgements">Acknowledgements</a> gives their versions, licences and sources.
		</p>
		<details class="ct-fold">
			<summary><ChevronRight size={16} /> The {RUN_TOOLS.length + CITED_SOFTWARE.length} tools, databases and software</summary>
			<ul class="ct-tools rp-plain">
				{#each [...RUN_TOOLS, ...CITED_SOFTWARE] as t ('id' in t ? t.id : t.name)}
					<li>
						<b>{t.name}</b>
						<ol class="rp-refs">
							{#each t.cite as c (c.key)}
								<li>{c.apa}{#if c.doi} <a href="https://doi.org/{c.doi}" target="_blank" rel="noreferrer">doi:{c.doi}</a>{/if}</li>
							{/each}
						</ol>
					</li>
				{/each}
			</ul>
		</details>
	</section>
</ReadingPage>

<style>
	.ct-lab {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 12px 16px;
		padding: 16px 18px;
		border: 1px solid var(--rp-edge);
		border-radius: var(--mg-r);
	}
	.ct-lab > div {
		flex: 1;
		min-width: 220px;
	}
	.ct-base {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.ct-fold > summary {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--rp-ink);
		font-weight: 600;
		cursor: pointer;
		list-style: none;
	}
	.ct-fold > summary::-webkit-details-marker {
		display: none;
	}
	.ct-fold > summary :global(svg) {
		transition: transform 150ms ease;
	}
	.ct-fold[open] > summary :global(svg) {
		transform: rotate(90deg);
	}
	.ct-tools {
		display: flex;
		flex-direction: column;
		gap: 14px;
		margin-top: 14px;
	}
	.ct-tools > li + li {
		margin-top: 0;
	}
	.ct-tools .rp-refs {
		margin-top: 4px;
	}
</style>
