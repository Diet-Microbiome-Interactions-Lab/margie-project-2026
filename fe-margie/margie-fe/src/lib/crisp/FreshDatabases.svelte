<script lang="ts">
	import { onMount } from 'svelte';
	import { Database, Sparkles } from 'lucide-svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';

	/**
	 * Settings → Databases: what a working folder starts from. By default the lab's prebuilt
	 * databases, copied from the group folder (they are never written to: runs grow the copies);
	 * or, for a new lab, every database made fresh and empty, after a yes. Either way each lands in
	 * its own folder of the working folder:
	 * sqlite/, operon-database/, fingerprint-database/, genome-pool/.
	 */
	onMount(() => {
		if (!ws.stores) ws.loadStores();
	});

	/** The working folder as set now (Settings or Analyze), else as the cluster reports it. */
	const working = $derived(ws.setting('margie_sb.stores_root') || ws.stores?.root || '');
	/** Where the prebuilt databases are: the folder above the base copies' own folders. */
	const prebuilt = $derived.by(() => {
		const base = ws.stores?.stores.find((s) => s.base)?.base ?? '';
		const at = base.indexOf('/margie-generated-databases');
		if (at >= 0) return base.slice(0, at + '/margie-generated-databases'.length);
		const group = ws.setting('margie_sb.shared_root');
		return group ? `${group.replace(/\/$/, '')}/databases/margie-generated-databases` : '';
	});
	const ready = $derived(!!ws.stores?.ready);

	let busy = $state(false);

	async function run(fresh: boolean) {
		busy = true;
		// Asks first (setupStores); its progress shows under Backups (Your databases), and the paths here follow once it is done.
		await ws.setupStores(fresh);
		busy = false;
	}
</script>

<section class="start" aria-labelledby="start-t">
	<h3 id="start-t">Starting databases <span class="mg-note">in {working || 'your databases folder'}</span></h3>
	<div class="pair">
		<!-- The default: the lab's prebuilt databases, copied once. -->
		<div class="box">
			<header><span class="ic" aria-hidden="true"><Database size={15} /></span><b>The lab's prebuilt databases</b><span class="tag">default</span></header>
			<p class="mg-note">
				A first run copies them into your databases folder, each into its own folder, and runs grow the copies. The prebuilt ones stay as
				they are, so every new user starts from the same place.
			</p>
			{#if prebuilt}
				<a class="path mg-mono" href={uiBase.to(`/files?path=${encodeURIComponent(prebuilt)}`)} title="Open in Files">{prebuilt}</a>
			{/if}
			<div class="go">
				<button type="button" class="mg-btn small" disabled={busy || ws.storesBusy || ready} onclick={() => run(false)}>
					{ready ? 'Already set up in this folder' : ws.storesBusy ? 'A copy is under way…' : 'Copy them now'}
				</button>
			</div>
		</div>

		<!-- For a new lab: everything empty, built up from its own genomes. -->
		<div class="box fresh">
			<header><span class="ic" aria-hidden="true"><Sparkles size={15} /></span><b>Fresh databases, for a new lab</b></header>
			<p class="mg-note">
				Every database starts new and empty: the MARGIE database, the operon reference, the fingerprint databases and the genome pool.
				Runs build them up from your own genomes. Your current copies stay where they are.
			</p>
			<div class="go">
				<button type="button" class="mg-btn small" disabled={busy || ws.storesBusy} onclick={() => run(true)}>
					{ws.storesBusy ? 'A copy is under way…' : busy ? 'Starting…' : 'Create fresh databases'}
				</button>
			</div>
		</div>
	</div>
</section>

<style>
	.start {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 4px var(--mg-pad) 12px;
	}
	h3 {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 8px;
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	h3 .mg-note {
		font-weight: 400;
		letter-spacing: 0;
		text-transform: none;
	}
	.pair {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
		align-items: stretch;
	}
	.box {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
		padding: 12px 14px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
	}
	.box.fresh {
		border-style: dashed;
		border-color: color-mix(in srgb, var(--mg-warn) 45%, var(--mg-border));
	}
	header {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--mg-fs-sm);
	}
	.ic {
		display: inline-flex;
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.tag {
		padding: 1px 7px;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-ok) 14%, transparent);
		color: var(--mg-ok);
		font-size: var(--mg-fs-xs);
		font-weight: 600;
	}
	.mg-note {
		margin: 0;
	}
	.path {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.go {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		margin-top: auto;
	}
	@media (max-width: 900px) {
		.pair {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
