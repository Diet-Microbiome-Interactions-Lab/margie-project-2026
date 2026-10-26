<script lang="ts">
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { pathComplete } from '$lib/workspace/path-complete';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * First-time setup on a cluster: the working folder before anything else. MARGIE suggests margie
	 * in the account's scratch and makes it in one click, or takes another path; margie-input,
	 * margie-output and margie-databases go in it, and sif and reference-databases/db when the account cannot read the
	 * group's containers and reference databases. Shown on Analyze and Settings until it is set.
	 */
	let { headingLevel = 3 }: { headingLevel?: 2 | 3 } = $props();

	$effect(() => {
		if (!ws.firstSetup) void ws.loadSetup();
	});
	const st = $derived(ws.firstSetup);
	let other = $state(false);
	let path = $state('');
	let busy = $state(false);
	const at = $derived(((other && path.trim()) || st?.default || '/scratch/<cluster>/<you>/margie').replace(/\/+$/, ''));
	/** The group's containers and reference databases, where this account reads them. */
	const groupSif = $derived(!!st?.group.sif_path.readable);
	const groupDb = $derived(!!st?.group.db_root.readable);
	const noGroup = $derived(!!st && !st.group.sif_path.path && !st.group.db_root.path);

	async function create() {
		if (busy || (other && !path.trim())) return;
		busy = true;
		await ws.setWorkingFolder(other ? path.trim() : '');
		busy = false;
	}
</script>

<section class="wf" aria-labelledby="wf-title">
	<svelte:element this={`h${headingLevel}`} id="wf-title" class="wf-title">Set up your working folder first</svelte:element>
	<p class="wf-lead">
		MARGIE keeps what your runs need in one working folder on the cluster. Setting it up makes these folders in it; you can point any of
		them elsewhere later, in Settings → Folders.
	</p>

	<ul class="wf-tree" aria-label="The working folder">
		<li class="wf-root mg-mono" title={at}>{at}/</li>
		<li><b class="mg-mono">margie-input</b><span>the genomes you add</span></li>
		<li><b class="mg-mono">margie-output</b><span>the results of each run</span></li>
		<li><b class="mg-mono">margie-databases</b><span>MARGIE's databases: the first run copies your group's base databases here, or starts new ones</span></li>
		{#if !groupSif}<li><b class="mg-mono">sif</b><span>the containers the tools run in, built or copied on Install</span></li>{/if}
		{#if !groupDb}<li><b class="mg-mono">reference-databases/db</b><span>the reference databases the tools search, downloaded on Install</span></li>{/if}
	</ul>
	{#if st && (groupSif || groupDb)}
		<p class="mg-note">
			Your group's {groupSif && groupDb ? 'containers and reference databases' : groupSif ? 'containers' : 'reference databases'} are read where they
			are ({[groupSif ? st.group.sif_path.path : '', groupDb ? st.group.db_root.path : ''].filter(Boolean).join(' | ')}).
		</p>
	{/if}

	<div class="wf-pick" role="radiogroup" aria-label="Where the working folder goes">
		<label class="wf-opt">
			<input type="radio" name="wf-where" checked={!other} onchange={() => (other = false)} />
			<span>Make it in your scratch <span class="mg-mono wf-path">{st?.default || '/scratch/<cluster>/<you>/margie'}</span> (recommended)</span>
		</label>
		<label class="wf-opt">
			<input type="radio" name="wf-where" checked={other} onchange={() => (other = true)} />
			<span>Use another folder</span>
		</label>
		{#if other}
			<input
				class="mg-input mg-mono wf-input"
				bind:value={path}
				placeholder="/scratch/cluster/you/margie"
				spellcheck="false"
				autocomplete="off"
				aria-label="Working folder"
				use:pathComplete={{ dirs: true }}
				onkeydown={(e) => e.key === 'Enter' && create()}
			/>
		{/if}
	</div>

	<div class="wf-go">
		<button type="button" class="mg-btn primary" disabled={busy || !st || (other && !path.trim())} onclick={create}>
			{busy ? 'Setting it up…' : 'Set up the working folder'}
		</button>
		{#if ui.guided}<a class="mg-link" href={uiBase.to('/setup')}>How to set up MARGIE</a>{/if}
	</div>

	{#if st && (!groupSif || !groupDb)}
		<div class="wf-warn" role="note">
			<b>Containers and reference databases take many hours to set up.</b>
			<span>
				Install builds or downloads them into sif and reference-databases/db here, since {noGroup
					? 'no group folder is set'
					: "your account cannot read your group's default folder"}. Once they are set up, back them up, ideally in your group's shared
				space (a depot folder, for example), where the whole group can use them; then set that folder in Settings → Folders.
			</span>
		</div>
	{/if}
	{#if st}
		<p class="mg-note">
			margie-build, the recipes for the containers and databases:
			{#if st.build.path}found in <span class="mg-mono">{st.build.path}</span>.{:else if st.build.bundled}not on the cluster yet. Install puts
				MARGIE's copy in <span class="mg-mono">{st.build.clone_to}</span> when a build needs it, or give its folder in Settings → Folders.{:else}not on the
				cluster yet. Install clones it into <span class="mg-mono">{st.build.clone_to}</span>, or give its folder in Settings → Folders.{/if}
		</p>
	{/if}
</section>

<style>
	.wf {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 16px 18px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		color: var(--mg-text);
	}
	.wf-title {
		margin: 0;
		font-size: var(--mg-fs-md, 1rem);
		font-weight: 600;
	}
	.wf-lead {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.wf-tree {
		display: flex;
		flex-direction: column;
		gap: 3px;
		margin: 0;
		padding: 10px 12px;
		list-style: none;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		font-size: var(--mg-fs-sm);
	}
	.wf-tree li {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 10px;
		padding-left: 18px;
	}
	.wf-tree li.wf-root {
		padding-left: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}
	.wf-tree b {
		min-width: 13.5em;
		font-weight: 500;
	}
	.wf-tree span {
		color: var(--mg-text-3);
	}
	.wf-pick {
		display: flex;
		flex-direction: column;
		gap: 6px;
		font-size: var(--mg-fs-sm);
	}
	.wf-opt {
		display: flex;
		align-items: baseline;
		gap: 8px;
		cursor: pointer;
	}
	.wf-opt input {
		accent-color: var(--mg-accent);
	}
	.wf-path {
		overflow-wrap: anywhere;
	}
	.wf-input {
		margin-left: 24px;
		max-width: 560px;
	}
	.wf-go {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 16px;
	}
	.wf-warn {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 10px 12px;
		border: 1px solid color-mix(in srgb, var(--mg-warn) 45%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		font-size: var(--mg-fs-sm);
	}
	.wf-warn span {
		color: var(--mg-text-2);
	}
	.wf p.mg-note {
		margin: 0;
	}
	@media (max-width: 600px) {
		.wf-input {
			margin-left: 0;
		}
		.wf-tree b {
			min-width: 0;
		}
	}
</style>
