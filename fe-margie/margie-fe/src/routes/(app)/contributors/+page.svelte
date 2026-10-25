<script lang="ts">
	import '$lib/crisp/about.css';
	import { Copy } from 'lucide-svelte';
	import { Download } from 'lucide-svelte';
	import { BASE_BIBTEX, BASE_CITATIONS, CITATION, CITE_URL, COMPUTING, LAB, PEOPLE, THESIS_BIBTEX, THESIS_CITATION, THESIS_DOI, THESIS_RECORDS, THESIS_RECORDS_BIBTEX } from '$lib/crisp/about';
	import { CITED_SOFTWARE, RUN_TOOLS, citedPapers, downloadBibtex } from '$lib/crisp/bibtex';
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
			<div class="acts">
				<button type="button" class="mg-btn primary small" onclick={downloadBibtex}><Download size={14} /> Download the citations (BibTeX)</button>
				<span class="ab-lab">MARGIE, the thesis, the base architecture, the research computing and the {citedPapers().length} papers of the tools and software she runs.</span>
			</div>
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
			<p class="ab-lab">The code and data as the thesis used and cites them:</p>
			<ol class="cite-list">
				{#each THESIS_RECORDS as r (r.href)}
					<li>{r.text} <span class="ab-lab">({r.what})</span></li>
				{/each}
			</ol>
			<div class="acts">
				<button type="button" class="mg-btn small" onclick={() => copy(THESIS_RECORDS_BIBTEX, 'The BibTeX')}><Copy size={14} /> Copy BibTeX for these</button>
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
			<p class="ab-lab">Research computing, as RCAC asks it to be cited:</p>
			<ol class="cite-list">
				{#each COMPUTING.refs as r (r.id)}
					<li>{r.apa} <a class="mg-link" href={r.url} target="_blank" rel="noreferrer">{r.url}</a></li>
				{/each}
			</ol>
			<details class="cite-with">
				<summary>Cite with her: the tools, databases and software she runs ({RUN_TOOLS.length + CITED_SOFTWARE.length})</summary>
				<p class="ab-lab">
					Results from MARGIE rest on these; their authors ask to be cited, several as a condition of use (marked). Cite those whose output
					you used; the BibTeX file above holds each one.
				</p>
				<ul class="cite-tools">
					{#each [...RUN_TOOLS, ...CITED_SOFTWARE] as t ('id' in t ? t.id : t.name)}
						<li>
							<b>{t.name}</b>
							{#if t.citeRequired}<span class="cite-req">asks to be cited</span>{/if}
							{#if t.citeRule}
								<span class="ab-lab cite-rule">“{t.citeRule}”{#if t.citeRuleUrl} (<a class="mg-link" href={t.citeRuleUrl} target="_blank" rel="noreferrer">its page</a>){/if}</span>
							{/if}
							<ol class="cite-list">
								{#each t.cite as c (c.key)}
									<li>{c.apa}{#if c.doi} <a class="mg-link" href="https://doi.org/{c.doi}" target="_blank" rel="noreferrer">doi:{c.doi}</a>{/if}</li>
								{/each}
							</ol>
						</li>
					{/each}
				</ul>
			</details>
			<p class="ab-lab">
				Cite the version you ran: its number is on the repository's Releases. Versions, licences and sources of each tool are under
				<a class="mg-link" href="/acknowledgements">Acknowledgements</a>.
			</p>
		</section>
	</div>
</div>

<style>
	.cite-list {
		margin: 2px 0 0;
		padding-left: 1.4em;
		list-style: decimal;
		font-size: var(--mg-fs-sm);
	}
	.cite-list a {
		overflow-wrap: anywhere;
	}
	.cite-with > summary {
		cursor: pointer;
		color: var(--mg-accent);
		font-weight: 600;
	}
	.cite-tools {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 10px 0 0;
		padding: 0;
		list-style: none;
	}
	.cite-req {
		margin-left: 6px;
		padding: 1px 7px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent);
		font-size: var(--mg-fs-xs);
		font-weight: 600;
	}
	.cite-rule {
		display: block;
		font-size: var(--mg-fs-sm);
	}
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
