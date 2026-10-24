<script lang="ts">
	import { Lock, Upload } from 'lucide-svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import GenomesPanel from '$lib/workspace/panels/GenomesPanel.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import Resizer from '$lib/workspace/motion/Resizer.svelte';
	import FolderField from './FolderField.svelte';

	/**
	 * Genomes, on Analyze: the folders a run uses (the genomes', the results', and on a cluster the
	 * working folder of your databases; the same settings Settings shows), a strip to drop FASTA
	 * files on or pick them from, and the genome table (GenomesPanel), folded until opened.
	 * Files dropped anywhere on the section are added too.
	 */
	/** `step`: its number among Analyze's steps, shown before the title. */
	let { foldId = '', step = 0 }: { foldId?: string; step?: number } = $props();
	const shut = $derived(!!foldId && ui.isFolded(foldId, true));
	const described = $derived(ws.genomes.filter((g) => g.domain && g.domain !== 'Unknown' && g.genetic_code).length);
	/** How tall the table may grow before it scrolls: 420 px, or as dragged at its bottom edge. */
	const TABLE_H = 'genomes:table-height';
	const tableHeight = $derived(ui.size(TABLE_H, 420));

	let fileInput = $state<HTMLInputElement>();
	let dragging = $state(0);
	let adding = $state(false);

	/** On the cluster, files go into its genomes folder, so there must be one. */
	const canAdd = $derived(!backend.cluster || !!ws.genomeFolder);

	// ------------------------------------------------ the folders a run uses
	const folder = $derived(ws.genomeFolder || ws.setting('USER_INPUT_DIR'));
	const output = $derived(ws.setting('OUTPUT_ROOT') || ws.resultRoots.outputRoot);
	const working = $derived(ws.setting('margie_sb.stores_root'));
	/** The folders' last names for the one-line summary; the whole path shows on hover. */
	const last = (p: string) => p.replace(/\/+$/, '').split('/').pop() || p;
	/** The three folder fields: folded under the genomes' title, open while no genomes folder is set. */
	let foldersOpen = $state(false);
	const showFolders = $derived(foldersOpen || !folder);

	// ------------------------------------------------ adding files
	async function add(files: FileList | File[]) {
		if (!files.length || adding) return;
		adding = true;
		await ws.upload(files);
		adding = false;
	}
	function drop(e: DragEvent) {
		// Handled here, so the page-wide drop (GenomeDrop) ignores it.
		e.preventDefault();
		dragging = 0;
		if (canAdd && e.dataTransfer?.files.length) add([...e.dataTransfer.files]);
	}
</script>

<!-- The genomes: folded to one line until opened; files dropped anywhere on it are added. -->
<section
	class="gb-board"
	class:folded={shut}
	class:over={dragging > 0 && canAdd}
	aria-label="Genomes"
	ondragenter={(e) => {
		e.preventDefault();
		dragging++;
	}}
	ondragleave={() => (dragging = Math.max(0, dragging - 1))}
	ondragover={(e) => e.preventDefault()}
	ondrop={drop}
