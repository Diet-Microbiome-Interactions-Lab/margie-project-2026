<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ChevronRight, ChevronsDownUp, ChevronsUpDown, Search } from 'lucide-svelte';
	import { LAB } from './about';
	import { FAQS, GROUPS, REFS, type Faq } from './faq';
	import FaqCode from './FaqCode.svelte';
	import { LockedError, alreadyOpen, openLocked, relock, type LockedPage } from './locked';

	/**
	 * The FAQ (its own page, /faq): how MARGIE works, question by question. Each answer names the papers it
	 * rests on and can show the code that does what it says; a thesis panel (under embargo) opens
	 * with the password. A link to #<question id> opens that question.
	 */
	let query = $state('');
	let opened = $state<Record<string, boolean>>({});
	let thesis = $state<LockedPage | null>(alreadyOpen('faq'));
	let password = $state('');
	let busy = $state(false);
	let lockError = $state('');

	const words = $derived(query.trim().toLowerCase().split(/\s+/).filter(Boolean));
	const plain = (html: string) => html.replace(/<[^>]+>/g, ' ');
	const matches = (f: Faq) => words.every((w) => `${f.q} ${plain(f.a.join(' '))}`.toLowerCase().includes(w));
	const shown = $derived(GROUPS.map((g) => ({ g, faqs: FAQS.filter((f) => f.group === g && matches(f)) })).filter((x) => x.faqs.length));
	const count = $derived(shown.reduce((n, x) => n + x.faqs.length, 0));
	/** The references the answers cite, in alphabetical order, numbered for the list at the foot. */
	const cited = $derived([...new Set(FAQS.flatMap((f) => f.refs))].filter((id) => REFS[id]).sort((a, b) => REFS[a].apa.localeCompare(REFS[b].apa)));

	/** What each group's questions cover. */
	const META: Record<string, { blurb: string }> = {
		'Running MARGIE': { blurb: 'How MARGIE reaches your cluster, calls genes and writes results, and the versions and licences behind each step.' },
		'Inside the pipeline': { blurb: 'Hashing, consolidation, labels, envelopes, operons and fingerprints: what each step does and why.' },
		'Databases and provenance': { blurb: 'What MARGIE keeps, how it grows with each genome, and how each result can be traced.' },
		Scoring: { blurb: 'How confident MARGIE is in each label: the four measures, C3 in depth, and how it was checked.' }
	};
	const slug = (g: string) => 'g-' + g.toLowerCase().replace(/[^a-z]+/g, '-');

	function setAll(open: boolean) {
		opened = Object.fromEntries(FAQS.map((f) => [f.id, open]));
	}

	async function unlock(e: SubmitEvent) {
		e.preventDefault();
		if (!password || busy) return;
		busy = true;
		lockError = '';
		try {
			thesis = await openLocked('faq', password);
			password = '';
		} catch (err) {
			lockError = err instanceof LockedError || err instanceof Error ? err.message : 'The panels could not be opened.';
		} finally {
			busy = false;
		}
	}

	onMount(async () => {
		const id = decodeURIComponent(location.hash.slice(1));
		if (FAQS.some((f) => f.id === id)) {
			opened[id] = true;
			await tick();
			document.getElementById(id)?.scrollIntoView({ block: 'start' });
		}
	});
</script>

