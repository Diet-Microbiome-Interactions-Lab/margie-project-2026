<script lang="ts">
	import { Lock, Upload } from 'lucide-svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import GenomesPanel from '$lib/workspace/panels/GenomesPanel.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import Fold from '$lib/workspace/motion/Fold.svelte';
	import FoldTitle from '$lib/workspace/motion/FoldTitle.svelte';
	import FoldToggle from '$lib/workspace/motion/FoldToggle.svelte';
	import Resizer from '$lib/workspace/motion/Resizer.svelte';
	import FolderField from './FolderField.svelte';
	import WorkingFolderSetup from './WorkingFolderSetup.svelte';

	/**
	 * Genomes, on Analyze, as Install's boxes: the folders a run uses (on a cluster the working folder
	 * first, then the genomes', the results', the databases' and the tools'; the same settings Settings
	 * shows) and the genome table (GenomesPanel), folded until opened. On a cluster with no working
	 * folder yet, the box opens on its setup (WorkingFolderSetup). FASTA files dropped anywhere on the
	 * box are added; an empty folder shows a large place to drop them.
	 */
	let { foldId }: { foldId: string } = $props();
	const described = $derived(ws.genomes.filter((g) => g.domain && g.domain !== 'Unknown' && g.genetic_code).length);
	const gtdbtkOn = $derived(ws.setting('RUN_GTDBTK') === '1');
	/** How tall the table may grow before it scrolls: 420 px, or as dragged at its bottom edge. */
	const TABLE_H = 'genomes:table-height';
	const tableHeight = $derived(ui.size(TABLE_H, 420));

	let fileInput = $state<HTMLInputElement>();
	let dragging = $state(0);
	let adding = $state(false);

	/** On a cluster, the working folder comes first: the genomes, results and databases folders go in it. */
	const needsWorking = $derived(backend.cluster && (ws.configMissing || (!!ws.firstSetup && !ws.firstSetup.working_folder)));
	$effect(() => {
		if (needsWorking && ui.isFolded(foldId, true)) ui.toggleFold(foldId, true);
	});
	/** On the cluster, files go into its genomes folder, so there must be one. */
	const canAdd = $derived(!backend.cluster || (!needsWorking && !!ws.genomeFolder));

	// ------------------------------------------------ the folders a run uses
	const folder = $derived(ws.genomeFolder || ws.setting('USER_INPUT_DIR'));
	const output = $derived(ws.setting('OUTPUT_ROOT') || ws.resultRoots.outputRoot);
	const working = $derived(ws.setting('margie_sb.working_folder'));
	/** The databases folder: as set, or margie-databases in the working folder. */
	const stores = $derived(ws.setting('margie_sb.stores_root'));
	const storesShown = $derived(stores || (working ? `${working.replace(/\/+$/, '')}/margie-databases` : ''));
	const containers = $derived(ws.setting('margie_sb.sif_path'));
	const references = $derived(ws.setting('margie_sb.db_root'));
	/** A folder in the working folder, as it would be named there. */
	const inWorking = (name: string) => (working ? `${working.replace(/\/+$/, '')}/${name}` : `/scratch/cluster/you/margie/${name}`);
	/** The folders' last names for the one-line summary; the whole path shows on hover. */
	const last = (p: string) => p.replace(/\/+$/, '').split('/').pop() || p;
	/** The folder fields: closed under the folders' line, open while no genomes folder is set. */
	let foldersOpen = $state(false);
	const showFolders = $derived(foldersOpen || !folder);

	/** The head's one line: how many genomes, how many are chosen, and who calls their genes. */
	const summary = $derived.by(() => {
		const n = ws.genomes.length;
		if (needsWorking) return 'set up the working folder first';
		if (!n) return folder ? 'none in the folder yet' : 'set the genomes folder first';
		const parts = [`${n} genome${n === 1 ? '' : 's'}`];
		const chosen = ws.selectedGenomes.length;
		if (chosen < n) parts.push(`${chosen} chosen`);
		if (!gtdbtkOn && described < n) parts.push(`${n - described} go to Prodigal (domain or genetic code unknown)`);
		return parts.join(' | ');
	});

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
	const target = $derived(backend.cluster && folder ? ` to ${last(folder)}` : '');
</script>

<!-- The genomes: folded to its head until opened; files dropped anywhere on it are added. -->
<section
	class="mg-card gb-board"
	data-shade="genomes"
	id="genomes"
	class:over={dragging > 0 && canAdd}
	aria-labelledby="gb-title"
	ondragenter={(e) => {
		e.preventDefault();
		dragging++;
	}}
	ondragleave={() => (dragging = Math.max(0, dragging - 1))}
	ondragover={(e) => e.preventDefault()}
	ondrop={drop}
