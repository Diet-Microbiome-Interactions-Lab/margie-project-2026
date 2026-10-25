<script lang="ts">
	import { Download, Landmark } from 'lucide-svelte';
	import { AI_USAGE, COMPUTING, FUNDING, LAB, SOFTWARE } from '$lib/crisp/about';
	import { SOFTWARE_CREDITS } from '$lib/crisp/credits';
	import { CITED_SOFTWARE, RUN_TOOLS, downloadBibtex } from '$lib/crisp/bibtex';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';

	/**
	 * Acknowledgements: thanks, funding and AI usage; the tools and databases MARGIE runs (credits.ts,
	 * checked against their own pages), each with its version, licence, source code and data sources;
	 * the software MARGIE is built with; the research computing MARGIE runs on; and the papers to cite.
	 */

	/** A download entry: its URL as a link, and any note after it ("register; tarball ..."). */
	function download(entry: string): { url: string | null; label: string; note: string } {
		const m = entry.match(/https?:\/\/\S+/);
		if (!m) return { url: null, label: entry, note: '' };
		const url = m[0].replace(/[),.;]+$/, '');
		const u = new URL(url);
		const tail = u.pathname.split('/').filter(Boolean).at(-1);
		return { url, label: u.host + (tail ? ` | ${tail}` : ''), note: entry.replace(m[0], '').replace(/^[\s(]+|[\s)]+$/g, '') };
	}

	/** The software credits behind one entry of the software list (some entries name several packages). */
	const creditsFor = (name: string) => SOFTWARE_CREDITS.filter((c) => c.listedAs === name || c.name === name);

	/** The tools by step, in the order of a run (credits.ts numbers the steps). */
	const PHASE_NAMES: Record<number, string> = {
		1: 'Quality',
		2: 'Taxonomy',
		3: 'Gene calling',
		4: 'Function',
		5: 'Operons',
		6: 'Envelope',
		7: 'Topology and localisation'
	};
	const BY_PHASE = [...new Set(RUN_TOOLS.map((t) => t.phase))].map((n) => ({ n, name: PHASE_NAMES[n] ?? `Step ${n}`, tools: RUN_TOOLS.filter((t) => t.phase === n) }));
	const [AWARD_BEFORE, AWARD_AFTER] = COMPUTING.thanks.split('OAC-2018926');
</script>

<svelte:head><title>Acknowledgements | MARGIE</title></svelte:head>