<div class="fq-list">
	<div class="fq-bar">
		<label class="fq-search">
			<Search size={16} />
			<input class="mg-input" type="search" placeholder="Search the questions" bind:value={query} aria-label="Search the questions" />
		</label>
		<button type="button" class="mg-btn small" onclick={() => setAll(true)}><ChevronsUpDown size={14} /> Expand all</button>
		<button type="button" class="mg-btn small" onclick={() => setAll(false)}><ChevronsDownUp size={14} /> Collapse all</button>
	</div>
	{#if words.length}<p class="ab-lab">{count} question{count === 1 ? '' : 's'} match.</p>{/if}

	{#each shown as { g, faqs } (g)}
		<section class="fq-group" id={slug(g)} data-toc="{g} ({FAQS.filter((f) => f.group === g).length})">
			<header class="fq-ghead">
				<div>
					<h2>{g}</h2>
					{#if META[g]}<p>{META[g].blurb}</p>{/if}
				</div>
			</header>
			{#each faqs as f (f.id)}
				{@const n = FAQS.indexOf(f) + 1}
				<details id={f.id} class="fq" bind:open={opened[f.id]}>
					<summary><span class="fq-n">{n}</span><span class="fq-q">{f.q}</span><ChevronRight size={20} class="fq-chev" /></summary>
					<div class="fq-a">
						<div class="fq-text">{#each f.a as p, i (i)}{@html p}{/each}</div>

						{#if f.code.length}
							<div class="fq-part">
								<h3>The code</h3>
								{#each f.code as c (c.path + c.symbol)}<FaqCode code={c} />{/each}
							</div>
						{/if}

						{#if f.thesis}
							<div class="fq-part fq-thesis">
								<h3>From the thesis</h3>
								{#if thesis?.sections[f.id]}
									<div class="fq-text fq-thesis-body">{@html thesis.sections[f.id]}</div>
									<button type="button" class="mg-btn small fq-relock" onclick={() => (relock('faq'), (thesis = null))}>Lock the thesis panels again</button>
								{:else}
									<p class="ab-lab">
										More on this, with figures, from the thesis, which is under embargo. It opens with a password; ask the {LAB.name}
										(<a class="mg-link" href="mailto:{LAB.email}?subject=MARGIE%20FAQ">{LAB.email}</a>).
									</p>
									<form class="fq-form" onsubmit={unlock}>
										<input class="mg-input" type="password" autocomplete="off" placeholder="Password" aria-label="Password" bind:value={password} disabled={busy} />
										<button type="submit" class="mg-btn small" disabled={!password || busy}>{busy ? 'Opening…' : 'Open'}</button>
									</form>
									{#if lockError}<p class="fq-error" role="alert">{lockError}</p>{/if}
								{/if}
							</div>
						{/if}

						{#if f.refs.length}
							<details class="fq-part fq-refs">
								<summary><h3>References ({f.refs.filter((r) => REFS[r]).length})</h3><ChevronRight size={15} class="fq-fold" /></summary>
								<ul>
									{#each f.refs.filter((r) => REFS[r]) as r (r)}
										<li>{REFS[r].apa} {#if REFS[r].url}<a class="mg-link" href={REFS[r].url} target="_blank" rel="noreferrer">{REFS[r].url}</a>{/if}</li>
									{/each}
								</ul>
							</details>
						{/if}
						<a class="fq-link" href="#{f.id}">Link to this question</a>
					</div>
				</details>
			{/each}
		</section>
	{/each}

	{#if !count}<section class="fq-group"><p>0 questions match “{query}”.</p></section>{/if}

	<section class="fq-group fq-allrefs" id="faq-references" data-toc="References">
		<header class="fq-ghead">
			<div>
				<h2>References</h2>
				<p>{cited.length} works the answers rest on.</p>
			</div>
		</header>
		<details class="fq-refs-all">
			<summary>Show the {cited.length} references <ChevronRight size={15} class="fq-fold" /></summary>
			<ol class="fq-all">
				{#each cited as r (r)}
					<li>{REFS[r].apa} {#if REFS[r].url}<a class="mg-link" href={REFS[r].url} target="_blank" rel="noreferrer">{REFS[r].url}</a>{/if}</li>
				{/each}
			</ol>
		</details>
		<p class="ab-lab">
			The citations, with one BibTeX file of each, are on <a class="mg-link" href="/contributors#cite">Contributors</a>; the tools and databases
			MARGIE runs, with their versions and licences, are on <a class="mg-link" href="/acknowledgements">Acknowledgements</a>.
		</p>
	</section>
</div>

<style>
	.fq-list {
		--fq-body: var(--rp-body, calc(var(--mg-fs) + 3px));
		--fq-tint: var(--rp-stripe, color-mix(in srgb, var(--mg-text) 5%, var(--mg-surface)));
		display: flex;
		flex-direction: column;
		gap: 18px;
	}
	.fq-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}
	.fq-search {
		display: flex;
		flex: 1;
		align-items: center;
		gap: 8px;
		min-width: 220px;
		color: var(--mg-text-3);
	}
	.fq-search input {
		flex: 1;
		font-size: var(--mg-fs);
	}
	/* A group: a white card with a header. */
	.fq-group {
		display: flex;
		flex-direction: column;
		scroll-margin-top: 18px;
	}
	.fq-ghead {
		display: flex;
		align-items: center;
		gap: 14px;
		padding-bottom: 12px;
	}
	.fq-ghead h2 {
		margin: 0;
		color: var(--rp-head, var(--mg-text));
		font-family: var(--rp-head-font, inherit);
		font-size: var(--rp-h2, var(--mg-fs-xl));
		font-weight: 700;
		line-height: 1.25;
	}
	.fq-ghead p {
		margin: 2px 0 0;
		color: var(--mg-text-2);
		font-size: var(--rp-small, var(--mg-fs));
		line-height: 1.5;
	}
	/* A question. */
	.fq {
		border-top: 1px solid var(--rp-line, var(--mg-border));
		scroll-margin-top: 12px;
	}
	.fq summary {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 14px 6px;
		border-radius: var(--mg-r-sm);
		cursor: pointer;
		list-style: none;
	}
	.fq summary::-webkit-details-marker {
		display: none;
	}
	.fq summary:hover {
		background: var(--fq-tint);
	}
	.fq-n {
		display: grid;
		flex: 0 0 auto;
		place-items: center;
		width: 34px;
		height: 34px;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-radius: 50%;
		background: var(--rp-paper, var(--mg-surface));
		color: var(--rp-link, var(--mg-accent));
		font-size: var(--mg-fs);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.fq[open] .fq-n {
		border-color: var(--rp-link, var(--mg-accent));
		background: var(--rp-link, var(--mg-accent));
		color: #fff;
	}
	.fq-q {
		flex: 1;
		color: var(--rp-head, var(--mg-text));
		font-size: var(--rp-h3, calc(var(--mg-fs) + 4px));
		font-weight: 700;
		line-height: 1.38;
	}
	.fq[open] .fq-q {
		color: var(--rp-link, var(--mg-accent));
	}
	.fq summary :global(.fq-chev) {
		flex: 0 0 auto;
		color: var(--mg-text-3);
		transition: transform 150ms ease;
	}
	.fq[open] summary :global(.fq-chev) {
		transform: rotate(90deg);
		color: var(--rp-link, var(--mg-accent));
	}
	/* The answer: large, airy text in a readable column. */
	.fq-a {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 4px 6px 24px 54px;
	}
	.fq-text {
		display: flex;
		flex-direction: column;
		gap: 14px;
		font-size: var(--fq-body);
		line-height: 1.72;
		color: var(--mg-text);
	}
	.fq-text :global(p) {
		text-wrap: pretty;
	}
	.fq-text :global(p) {
		margin: 0;
	}
	.fq-text :global(b) {
		color: var(--mg-text);
		font-weight: 650;
	}
	.fq-text :global(ul),
	.fq-text :global(ol) {
		margin: 0;
		padding-left: 1.5em;
	}
	.fq-text :global(ul) {
		list-style: disc;
	}
	.fq-text :global(ol) {
		list-style: decimal;
	}
	.fq-text :global(li::marker) {
		color: var(--mg-text-3);
	}
	.fq-text :global(li + li) {
		margin-top: 6px;
	}
	.fq-text :global(code) {
		padding: 1px 5px;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-radius: 2px;
		background: var(--rp-paper, var(--mg-surface));
		color: var(--rp-lit, var(--mg-text));
		font-family: var(--mg-mono);
		font-size: 0.82em;
	}
	/* Formulas, as literal blocks. */
	.fq-text :global(pre) {
		margin: 0;
		padding: 12px 16px;
		border: 1px solid var(--rp-line, var(--mg-border));
		background: var(--rp-pre, var(--mg-surface-2));
		font-family: var(--mg-mono);
		font-size: var(--mg-fs);
		line-height: 1.6;
		white-space: pre-wrap;
	}
	/* Tables: ruled cells, striped rows. */
	.fq-text :global(table) {
		width: 100%;
		border: 1px solid var(--rp-line, var(--mg-border));
		border-collapse: collapse;
		font-size: var(--mg-fs);
		line-height: 1.5;
	}
	.fq-text :global(th) {
		padding: 8px 10px;
		border: 1px solid var(--rp-line, var(--mg-border));
		color: var(--rp-head, var(--mg-text));
		font-weight: 700;
		text-align: left;
	}
	.fq-text :global(td) {
		padding: 8px 10px;
		border: 1px solid var(--rp-line, var(--mg-border));
		vertical-align: top;
		overflow-wrap: anywhere;
	}
	.fq-text :global(tbody tr:nth-child(odd) td) {
		background: var(--fq-tint);
	}
	/* The parts under an answer. */
	.fq-part {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.fq-part h3 {
		display: flex;
		align-items: center;
		gap: 7px;
		margin: 0;
		color: var(--rp-ink, var(--mg-accent));
		font-size: var(--mg-fs-sm);
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
	}
	.fq-thesis {
		padding: 14px 16px;
		border: 1px solid var(--rp-line, var(--mg-border));
		background: var(--rp-pre, var(--mg-surface-2));
	}
	.fq-thesis-body :global(figure) {
		margin: 4px 0;
	}
	.fq-thesis-body :global(img) {
		display: block;
		width: 100%;
		max-width: 860px;
		height: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: #fff;
	}
	.fq-thesis-body :global(figcaption) {
		margin-top: 6px;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
	}
	.fq-relock {
		align-self: flex-start;
	}
	.fq-form {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.fq-form input {
		flex: 1;
		min-width: 160px;
		max-width: 320px;
	}
	.fq-error {
		margin: 0;
		color: var(--mg-danger, #c0392b);
	}
	/* References fold away until asked for. */
	.fq-refs > summary,
	.fq-refs-all > summary {
		display: flex;
		align-items: center;
		gap: 6px;
		width: max-content;
		cursor: pointer;
		list-style: none;
	}
	.fq-refs > summary::-webkit-details-marker,
	.fq-refs-all > summary::-webkit-details-marker {
		display: none;
	}
	.fq-refs-all > summary {
		margin-bottom: 8px;
		color: var(--rp-link, var(--mg-accent));
		font-size: var(--mg-fs);
		font-weight: 600;
	}
	.fq-refs :global(.fq-fold),
	.fq-refs-all :global(.fq-fold) {
		color: var(--mg-text-3);
		transition: transform 150ms ease;
	}
	.fq-refs[open] :global(.fq-fold),
	.fq-refs-all[open] :global(.fq-fold) {
		transform: rotate(90deg);
	}
	.fq-refs ul {
		margin: 0;
		padding-left: 1.3em;
		list-style: disc;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
		line-height: 1.55;
	}
	.fq-refs li + li {
		margin-top: 4px;
	}
	.fq-refs a,
	.fq-all a {
		overflow-wrap: anywhere;
	}
	.fq-link {
		align-self: flex-start;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
	}
	.fq-allrefs {
		padding-bottom: 18px;
	}
	.fq-all {
		margin: 0 0 10px;
		padding-left: 1.8em;
		list-style: decimal;
		font-size: var(--mg-fs-sm);
		line-height: 1.55;
	}
	.fq-all li + li {
		margin-top: 5px;
	}
	@media (max-width: 640px) {
		.fq-a {
			padding-left: 4px;
		}
		.fq-q {
			font-size: calc(var(--mg-fs) * 1.1);
		}
	}
</style>
