<script lang="ts">
	import '$lib/crisp/about.css';
	import { Download } from 'lucide-svelte';
	import { COMPUTING, LAB, SOFTWARE } from '$lib/crisp/about';
	import { SOFTWARE_CREDITS } from '$lib/crisp/credits';
	import { RUN_TOOLS, downloadBibtex } from '$lib/crisp/bibtex';

	/**
	 * Acknowledgements: the tools and databases MARGIE runs (credits.ts, checked against their own
	 * pages): each one's version, licence, source code and data sources, and the papers it asks to be
	 * cited; then the software MARGIE herself is built with, and the research computing she runs on.
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
				Special thanks go to Dr. {LAB.pi} for his vision, supervision and support throughout her development, and to the members of the
				{LAB.name} for their feedback and ideas.
			</p>
			<p>
				{COMPUTING.thanks.split('OAC-2018926')[0]}<a class="mg-link" href={COMPUTING.award} target="_blank" rel="noreferrer">OAC-2018926</a>{COMPUTING.thanks.split('OAC-2018926')[1]}
				Please cite RCAC's computing as it asks, below.
			</p>
			<p class="ab-lab">
				If you publish results from MARGIE, please cite the tools and databases she ran for you, below, as well as MARGIE herself
				(<a class="mg-link" href="/contributors">how to cite</a>).
			</p>
		</section>

		<section class="ab-box">
			<h2>Tools and databases she runs</h2>
			<p class="ab-lab">
				The version each step uses, its licence as its provider states it, its source code and where its data comes from. Tools for
				academic use only are fetched from their providers by each user, under the provider's licence.
			</p>
			<div class="tl-scroll">
				<table class="ab-table tl">
					<thead><tr><th>Phase</th><th>Tool</th><th>Version</th><th>Licence</th><th>Source code</th><th>Data from</th></tr></thead>
					<tbody>
						{#each RUN_TOOLS as t (t.id)}
							<tr>
								<td class="ab-num">{t.phase}</td>
								<td><b>{t.name}</b>{#if t.role}<br /><span class="ab-lab">{t.role}</span>{/if}</td>
								<td>{t.version}{#if !t.versionExact}<br /><span class="ab-lab">recorded as a moving release</span>{/if}</td>
								<td>
									{#if t.licenceUrl}<a class="mg-link" href={t.licenceUrl} target="_blank" rel="noreferrer">{t.licence}</a>{:else}{t.licence}{/if}
									{#if t.catalogLicence && t.catalogLicence !== t.licence}<br /><span class="ab-lab">MARGIE's licence terms record: {t.catalogLicence}</span>{/if}
								</td>
								<td>{#if t.source}<a class="mg-link" href={t.source} target="_blank" rel="noreferrer">{new URL(t.source).host}</a>{/if}</td>
								<td>
									<ul class="tl-dl">
										{#each t.downloads as d (d)}
											{@const x = download(d)}
											<li>
												{#if x.url}<a class="mg-link" href={x.url} target="_blank" rel="noreferrer">{x.label}</a>{:else}{x.label}{/if}
												{#if x.note}<span class="ab-lab"> ({x.note})</span>{/if}
											</li>
										{/each}
									</ul>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		<section class="ab-box">
			<h2>Software she is built with</h2>
			<p class="ab-lab">MARGIE runs on open-source software that others write and share. Thank you to each of these projects.</p>
			<div class="sw">
				{#each SOFTWARE as g (g.group)}
					<div class="sw-g">
						<h3>{g.group}</h3>
						<ul>
							{#each g.items as it (it.name)}
								<li>
									<a class="mg-link" href={it.href} target="_blank" rel="noreferrer">{it.name}</a> <span>{it.what}</span>
									{#each creditsFor(it.name) as c (c.name)}
										<br /><span class="sw-l"
											>{c.name}{#if c.version} {c.version}{/if} | {#if c.licenceUrl}<a class="mg-link" href={c.licenceUrl} target="_blank" rel="noreferrer"
													>{c.licence}</a
												>{:else}{c.licence}{/if}{#if c.source}
												| <a class="mg-link" href={c.source} target="_blank" rel="noreferrer">source</a>{/if}</span
										>
									{/each}
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>
		</section>

		<section class="ab-box">
			<h2>Computing</h2>
			<p class="ab-lab">The research computing MARGIE runs on, to cite beside her (as RCAC asks).</p>
			<ol class="refs">
				{#each COMPUTING.refs as r (r.id)}
					<li>{r.apa} <a class="mg-link" href={r.url} target="_blank" rel="noreferrer">{r.url}</a></li>
				{/each}
			</ol>
		</section>

		<section class="ab-box">
			<h2>References</h2>
			<div class="acts">
				<button type="button" class="mg-btn primary small" onclick={downloadBibtex}><Download size={14} /> Download the citations (BibTeX)</button>
				<span class="ab-lab">With MARGIE's own, the thesis and the research computing (<a class="mg-link" href="/contributors">how to cite</a>).</span>
			</div>
			<ul class="refs">
				{#each RUN_TOOLS.filter((t) => t.cite.length) as t (t.id)}
					<li>
						<b>{t.name}</b>
						{#if t.citeRequired}<span class="cite-req">asks to be cited</span>{/if}
						{#if t.citeRule}<span class="ab-lab cite-rule">“{t.citeRule}”{#if t.citeRuleUrl} (<a class="mg-link" href={t.citeRuleUrl} target="_blank" rel="noreferrer">its page</a>){/if}</span>{/if}
						<ol>
							{#each t.cite as c (c.key)}
								<li>{c.apa}{#if c.doi} <a class="mg-link" href="https://doi.org/{c.doi}" target="_blank" rel="noreferrer">doi:{c.doi}</a>{/if}</li>
							{/each}
						</ol>
					</li>
				{/each}
			</ul>
		</section>
	</div>
</div>

<style>
	.tl-scroll {
		overflow-x: auto;
	}
	.tl td {
		font-size: var(--mg-fs-xs);
	}
	.tl a {
		overflow-wrap: anywhere;
	}
	.tl-dl {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.tl-dl li + li {
		margin-top: 2px;
	}
	.sw-l {
		font-size: var(--mg-fs-xs);
	}
	.acts {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}
	.refs {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.refs ol {
		margin: 4px 0 0;
		padding-left: 1.4em;
		list-style: decimal;
		font-size: var(--mg-fs-sm);
	}
	.refs a,
	.sw-l a {
		overflow-wrap: anywhere;
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
