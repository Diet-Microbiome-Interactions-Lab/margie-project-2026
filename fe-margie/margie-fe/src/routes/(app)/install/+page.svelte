<script lang="ts">
	import { Check, ScrollText } from 'lucide-svelte';
	import InstallBoard from '$lib/crisp/InstallBoard.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { installLock } from '$lib/workspace/install-lock.svelte';
	import LicenceReading from '$lib/workspace/blocks/LicenceReading.svelte';

	/**
	 * Install page: what this computer or cluster account needs before a run. It opens freely; the
	 * first installation, database download or database setup asks for the install statement once
	 * for this place (installLock, InstallGate).
	 */
	$effect(() => {
		if (installLock.place) installLock.check();
	});

	const where = $derived(backend.cluster ? (installLock.place ? `for ${installLock.place}` : 'for this account') : 'on this computer');
</script>

<svelte:head><title>Install | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-setup">
	<div class="cr-head">
		<h1 class="cr-title">Install</h1>
		<p class="cr-lede mg-explain">
			{#if backend.cluster}
				What your cluster account needs before a run: a connection and a SLURM account. Tools and databases are installed by the
				cluster's administrators; the licence terms are accepted on <a class="mg-link" href="/analyze#licence">Analyze</a>, before a first run.
			{:else}
				What this computer needs before a run: a container app, the tools' images and their reference data. Folders and resource limits
				are in <a class="mg-link" href="/settings">Settings</a>.
			{/if}
		</p>
		<span class="cr-meta">{ws.overview ? `${ws.setupReady.ok} of ${ws.setupReady.total} ready` : ''}</span>
	</div>

	<section class="mg-card in-statement" aria-label="The install statement">
		{#if installLock.unlocked}
			<p class="in-line"><Check size={16} strokeWidth={2.5} /> You have typed the install statement {where}; installations go ahead.</p>
		{:else}
			<p class="in-line">
				<ScrollText size={16} /> The first installation, database download or database setup {where} asks you to type the install statement once,
				confirming the tools' licences and MARGIE's terms.
			</p>
		{/if}
		<LicenceReading label="Read the licences" />
	</section>

	<InstallBoard />
</div>

<style>
	.in-statement {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: var(--cr-note-pad, 10px 18px);
	}
	.in-line {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0;
		font-size: var(--mg-fs-sm);
	}
	.in-line :global(svg) {
		flex: 0 0 auto;
		margin-top: 2px;
		color: var(--mg-accent);
	}
</style>