>
	<header class="mg-card-head">
		<FoldTitle id={foldId} closed headingId="gb-title">Genomes</FoldTitle>
		<span class="mg-note">{summary}</span>
		<span class="mg-grow"></span>
		{#if canAdd}
			<button type="button" class="mg-link quiet" disabled={adding} onclick={() => fileInput?.click()}>{adding ? (backend.cluster ? 'Copying…' : 'Adding…') : 'Add files'}</button>
		{/if}
		<FoldToggle id={foldId} closed />
	</header>

	<Fold id={foldId} closed>
		<div class="gb-body">
			{#if needsWorking}
				<WorkingFolderSetup />
			{:else}
			<!-- Where genomes come from and results go: one line, the fields behind Change folders. -->
			<div class="gb-where">
				<span>
					{#if backend.cluster}Working folder <b class="mg-mono" title={working}>{working ? last(working) : 'margie'}</b>{' | '}genomes from{:else}From{/if}
					<b class="mg-mono" title={folder}>{folder ? last(folder) : 'no folder yet'}</b> | results to
					<b class="mg-mono" title={output}>{output ? last(output) : 'your home folder'}</b>{#if backend.cluster}{' | '}databases in
						<b class="mg-mono" title={storesShown}>{storesShown ? last(storesShown) : 'margie-databases'}</b>{/if}
				</span>
				{#if folder}<button type="button" class="mg-link quiet" aria-expanded={foldersOpen} onclick={() => (foldersOpen = !foldersOpen)}>{foldersOpen ? 'Done' : 'Change folders'}</button>{/if}
			</div>
			{#if showFolders}
				<div class="gb-folders">
					{#if backend.cluster}
						<FolderField label="MARGIE working folder" key="margie_sb.working_folder" value={working} placeholder="/scratch/cluster/you/margie">
							{#snippet help()}
								<p>
									MARGIE's own folder on the cluster. margie-input (genomes), margie-output (results) and margie-databases (MARGIE's
									databases) go in it, and sif and reference-databases/db when your account cannot read your group's containers and reference databases.
								</p>
								<p>
									A new path here moves the folders that sit in the working folder with it; a folder you set yourself stays where it is. The
									containers and reference databases stay where they are set up, and files stay in the old folder.
								</p>
							{/snippet}
						</FolderField>
					{/if}
					<FolderField label="Genomes folder" key="USER_INPUT_DIR" value={folder} placeholder={backend.cluster ? inWorking('margie-input') : '/path/to/genomes'} />
					<FolderField label="Results folder" key="OUTPUT_ROOT" value={output} placeholder={backend.cluster ? inWorking('margie-output') : '/path/to/results'} />
					{#if backend.cluster}
						<FolderField
							label="MARGIE databases"
							key="margie_sb.stores_root"
							value={stores}
							placeholder={working ? `${working.replace(/\/+$/, '')}/margie-databases` : '/scratch/cluster/you/margie/margie-databases'}
						>
							{#snippet help()}
								<p>
									The databases MARGIE builds from your runs and adds to with each genome: the MARGIE database (SQLite: results, cached tool
									outputs and job history), the operon reference, the fingerprint databases and the genome pool. Left empty, MARGIE makes
									margie-databases in the working folder. You can back them up to depot from <a class="mg-link" href={uiBase.to('/settings#databases')}
										>Settings</a
									>; the reference databases the annotation tools search (Pfam, KEGG, COG and the others) are set up on Install.
								</p>
								<p>
									The first run sets them up, as a short SLURM job with its progress shown here: it copies the lab's base databases from the
									group's folder on depot, or, where your account reads no base, makes new ones (MARGIE's starter operon reference, the others
									empty). Fresh, empty ones can also be set up in <a class="mg-link" href={uiBase.to('/settings#databases')}>Settings → Databases</a>.
								</p>
								<p>
									Scoring compares each genome with what the SQLite database, the operon reference and the fingerprint databases already hold.
									Starting from the base databases gives it reference genomes to compare with from the first run, so that is the recommended
									start.
								</p>
							{/snippet}
						</FolderField>
						<FolderField label="Containers folder (sif)" key="margie_sb.sif_path" value={containers} placeholder={inWorking('sif')}>
							{#snippet help()}
								<p>
									The Apptainer containers (.sif) the tools run in. MARGIE uses your group's containers folder when your account can read it,
									else sif in the working folder, where <a class="mg-link" href={uiBase.to('/install')}>Install</a> builds or copies them.
								</p>
							{/snippet}
						</FolderField>
						<FolderField label="Reference databases folder" key="margie_sb.db_root" value={references} placeholder={inWorking('reference-databases/db')}>
							{#snippet help()}
								<p>
									The reference databases the annotation tools search (Pfam, KEGG, COG, eggNOG, InterPro, GTDB-Tk's and the others), one
									folder per tool. MARGIE uses your group's when your account can read them, else reference-databases/db in the working folder, where
									<a class="mg-link" href={uiBase.to('/install')}>Install</a> downloads them.
								</p>
								<p>
									They take many hours to set up. Once they are, back them up, ideally in your group's shared space where the whole group can
									use them, and point this setting there. These are not MARGIE's own databases (margie-databases), which grow with your runs.
								</p>
							{/snippet}
						</FolderField>
					{/if}
				</div>
				<p class="gb-note mg-explain">
					{backend.cluster
						? "The working folder holds the genomes, results and MARGIE's databases folders unless you point them elsewhere; the containers and reference databases are the tools'. Each ? says more."
						: 'Genomes are read from the first folder and results written to the second.'}
				</p>
			{/if}

			{#if ws.genomes.length}
				<div class="gb-frame" style="--gb-h: {tableHeight}px">
					<div class="gb-table"><GenomesPanel bare addRow={false} /></div>
					<Resizer id={TABLE_H} fallback={420} min={160} max={2400} edge="bottom" label="Drag to make the genome table taller or shorter" />
				</div>
				{#if canAdd}
					<p class="gb-hint">
						<Upload size={13} />
						<span
							>Drop FASTA files (.fna, .fa, .fasta) anywhere on this box to add them{target}, or <button
								type="button"
								class="mg-link"
								disabled={adding}
								onclick={() => fileInput?.click()}>select them</button
							>.</span
						>
					</p>
				{/if}
			{:else}
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
						<Lock size={20} /><b>Set the genomes folder first</b><span>Change folders, above, to choose where genomes are read from.</span>
					{:else if adding}
						<span class="spin" aria-hidden="true"></span><b>{backend.cluster ? 'Copying to the cluster…' : 'Adding…'}</b>
					{:else}
						<Upload size={20} /><b>Drop genome FASTA files here</b><span>or <u>select them</u> | .fna, .fa, .fasta{target ? ` | copied${target}` : ''}</span>
					{/if}
				</button>
			{/if}
			{/if}
		</div>
	</Fold>

	{#if dragging > 0 && canAdd}
		<div class="gb-overlay" aria-hidden="true"><Upload size={18} /> Drop to add them{target}</div>
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
		position: relative;
		color: var(--mg-text);
		accent-color: var(--mg-accent);
	}
	.gb-board :global(.mg-card-head) {
		flex-wrap: wrap;
		row-gap: 6px;
	}
	.gb-body {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: var(--cr-pad, 16px 18px);
	}
	.gb-where {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
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

	/* ---- files dragged over the box: an outline and one line saying where they go ---- */
	.gb-board.over {
		border-color: var(--mg-accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--mg-accent) 25%, transparent);
	}
	.gb-overlay {
		position: absolute;
		inset: 6px;
		z-index: 5;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		border: 2px dashed var(--mg-accent);
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-accent) 8%, var(--mg-surface));
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: var(--mg-fs-sm);
		font-weight: 600;
		pointer-events: none;
	}

	/* ---- the folders, side by side ---- */
	.gb-folders {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	/* ---- no genomes yet: a large place to drop them ---- */
	.gb-drop {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		min-height: 140px;
		padding: 20px;
		border: 1.5px dashed var(--mg-border-strong);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		color: var(--mg-text-3);
		font: inherit;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
		transition:
			background-color 160ms,
			border-color 160ms;
	}
	.gb-drop b {
		font-size: var(--mg-fs-md, 1rem);
		font-weight: 600;
		color: var(--mg-text);
	}
	.gb-drop u {
		color: var(--mg-accent-ink);
		text-underline-offset: 2px;
	}
	.gb-drop:hover:not(:disabled) {
		border-color: var(--mg-accent);
		background: color-mix(in srgb, var(--mg-accent) 5%, var(--mg-surface));
	}
	.gb-drop:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: 2px;
	}
	.gb-drop.locked {
		border-color: color-mix(in srgb, var(--mg-warn) 60%, var(--mg-border));
		color: var(--mg-text-3);
		cursor: not-allowed;
	}
	.gb-drop.locked b {
		color: var(--mg-warn);
	}
	.gb-drop.busy {
		cursor: progress;
	}
	.spin {
		width: 18px;
		height: 18px;
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
	.gb-hint {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.gb-hint button {
		font-size: inherit;
	}

	/* ---- the table, in a frame of its own: it scrolls, so the next boxes stay near;
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
		.gb-folders {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