<ReadingPage title="Acknowledgements" lede="The people, funding, tools and computing that MARGIE is built on." shade="page-acknowledgements">
	<section class="rp-sec" id="thanks" data-toc="With thanks">
		<h2>With thanks</h2>
		<p class="rp-lead">
			MARGIE is built on databases and tools that others built and shared. We humbly acknowledge each team whose tools and databases
			MARGIE uses: their work, and their choice to share it, made MARGIE possible.
		</p>
		<p>
			Sajal Bhattarai gratefully acknowledges Dane Deemer (<a href="https://github.com/wintermutant" target="_blank" rel="noreferrer">wintermutant</a>)
			for his mentoring, and for the design and development of the engine and GUI orchestration platform,
			<a href="https://github.com/wintermutant/bioinformatics-tools" target="_blank" rel="noreferrer">BSP</a>, on which MARGIE was built. Special thanks
			go to Dr. {LAB.pi} for his vision, supervision and support throughout MARGIE's development, and to the members of the {LAB.name} for their
			feedback and ideas.
		</p>
		<p>
			{AWARD_BEFORE}<a href={COMPUTING.award} target="_blank" rel="noreferrer">OAC-2018926</a>{AWARD_AFTER} RCAC's citations are under
			<a href="#computing">Computing</a>.
		</p>
		<p class="rp-note">
			If you publish results from MARGIE, please cite MARGIE and the tools and databases she ran for you, listed under
			<a href="#references">References</a> (<a href="/contributors#cite">how to cite</a>).
		</p>
	</section>

	<section class="rp-sec" id="funding" data-toc="Funding">
		<h2>Funding</h2>
		<p>MARGIE was developed in the {LAB.name} with support from these grants (PI: {LAB.pi}).</p>
		<div class="rp-pair">
			{#each FUNDING as f (f.award)}
				<div class="rp-tile ak-grant">
					<Landmark size={22} />
					<b>{f.funder}</b>
					<a href={f.url} target="_blank" rel="noreferrer">{f.award}</a>
					<i>{f.title}</i>
				</div>
			{/each}
		</div>
	</section>

	<section class="rp-sec" id="ai-usage" data-toc="AI usage">
		<h2>AI usage in the project</h2>
		{#each AI_USAGE.paragraphs as p (p)}<p>{p}</p>{/each}
		<p class="rp-cite">
			{AI_USAGE.reference.apa} <a href={AI_USAGE.reference.url} target="_blank" rel="noreferrer">{AI_USAGE.reference.url}</a>
		</p>
	</section>

	<section class="rp-sec" id="tools" data-toc="Tools and databases">
		<h2>Tools and databases MARGIE runs</h2>
		<p class="rp-note">
			The version each step uses, its licence as its provider states it, its source code and where its data comes from. Each user fetches the
			tools for academic use from their providers, under the provider's licence.
		</p>
		{#each BY_PHASE as g (g.n)}
			<div class="ak-phase">
				<h3>{g.name}</h3>
				{#each g.tools as t (t.id)}
					<article class="ak-tool">
						<header>
							<b>{t.name}</b>
							<span class="ak-ver">{t.version}</span>
							{#if !t.versionExact}<span class="ak-moving">moving release</span>{/if}
						</header>
						{#if t.role}<p class="rp-note">{t.role}</p>{/if}
						<dl>
							<dt>Licence</dt>
							<dd>
								{#if t.licenceUrl}<a href={t.licenceUrl} target="_blank" rel="noreferrer">{t.licence}</a>{:else}{t.licence}{/if}
								{#if t.catalogLicence && t.catalogLicence !== t.licence}<span class="rp-note"> | MARGIE's licence terms record: {t.catalogLicence}</span>{/if}
							</dd>
							{#if t.source}
								<dt>Source code</dt>
								<dd><a href={t.source} target="_blank" rel="noreferrer">{new URL(t.source).host}</a></dd>
							{/if}
							{#if t.downloads.length}
								<dt>Data from</dt>
								<dd>
									<ul class="rp-plain">
										{#each t.downloads as d (d)}
											{@const x = download(d)}
											<li>
												{#if x.url}<a href={x.url} target="_blank" rel="noreferrer">{x.label}</a>{:else}{x.label}{/if}
												{#if x.note}<span class="rp-note"> ({x.note})</span>{/if}
											</li>
										{/each}
									</ul>
								</dd>
							{/if}
						</dl>
					</article>
				{/each}
			</div>
		{/each}
	</section>

	<section class="rp-sec" id="software" data-toc="Software">
		<h2>Software MARGIE is built with</h2>
		<p class="rp-note">MARGIE runs on open-source software that others write and share. Thank you to each of these projects.</p>
		<div class="ak-sw">
			{#each SOFTWARE as g (g.group)}
				<div class="ak-sw-g">
					<h3>{g.group}</h3>
					<ul class="rp-plain">
						{#each g.items as it (it.name)}
							<li>
								<a href={it.href} target="_blank" rel="noreferrer">{it.name}</a> <span class="rp-note">{it.what}</span>
								{#each creditsFor(it.name) as c (c.name)}
									<span class="ak-cred"
										>{c.name}{#if c.version} {c.version}{/if} | {#if c.licenceUrl}<a href={c.licenceUrl} target="_blank" rel="noreferrer">{c.licence}</a
											>{:else}{c.licence}{/if}{#if c.source}
											| <a href={c.source} target="_blank" rel="noreferrer">source</a>{/if}</span
									>
								{/each}
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		</div>
	</section>

	<section class="rp-sec" id="computing" data-toc="Computing">
		<h2>Computing</h2>
		<p class="rp-note">The research computing MARGIE runs on, cited with MARGIE.</p>
		<ol class="rp-refs">
			{#each COMPUTING.refs as r (r.id)}
				<li>{r.apa} <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a></li>
			{/each}
		</ol>
	</section>

	<section class="rp-sec" id="references" data-toc="References">
		<h2>References</h2>
		<div class="rp-row">
			<button type="button" class="mg-btn primary small" onclick={downloadBibtex}><Download size={14} /> Download the citations (BibTeX)</button>
			<span class="rp-note">With MARGIE's own, the thesis and the research computing (<a href="/contributors#cite">how to cite</a>).</span>
		</div>
		<ul class="rp-plain ak-refs">
			{#each [...RUN_TOOLS.filter((t) => t.cite.length), ...CITED_SOFTWARE] as t ('id' in t ? t.id : t.name)}
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
	</section>
</ReadingPage>

<style>
	.ak-grant {
		gap: 4px;
	}
	.ak-grant i {
		color: var(--mg-text);
	}
	.ak-phase {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.ak-phase + .ak-phase {
		margin-top: 8px;
	}
	/* A tool: its name and version, then licence, source and data in two columns. */
	.ak-tool {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 14px 18px;
		border: 1px solid var(--rp-edge);
		border-radius: var(--mg-r);
		font-size: var(--rp-small);
		line-height: 1.55;
	}
	.ak-tool header {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
	}
	.ak-tool header b {
		font-size: var(--rp-body);
		font-weight: 650;
	}
	.ak-ver {
		color: var(--mg-text-2);
		font-variant-numeric: tabular-nums;
	}
	.ak-moving {
		padding: 0 8px;
		border: 1px solid var(--rp-edge);
		border-radius: 999px;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-xs);
	}
	.ak-tool dl {
		display: grid;
		grid-template-columns: max-content minmax(0, 1fr);
		gap: 4px 16px;
		margin: 2px 0 0;
	}
	.ak-tool dt {
		color: var(--mg-text-3);
		font-weight: 600;
	}
	.ak-tool dd {
		margin: 0;
		min-width: 0;
	}
	.ak-tool dd li + li {
		margin-top: 2px;
	}
	.ak-sw {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 22px 28px;
	}
	.ak-sw-g h3 {
		margin: 0 0 8px;
	}
	.ak-sw-g ul {
		display: flex;
		flex-direction: column;
		gap: 8px;
		font-size: var(--rp-small);
		line-height: 1.5;
	}
	.ak-sw-g li + li {
		margin-top: 0;
	}
	.ak-cred {
		display: block;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
	}
	.ak-refs {
		display: flex;
		flex-direction: column;
		gap: 14px;
		font-size: var(--rp-small);
	}
	.ak-refs > li + li {
		margin-top: 0;
	}
	.ak-refs .rp-refs {
		margin-top: 4px;
	}
	@container (max-width: 720px) {
		.ak-sw {
			grid-template-columns: minmax(0, 1fr);
		}
		.ak-tool dl {
			grid-template-columns: minmax(0, 1fr);
			gap: 0;
		}
		.ak-tool dd + dt {
			margin-top: 6px;
		}
	}
</style>
