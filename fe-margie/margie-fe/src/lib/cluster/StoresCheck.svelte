<script lang="ts">
	import { onMount } from 'svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import ProgressBar from '$lib/workspace/ProgressBar.svelte';
	import CopyPath from '$lib/workspace/blocks/CopyPath.svelte';

	/**
	 * Install's check of your databases: for each, whether it is in your working folder already, a
	 * copy of your own was found there (used as is, api/services/user_stores.own_copy), or it still
	 * needs copying from the group's folder; and the setup itself, with its progress and Stop.
	 */

	onMount(() => {
		ws.loadStores();
	});

	const st = $derived(ws.stores);
	const op = $derived(ws.storesOp);
	const copying = $derived(ws.storesBusy && op?.op === 'setup');
	let looking = $state(false);

	async function again() {
		looking = true;
		await ws.loadStores();
		looking = false;
	}

	type Row = { tone: 'ok' | 'mine' | 'wait' | 'need'; word: string; path: string; note: string };
	function row(s: NonNullable<typeof st>['stores'][number]): Row {
		if (s.version) return { tone: 'ok', word: `In your working folder (v${s.version})`, path: s.path, note: '' };
		if (s.found?.ready) return { tone: 'mine', word: 'Your copy is there', path: s.found.path, note: 'Used where it is when you set up; nothing is copied.' };
		if (s.found) return { tone: 'wait', word: 'Your copy is there, not ready', path: s.found.path, note: `It is ${s.found.note}.` };
		return { tone: 'need', word: 'Needs copying', path: s.base, note: s.base ? 'From the group’s folder, once.' : 'Starts empty: no group copy was found.' };
	}
</script>

{#if st}
	<div class="sc">
		<div class="sc-root">
			<span class="mg-note">Working folder</span>
			<span class="mg-mono sc-path" title={st.root}><span dir="ltr">{st.root}</span></span>
			<CopyPath path={st.root} />
			<span class="mg-grow"></span>
			<button type="button" class="mg-link quiet" disabled={looking} onclick={again}>{looking ? 'Looking…' : 'Look again'}</button>
		</div>
		<ul class="sc-list">
			{#each st.stores as s (s.id)}
				{@const r = row(s)}
				<li class="sc-row">
					<b class="sc-name">{s.label}</b>
					<span class="sc-chip {r.tone}">{r.word}</span>
					<span class="sc-where">
						{#if r.path}<span class="mg-mono sc-path" title={r.path}><span dir="ltr">{r.path}</span></span><CopyPath path={r.path} />{/if}
						{#if r.note}<span class="mg-note">{r.note}</span>{/if}
					</span>
				</li>
			{/each}
		</ul>
		{#if copying && op}
			<ProgressBar
				percent={op.percent}
				state={op.state}
				label={op.state === 'queued' ? 'Waiting for a SLURM slot' : `Setting up${op.label && !['Starting', 'Finished'].includes(op.label) ? `: ${op.label}` : ''}`}
				detail={op.job ? `SLURM job ${op.job}` : ''}
				log={[...(op.log ?? []), ...(op.slurm_out ?? [])]}
				onstop={() => ws.stopStores()}
			/>
		{:else if !st.ready}
			<div class="sc-go">
				<span class="mg-note">
					Copy a database into the working folder yourself and MARGIE uses it (Look again once the copy has finished); the rest are copied
					when you set up, or before your first run.
				</span>
				<button type="button" class="mg-btn small primary" disabled={ws.storesBusy} onclick={() => ws.setupStores()}>Set them up now</button>
			</div>
		{/if}
	</div>
{:else}
	<p class="mg-note sc-wait">Reading your working folder…</p>
{/if}

<style>
	.sc {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 0 var(--mg-pad) var(--mg-pad);
	}
	.sc-wait {
		padding: 0 var(--mg-pad) var(--mg-pad);
	}
	.sc-root {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		font-size: var(--mg-fs-sm);
	}
	.sc-root > .mg-note {
		flex: none;
		white-space: nowrap;
	}
	.sc-path {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		direction: rtl;
		text-align: left;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.sc-list {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	@media (max-width: 760px) {
		.sc-list {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.sc-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 6px 10px;
		min-width: 0;
		padding: 10px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
	}
	.sc-name {
		min-width: 0;
		font-weight: 600;
	}
	/* The path (its end in view) with its copy button, and the note under both. */
	.sc-where {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 2px 6px;
		min-width: 0;
	}
	.sc-where .mg-note {
		grid-column: 1 / -1;
		font-size: var(--mg-fs-xs);
	}
	.sc-chip {
		padding: 1px 8px;
		border-radius: 999px;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		white-space: nowrap;
	}
	.sc-chip.ok {
		background: color-mix(in srgb, var(--mg-ok) 15%, transparent);
		color: var(--mg-ok);
	}
	.sc-chip.mine {
		background: color-mix(in srgb, var(--mg-accent) 15%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.sc-chip.wait,
	.sc-chip.need {
		background: color-mix(in srgb, var(--mg-warn) 14%, transparent);
		color: var(--mg-warn);
	}
	.sc-go {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px 16px;
	}
	.sc-go .mg-note {
		flex: 1 1 40ch;
		font-size: var(--mg-fs-xs);
	}
</style>
