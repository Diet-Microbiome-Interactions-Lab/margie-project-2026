<script lang="ts">
	import '$lib/crisp/about.css';
	import { ArrowLeft, LockKeyhole } from 'lucide-svelte';
	import { LAB } from '$lib/crisp/about';
	import { LockedError, alreadyOpen, openLocked, relock, type LockedPage } from '$lib/crisp/locked';

	/**
	 * Reading the scores: what a gene's confidence is made of, C3's two channels, the genome pool and
	 * what to make of a score. It draws on a thesis under embargo, so it opens with a password the lab
	 * gives on request (lib/crisp/locked.ts). Opened from Methods (no sidebar entry).
	 */
	let page = $state<LockedPage | null>(alreadyOpen('scores'));
	let password = $state('');
	let busy = $state(false);
	let error = $state('');
	let missing = $state(false);

	async function open(e: SubmitEvent) {
		e.preventDefault();
		if (!password || busy) return;
		busy = true;
		error = '';
		try {
			page = await openLocked('scores', password);
			password = '';
		} catch (err) {
			error = err instanceof Error ? err.message : 'The page could not be opened.';
			missing = err instanceof LockedError && err.kind === 'missing';
		} finally {
			busy = false;
		}
	}
	/** The opened page: its text is for reading here, so copying from it is held back. */
	let body = $state<HTMLElement>();
</script>

<svelte:head><title>Reading the scores | MARGIE</title></svelte:head>

<svelte:document
	oncopy={(e) => {
		const sel = getSelection();
		if (body && sel && !sel.isCollapsed && sel.rangeCount && sel.getRangeAt(0).intersectsNode(body)) e.preventDefault();
	}}
/>

<div class="cr-page" data-shade="page-methods">
	<div class="cr-head">
		<a class="mg-link sc-back" href="/methods"><ArrowLeft size={14} /> Methods</a>
		<h1 class="cr-title">Reading the scores</h1>
		<p class="cr-lede">What a gene’s confidence is made of, how C3 compares it with the genome pool, and what to make of a score.</p>
	</div>

	{#if page}
		<div class="sc-relock">
			<button type="button" class="mg-btn small" onclick={() => (relock('scores'), (page = null))}><LockKeyhole size={14} /> Lock again</button>
		</div>
		<div class="ab sc-body sc-read" bind:this={body}>{@html page.html}</div>
	{:else}
		<div class="ab">
			<section class="ab-box sc-lock">
				<h2><LockKeyhole size={13} /> Opens with a password</h2>
				<p>
					This page draws on a thesis that is under embargo, so it opens with a password. Ask the {LAB.name} for it:
					<a class="mg-link" href="mailto:{LAB.email}?subject=MARGIE%20scores%20page">{LAB.email}</a>.
				</p>
				<form class="sc-form" onsubmit={open}>
					<label class="sc-label" for="sc-pw">Password</label>
					<input id="sc-pw" class="mg-input" type="password" autocomplete="off" bind:value={password} disabled={busy || missing} />
					<button type="submit" class="mg-btn primary small" disabled={!password || busy || missing}>{busy ? 'Opening…' : 'Open'}</button>
				</form>
				{#if error}<p class="sc-error" role="alert">{error}</p>{/if}
				<p class="ab-lab">The four measures and the confidence formula are in the <a class="mg-link" href="/faq#scoring">FAQ</a>, open to everyone.</p>
			</section>
		</div>
	{/if}
</div>

<style>
	.sc-relock {
		display: flex;
		justify-content: flex-end;
	}
	.sc-body {
		-webkit-user-select: none;
		user-select: none;
	}
	.sc-back {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: var(--mg-fs-sm);
	}
	.sc-lock {
		max-width: 640px;
	}
	.sc-lock h2 {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	.sc-form {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}
	.sc-label {
		font-weight: 600;
	}
	.sc-form input {
		flex: 1;
		min-width: 180px;
	}
	.sc-error {
		color: var(--mg-danger, #c0392b);
	}
	/* Reading size, as on Methods. */
	.sc-read :global(.ab-box) {
		font-size: var(--mg-fs-lg);
		line-height: 1.65;
	}
	.sc-read :global(.ab-table) {
		font-size: var(--mg-fs);
	}
	.sc-read :global(.ab-formula) {
		font-size: var(--mg-fs-sm);
	}
	/* The opened page's content (lib/crisp/locked.ts). */
	.sc-body :global(.sc-cols) {
		font-family: var(--mg-mono);
		font-size: var(--mg-fs-xs);
		overflow-wrap: anywhere;
	}
	.sc-body :global(.sc-pair) {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}
	.sc-body :global(.sc-chan) {
		padding: 10px 12px;
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
	}
	.sc-body :global(.sc-chan h3) {
		margin: 0 0 4px;
	}
	.sc-body :global(.sc-fig) {
		margin: 4px 0;
	}
	.sc-body :global(.sc-fig img) {
		display: block;
		width: 100%;
		max-width: 860px;
		height: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: #fff;
	}
	.sc-body :global(.sc-fig-small img) {
		max-width: 620px;
	}
	.sc-body :global(.sc-fig figcaption) {
		margin-top: 6px;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
	}
	.sc-body :global(.sc-pool summary) {
		cursor: pointer;
		color: var(--mg-accent);
		font-weight: 600;
	}
	.sc-body :global(.sc-pool p) {
		margin-top: 6px;
		color: var(--mg-text-2);
		font-size: var(--mg-fs-xs);
	}
	.sc-body :global(.sc-scroll) {
		overflow-x: auto;
	}
	@media (max-width: 760px) {
		.sc-body :global(.sc-pair) {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