>
	<div class="gb-top">
		{#if step}<span class="gb-step">{step}</span>{/if}
		<h2 class="gb-colhead">Genomes</h2>
		{#if ws.genomes.length}<span class="gb-count">{ws.genomes.length}</span>{/if}
		<!-- Only when it changes the gene caller: without GTDB-Tk, a genome needs both to be called by RASTtk. -->
		{#if ws.genomes.length && ws.setting('RUN_GTDBTK') !== '1' && described < ws.genomes.length}
			<span class="gb-sum">{ws.genomes.length - described} without a domain and genetic code (called by Prodigal)</span>
		{/if}
		<span class="mg-grow"></span>
		{#if canAdd}
			<button type="button" class="mg-link quiet" disabled={adding} onclick={() => fileInput?.click()}>{adding ? (backend.cluster ? 'Copying…' : 'Adding…') : dragging ? 'Drop to add them' : 'Add files'}</button>
		{/if}
		{#if foldId}
			<button type="button" class="mg-link quiet" aria-expanded={!shut} onclick={() => ui.toggleFold(foldId, true)}>{shut ? 'Show' : 'Hide'}</button>
		{/if}
	</div>

	<!-- Where genomes come from and results go: one line, the fields behind Change folders. -->
	<div class="gb-where">
		<span>
			From <b class="mg-mono" title={folder}>{folder ? last(folder) : 'no folder yet'}</b> | results to
			<b class="mg-mono" title={output}>{output ? last(output) : 'your home folder'}</b>{#if backend.cluster}{' | '}databases in
				<b class="mg-mono" title={working}>{working ? last(working) : 'margie-databases'}</b>{/if}
		</span>
		{#if folder}<button type="button" class="mg-link quiet" aria-expanded={foldersOpen} onclick={() => (foldersOpen = !foldersOpen)}>{foldersOpen ? 'Done' : 'Change folders'}</button>{/if}
	</div>
	{#if showFolders}
		<div class="gb-folders" class:three={backend.cluster}>
			<FolderField label="Genomes folder" key="USER_INPUT_DIR" value={folder} placeholder="/path/to/genomes" />
			<FolderField label="Results folder" key="OUTPUT_ROOT" value={output} placeholder="/path/to/results" />
			{#if backend.cluster}
				<FolderField label="MARGIE-generated databases" key="margie_sb.stores_root" value={working} placeholder="/scratch/cluster/you/margie/margie-databases">
					{#snippet help()}
						<p>
							These are not the reference databases the annotation tools search (Pfam, KEGG, COG and the others, set up on Install). They are the
							databases MARGIE builds from your own runs and adds to with every genome: the MARGIE database (SQLite: results, cached tool outputs
							and job history), the operon reference, the fingerprint databases and the genome pool. You can back them up to depot from
							<a class="mg-link" href={uiBase.to('/settings#databases')}>Settings</a>.
						</p>
						<p>
							They live in this working folder on the cluster, and runs need them; change the path here to use another folder. When none are found
							here, the first run copies the lab's base databases from the group's folder on depot and works from those, unless you set up fresh,
							empty ones in <a class="mg-link" href={uiBase.to('/settings#databases')}>Settings → Databases</a>.
						</p>
						<p>
							Scoring compares each genome with what the SQLite database, the operon reference and the fingerprint databases already hold. Starting
							from the base databases gives it reference genomes to compare with from the first run, so that is the recommended start.
						</p>
					{/snippet}
				</FolderField>
			{/if}
		</div>
		<p class="gb-note mg-explain">
			Genomes are read from the first folder and results written to the second.{backend.cluster
				? ' The third holds the databases MARGIE generates from your runs (not the tools\' reference databases); its ? says more.'
				: ''}
		</p>
	{/if}

	{#if !shut}
		<div class="gb-src">
			<button
				type="button"
				class="gb-drop"
				class:locked={!canAdd}
				class:busy={adding}
				disabled={!canAdd || adding}
				title={canAdd ? 'FASTA files (.fna, .fa, .fasta)' : 'Set the genomes folder first'}
				onclick={() => fileInput?.click()}
			>
				{#if !canAdd}
					<Lock size={16} /><span><b>Set the genomes folder first</b></span>
				{:else if adding}
					<span class="spin" aria-hidden="true"></span><span><b>{backend.cluster ? 'Copying to the cluster…' : 'Adding…'}</b></span>
				{:else if dragging}
					<Upload size={16} /><span><b>Drop to add them</b></span>
				{:else}
					<Upload size={16} /><span><b>Drop genome files here</b> or <u>select them</u></span>
				{/if}
			</button>
		</div>
		{#if ws.genomes.length}
			<div class="gb-frame" style="--gb-h: {tableHeight}px">
				<div class="gb-table"><GenomesPanel bare addRow={false} /></div>
				<Resizer id={TABLE_H} fallback={420} min={160} max={2400} edge="bottom" label="Drag to make the genome table taller or shorter" />
			</div>
		{:else if canAdd}
			<p class="gb-empty">No FASTA files in this folder yet.</p>
		{/if}
	{/if}

	<input
		bind:this={fileInput}
		type="file"
		multiple
		accept={backend.cluster ? '.fna,.fa,.fasta' : '.fna,.fa,.fasta,.fsa,.fas'}
		hidden
		onchange={(e) => {
			const files = [...(e.currentTarget.files ?? [])];
			e.currentTarget.value = '';
			add(files);
		}}
	/>
</section>

<style>
	.gb-board {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: calc(var(--mg-pad) * 1.2);
		border: 1px solid var(--cr-card-edge, transparent);
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text);
		accent-color: var(--mg-accent);
	}
	/* Folded: one slim line. */
	.gb-board.folded {
		padding-top: 10px;
		padding-bottom: 10px;
	}
	.gb-where {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
		padding-left: 32px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.gb-where b {
		font-weight: 500;
		color: var(--mg-text);
	}
	.gb-note {
		margin: 0;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.gb-board.over {
		border-color: var(--mg-accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--mg-accent) 25%, transparent);
	}
	.gb-top {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.gb-step {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: var(--mg-fs-xs);
		font-weight: 700;
	}
	/* A small label at the top, as the other steps have. */
	.gb-colhead {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.gb-count {
		font-size: var(--mg-fs-xs);
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-3);
	}

	/* ---- the folders, side by side, then the drop strip ---- */
	.gb-folders {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}
	.gb-folders.three {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.gb-src {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
	}
	.gb-sum {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.gb-drop {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		height: 38px;
		padding: 0 14px;
		border: 1.5px dashed var(--mg-border-strong);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
		transition:
			background-color 160ms,
			border-color 160ms;
	}
	.gb-drop b {
		font-weight: 600;
		color: var(--mg-text);
	}
	.gb-drop u {
		color: var(--mg-accent-ink);
		text-underline-offset: 2px;
	}
	.gb-drop:hover:not(:disabled),
	.over .gb-drop {
		border-color: var(--mg-accent);
		background: color-mix(in srgb, var(--mg-accent) 6%, var(--mg-surface));
	}
	.gb-drop:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: 2px;
	}
	.gb-drop.locked {
		border-color: color-mix(in srgb, var(--mg-warn) 60%, var(--mg-border));
		color: var(--mg-warn);
		cursor: not-allowed;
	}
	.gb-drop.busy {
		cursor: progress;
	}
	.spin {
		width: 14px;
		height: 14px;
		border: 2px solid color-mix(in srgb, var(--mg-accent) 30%, transparent);
		border-top-color: var(--mg-accent);
		border-radius: 50%;
		animation: spin 900ms linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.gb-empty {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-3);
	}

	/* ---- the table, in a frame of its own: it scrolls, so the next steps stay near;
	   its bottom edge drags it taller or shorter ---- */
	.gb-frame {
		position: relative;
		min-width: 0;
	}
	.gb-table {
		min-width: 0;
		max-height: var(--gb-h, 420px);
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		overflow: auto;
	}

	:global([data-motion='off']) .gb-board * {
		animation: none !important;
		transition: none !important;
	}
	@media (max-width: 900px) {
		.gb-folders,
		.gb-folders.three {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
