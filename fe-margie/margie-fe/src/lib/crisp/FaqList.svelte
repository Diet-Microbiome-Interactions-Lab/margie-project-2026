<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ChevronRight, ChevronsDownUp, ChevronsUpDown, Lightbulb, LockKeyhole, Search } from 'lucide-svelte';
	import { LAB } from './about';
	import { FAQS, GROUPS, REFS, type Faq } from './faq';
	import FaqCode from './FaqCode.svelte';
	import { LockedError, alreadyOpen, openLocked, type LockedPage } from './locked';

	/**
	 * The FAQ (on Methods): how MARGIE works, question by question. Each answer names the papers it
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
				<Search size={15} />
				<input class="mg-input" type="search" placeholder="Search the questions" bind:value={query} aria-label="Search the questions" />
			</label>
			<button type="button" class="mg-btn small" onclick={() => setAll(true)}><ChevronsUpDown size={14} /> Expand all</button>
			<button type="button" class="mg-btn small" onclick={() => setAll(false)}><ChevronsDownUp size={14} /> Collapse all</button>
			<a class="mg-btn small" href="/quiz?topic=margie"><Lightbulb size={14} /> MARGIE quiz</a>
		</div>
		{#if words.length}<p class="ab-lab">{count} question{count === 1 ? '' : 's'} match.</p>{/if}

		{#each shown as { g, faqs } (g)}
			<section class="ab-box fq-group">
				<h2>{g}</h2>
				{#each faqs as f (f.id)}
					{@const n = FAQS.indexOf(f) + 1}
					<details id={f.id} class="fq" bind:open={opened[f.id]}>
						<summary><ChevronRight size={16} class="fq-chev" /><span class="fq-n">{n}</span><span class="fq-q">{f.q}</span></summary>
						<div class="fq-a">
							{#each f.a as p, i (i)}{@html p}{/each}

							{#if f.code.length}
								<div class="fq-code">
									<h3>The code</h3>
									{#each f.code as c (c.path + c.symbol)}<FaqCode code={c} />{/each}
								</div>
							{/if}

							{#if f.thesis}
								<div class="fq-thesis">
									<h3><LockKeyhole size={13} /> From the thesis</h3>
									{#if thesis?.sections[f.id]}
										<div class="fq-thesis-body">{@html thesis.sections[f.id]}</div>
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
								<div class="fq-refs">
									<h3>References</h3>
									<ul>
										{#each f.refs.filter((r) => REFS[r]) as r (r)}
											<li>{REFS[r].apa} {#if REFS[r].url}<a class="mg-link" href={REFS[r].url} target="_blank" rel="noreferrer">{REFS[r].url}</a>{/if}</li>
										{/each}
									</ul>
								</div>
							{/if}
							<a class="fq-link" href="#{f.id}">Link to this question</a>
						</div>
					</details>
				{/each}
			</section>
		{/each}

		{#if !count}<section class="ab-box"><p>No question matches “{query}”.</p></section>{/if}

		<section class="ab-box">
			<h2>References</h2>
			<ol class="fq-all">
				{#each cited as r (r)}
					<li>{REFS[r].apa} {#if REFS[r].url}<a class="mg-link" href={REFS[r].url} target="_blank" rel="noreferrer">{REFS[r].url}</a>{/if}</li>
				{/each}
			</ol>
			<p class="ab-lab">
				To cite MARGIE herself, see <a class="mg-link" href="/contributors">Contributors</a>; the tools and databases she runs, with their versions and
				licences, are on <a class="mg-link" href="/acknowledgements">Acknowledgements</a>.
			</p>
		</section>
	</div>

<style>
	.fq-list {
		display: flex;
		flex-direction: column;
		gap: var(--cr-gutter, 16px);
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
		gap: 6px;
		min-width: 220px;
		color: var(--mg-text-3);
	}
	.fq-search input {
		flex: 1;
	}
	.fq-group {
		gap: 0;
	}
	.fq-group > h2 {
		margin-bottom: 6px;
	}
	.fq {
		border-top: 1px solid var(--mg-border);
	}
	.fq summary {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 10px 2px;
		cursor: pointer;
		list-style: none;
		font-size: var(--mg-fs-lg);
		font-weight: 600;
	}
	.fq summary::-webkit-details-marker {
		display: none;
	}
	.fq summary:hover .fq-q {
		color: var(--mg-accent);
	}
	.fq summary :global(.fq-chev) {
		flex: 0 0 auto;
		align-self: center;
		color: var(--mg-text-3);
		transition: transform 150ms ease;
	}
	.fq[open] summary :global(.fq-chev) {
		transform: rotate(90deg);
		color: var(--mg-accent);
	}
	.fq-n {
		flex: 0 0 auto;
		min-width: 1.6em;
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.fq-a {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 0 4px 16px calc(16px + 1.6em + 16px);
		max-width: 980px;
	}
	.fq-a :global(p) {
		margin: 0;
	}
	.fq-a :global(ul),
	.fq-a :global(ol) {
		margin: 0;
		padding-left: 1.4em;
	}
	.fq-a :global(ul) {
		list-style: disc;
	}
	.fq-a :global(ol) {
		list-style: decimal;
	}
	.fq-a :global(li + li) {
		margin-top: 3px;
	}
	/* Tables in an answer, as on the About pages. */
	.fq-a :global(table) {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--mg-fs);
	}
	.fq-a :global(th) {
		padding: 6px 8px;
		border-bottom: 1px solid var(--mg-border);
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
		font-weight: 600;
		text-align: left;
	}
	.fq-a :global(td) {
		padding: 6px 8px;
		border-top: 1px solid var(--mg-border);
		vertical-align: top;
		overflow-wrap: anywhere;
	}
	.fq-a :global(tr:first-child td) {
		border-top: none;
	}
	.fq-a :global(pre) {
		margin: 0;
		padding: 8px 12px;
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
		font-family: var(--mg-mono);
		font-size: var(--mg-fs-sm);
		white-space: pre-wrap;
	}
	.fq-a :global(code) {
		font-family: var(--mg-mono);
		font-size: 0.92em;
	}
	.fq-a h3 {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		font-size: var(--mg-fs-sm);
		font-weight: 650;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.fq-code {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.fq-thesis {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
	}
	.fq-thesis-body {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.fq-thesis-body :global(figure) {
		margin: 4px 0;
	}
	.fq-thesis-body :global(img) {
		display: block;
		width: 100%;
		max-width: 820px;
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
		color: var(--mg-danger, #c0392b);
	}
	.fq-refs ul {
		margin: 4px 0 0;
		padding-left: 1.2em;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
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
	.fq-all {
		margin: 0;
		padding-left: 1.6em;
		font-size: var(--mg-fs-sm);
	}
	.fq-all li + li {
		margin-top: 4px;
	}
	@media (max-width: 640px) {
		.fq-a {
			padding-left: 4px;
		}
	}
</style>
