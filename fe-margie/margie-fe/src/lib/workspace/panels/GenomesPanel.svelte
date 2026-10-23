<script lang="ts">
	import { Check, ChevronDown, CircleHelp, X } from 'lucide-svelte';
	import { formatBytes } from '$lib/api';
	import NestedGenomes from '../NestedGenomes.svelte';
	import Panel from '../Panel.svelte';
	import { backend } from '../backend.svelte';
	import { geneticCode, ws } from '../data.svelte';
	import { ui } from '../ui.svelte';

	/**
	 * Genome table: a toolbar (selection and table tools), then one row per FASTA file with domain
	 * and genetic code as coloured selects and the gene caller it will get.
	 */

	let fileInput = $state<HTMLInputElement>();
	let tableInput = $state<HTMLInputElement>();
	let popover = $state<'paste' | 'fill' | null>(null);
	let pasted = $state('');
	let fillDomain = $state('Bacteria');
	let fillCode = $state('11');
	let dragging = $state(0);

	const toggle = (p: 'paste' | 'fill') => (popover = popover === p ? null : p);
	/*
	 * Drag to choose: press on a row's box and move down or up the table; every row passed
	 * takes the state the first one got. A click or the space bar still ticks one row.
	 */
	let dragTo = $state<boolean | null>(null);
	function dragStart(name: string, e: PointerEvent) {
		if (e.button !== 0) return;
		dragTo = !ws.isGenomeChosen(name);
		ws.setGenomeChosen(name, dragTo);
	}
	function dragOver(name: string) {
		if (dragTo !== null && ws.isGenomeChosen(name) !== dragTo) ws.setGenomeChosen(name, dragTo);
	}
	/** The box itself: the press above already set it, so its own toggle is held back (the keyboard's is not). */
	function boxClick(name: string, e: MouseEvent) {
		e.preventDefault();
		if (e.detail === 0) ws.setGenomeChosen(name, !ws.isGenomeChosen(name));
	}
	/** What the domain and genetic code mean and which to pick: open from the column heads, or by itself in Guided mode. */
	let helpOpen = $state(ui.guided);
	/** The NCBI translation tables offered, with who uses them. */
	const CODE_LABEL: Record<string, string> = { '11': '11 | most bacteria and archaea', '4': '4 | Mycoplasma and kin', '25': '25 | SR1, Gracilibacteria' };
	const CODE_NOTE: Record<string, string> = {
		'': 'Genetic code not set: GTDB-Tk can work it out, or Prodigal calls the genes without RASTtk',
		'11': 'Table 11, the standard code of almost all bacteria and archaea',
		'4': 'Table 4: Mycoplasma, Spiroplasma, Ureaplasma and other Mollicutes, where TGA codes for tryptophan',
		'25': 'Table 25: candidate division SR1 and Gracilibacteria, where TGA codes for glycine'
	};
	const DOMAIN_NOTE: Record<string, string> = {
		'': 'Domain not set: GTDB-Tk can work it out, or Prodigal calls the genes without RASTtk',
		Bacteria: 'Bacteria: RASTtk uses its bacterial gene models',
		Archaea: 'Archaea: RASTtk uses its archaeal gene models'
	};
	/** Sets a genome's genetic code from what was typed: 1 to 100, or empty for unknown. */
	function setCode(name: string, input: HTMLInputElement) {
		const typed = input.value.trim();
		const code = geneticCode(typed);
		if (typed && !code) {
			ui.notify('A genetic code is a whole number from 1 to 100.', 'error');
			input.value = ws.genomes.find((g) => g.name === name)?.genetic_code ?? '';
			return;
		}
		ws.edit(name, 'genetic_code', code);
	}
	/** The table's less frequent tools, in one menu. */
	let moreOpen = $state(false);
	function fromMore(act: () => void) {
		moreOpen = false;
		act();
	}

	function applyPaste() {
		const n = ws.applyRows(pasted);
		ui.notify(n ? `Updated ${n} genome${n === 1 ? '' : 's'}` : 'No rows matched a genome file name', n ? 'ok' : 'error');
		if (n) {
			pasted = '';
			popover = null;
		}
	}

	async function importTable(files: FileList | null) {
		const f = files?.[0];
		if (!f) return;
		const n = ws.applyRows(await f.text());
		ui.notify(n ? `Updated ${n} genome${n === 1 ? '' : 's'} from ${f.name}` : `No rows in ${f.name} matched a genome file name`, n ? 'ok' : 'error');
		if (tableInput) tableInput.value = '';
	}

	function drop(e: DragEvent) {
		e.preventDefault();
		dragging = 0;
		if (e.dataTransfer?.files.length) ws.upload(e.dataTransfer.files);
	}

	/** `bare` omits the panel frame; `addRow: false` omits "Add FASTA files" where the page has a drop zone. */
	let { bare = false, actionsShown = true, addRow = true }: { bare?: boolean; actionsShown?: boolean; addRow?: boolean } = $props();

	/**
	 * Returns a genome's gene caller: Prodigal for all when chosen; otherwise RASTtk if domain and
	 * genetic code are known (or GTDB-Tk will find them), else Prodigal (margie_sb.smk's genome_calls).
	 */
	function caller(g: { domain: string; genetic_code: string }) {
		if (!backend.cluster && (ws.setting('GENE_CALLER') || 'prodigal') === 'prodigal') return 'Prodigal';
		if (g.domain && g.genetic_code) return 'RASTtk';
		return ws.runGtdbtk ? 'GTDB-Tk, then RASTtk' : 'Prodigal';
	}

	let pattern = $state('');

	/** "Only these" replaces the selection, "Add" extends it; both report the match count. */
	function applyPattern(add = false) {
		const text = pattern.trim();
		if (!text) return;
		const n = add ? ws.addGenomesByPattern(text) : ws.onlyGenomesByPattern(text);
		ui.notify(
			n ? `${n} genome${n === 1 ? '' : 's'} matched ${text}` : `Nothing matched ${text}`,
			n ? 'ok' : 'error'
		);
	}

	let switchingGtdbtk = $state(false);

	/** Genomes GTDB-Tk would classify: those missing either field. */
	const needGtdbtk = $derived(ws.genomes.filter((g) => !g.domain || !g.genetic_code).length);

	/**
	 * Toggles RUN_GTDBTK for the whole run; it affects only genomes missing domain or genetic code.
	 * saveSettings reloads the genomes, so ws.runGtdbtk and the caller column update themselves.
	 */
	async function toggleGtdbtk() {
		if (switchingGtdbtk) return;
		switchingGtdbtk = true;
		const on = !ws.runGtdbtk;
		const saved = await ws.saveSettings({ RUN_GTDBTK: on ? '1' : '0' });
		switchingGtdbtk = false;
		if (!saved) return;
		ui.notify(
			on
				? 'GTDB-Tk will classify the genomes with no domain or genetic code.'
				: 'GTDB-Tk is off. Genomes with no domain or genetic code use Prodigal.',
			'ok'
		);
	}
</script>

<svelte:window onpointerup={() => (dragTo = null)} onpointercancel={() => (dragTo = null)} />

{#snippet actions()}
	<!-- On the cluster, domain and code are saved to the account's config, where the run reads them. -->
	{#if ws.genomes.length}
		{#if ws.savingGenomes}<span class="gp-saving">Saving</span>{/if}
		<button
			type="button"
			class="gp-pill"
			aria-pressed={ws.runGtdbtk}
			disabled={switchingGtdbtk}
			title={needGtdbtk
				? `Classify the ${needGtdbtk} genome${needGtdbtk === 1 ? '' : 's'} with no domain or genetic code. ${backend.cluster ? 'Runs on the highmem partition, about 400 GB of memory.' : 'Needs a high-memory machine.'}`
				: 'Every genome already has a domain and genetic code, so GTDB-Tk has nothing to classify.'}
			onclick={toggleGtdbtk}
		>
			{#if ws.runGtdbtk}<Check size={14} />{/if}Work out domain and genetic code with GTDB-Tk
		</button>
		<span class="gp-more">
			<button type="button" class="gp-pill" aria-expanded={moreOpen} aria-haspopup="menu" onclick={() => (moreOpen = !moreOpen)}>More<ChevronDown size={13} /></button>
			{#if moreOpen}
				<button type="button" class="gp-scrim" aria-label="Close the menu" onclick={() => (moreOpen = false)}></button>
				<span class="gp-menu" role="menu">
					<button type="button" role="menuitem" disabled={!pattern.trim()} onclick={() => fromMore(() => applyPattern(true))}>Add name matches to the selection</button>
					<button type="button" role="menuitem" onclick={() => fromMore(() => ws.invertGenomes())}>Invert the selection</button>
					<button type="button" role="menuitem" onclick={() => fromMore(() => toggle('paste'))}>Paste domains and codes</button>
					<button type="button" role="menuitem" onclick={() => fromMore(() => toggle('fill'))}>Fill empty cells</button>
					<button type="button" role="menuitem" onclick={() => fromMore(() => tableInput?.click())}>Import a table</button>
				</span>
			{/if}
		</span>
	{/if}
{/snippet}

<!-- Shared body: inside the board's Panel, or bare inside the Analyze step. -->
{#snippet picker()}
		<!-- Selects which genomes a run annotates; all are selected by default. -->
		<div class="pick">
			<label class="pick-all">
				<input
					type="checkbox"
					checked={ws.everyGenomeChosen}
					indeterminate={!ws.everyGenomeChosen && ws.selectedGenomes.length > 0}
					onchange={(e) => (e.currentTarget.checked ? ws.chooseAllGenomes() : ws.chooseNoGenomes())}
				/>
				<span>
					{#if ws.everyGenomeChosen}
						All {ws.genomes.length} genomes
					{:else}
						{ws.selectedGenomes.length} of {ws.genomes.length} chosen
					{/if}
				</span>
			</label>

			<form
				class="pick-pattern"
				onsubmit={(e) => {
					e.preventDefault();
					applyPattern();
				}}
			>
				<input
					bind:value={pattern}
					placeholder="a-c, 1-9, GCA*"
					spellcheck="false"
					aria-label="Choose genomes by name"
					title={'Comma-separated. "a" starts with a, "a-c" starts with a to c, "1-9" starts with a digit, "GCA*" matches the whole name.'}
				/>
				<button type="submit" class="gp-seg" disabled={!pattern.trim()} title="Choose only the genomes whose names match">Select</button>
			</form>
		</div>
{/snippet}

{#snippet body()}
	<div
		class="drop"
		class:over={dragging > 0}
		role="region"
		aria-label="Genome files"
		ondragenter={(e) => {
			e.preventDefault();
			dragging++;
		}}
		ondragleave={() => (dragging = Math.max(0, dragging - 1))}
		ondragover={(e) => e.preventDefault()}
		ondrop={drop}
	>
		{#if ws.genomes.length}
			<div class="gp-bar">
				{@render picker()}
				{#if bare && actionsShown}<div class="gp-acts">{@render actions()}</div>{/if}
			</div>
		{/if}
		{#if popover === 'paste'}
			<div class="pop">
				<label class="mg-label" for="paste-rows">Paste rows of file name, domain and genetic code</label>
				<textarea id="paste-rows" class="mg-input mono" rows="4" placeholder={'Ecoli_K12.fna\tBacteria\t11'} bind:value={pasted}></textarea>
				<div class="row-end">
					<button type="button" class="mg-link quiet" onclick={() => (popover = null)}>Cancel</button>
					<button type="button" class="mg-btn small primary" disabled={!pasted.trim()} onclick={applyPaste}>Apply</button>
				</div>
			</div>
		{:else if popover === 'fill'}
			<div class="pop">
				<span class="mg-label">Fill every empty cell with</span>
				<div class="row-end">
					<select class="mg-select" aria-label="Domain" bind:value={fillDomain}>
						<option value="Bacteria">Bacteria</option>
						<option value="Archaea">Archaea</option>
					</select>
					<input class="mg-input gp-fill-code" type="number" min="1" max="100" step="1" list="gp-codes" aria-label="Genetic code (1 to 100)" bind:value={fillCode} />
					<span class="mg-grow"></span>
					<button type="button" class="mg-link quiet" onclick={() => (popover = null)}>Cancel</button>
					<button
						type="button"
						class="mg-btn small primary"
						onclick={() => {
							const code = geneticCode(String(fillCode));
							if (!code) {
								ui.notify('A genetic code is a whole number from 1 to 100.', 'error');
								return;
							}
							ws.fillEmpty(fillDomain, code);
							popover = null;
						}}>Fill</button
					>
				</div>
			</div>
		{/if}

		<NestedGenomes />

		<datalist id="gp-codes">
			{#each Object.entries(CODE_LABEL) as [code, label] (code)}<option value={code}>{label}</option>{/each}
		</datalist>
		{#if ws.genomes.length && helpOpen}
			<div class="gp-explain" role="note">
				<button type="button" class="gp-explain-x" aria-label="Close" onclick={() => (helpOpen = false)}><X size={14} /></button>
				<div>
					<b>Domain</b>
					<p>Bacteria or Archaea: the genome's domain of life. RASTtk needs it to choose its gene models.</p>
				</div>
				<div>
					<b>Genetic code</b>
					<p>
						The NCBI translation table its genes use, a number from 1 to 100. <b>11</b> is the standard code of almost all bacteria and archaea. <b>4</b> is for Mycoplasma,
						Spiroplasma and other Mollicutes, where TGA codes for tryptophan. <b>25</b> is for candidate division SR1 and Gracilibacteria, where TGA
						codes for glycine.
					</p>
				</div>
				<div>
					<b>Which to choose</b>
					<p>
						Known organism: its domain, and code 11 unless it belongs to the groups above. Not sure: leave both Unknown and switch on
						<i>Work out domain and genetic code with GTDB-Tk</i>, which places the genome in the GTDB taxonomy first. Left Unknown without it, the
						genome's genes are called by Prodigal alone, without RASTtk.
					</p>
				</div>
				<div>
					<b>Gene caller</b>
					<p>Follows from the two: RASTtk when both are set; GTDB-Tk then RASTtk when they are Unknown and GTDB-Tk is on; Prodigal otherwise.</p>
				</div>
			</div>
		{/if}
		{#if ws.genomes.length}
			<div class="gtable" class:dragging={dragTo !== null} role="table" aria-label="Genomes">
				<div class="tr th" class:remote={backend.cluster} role="row">
					<span role="columnheader"><span class="vh">Chosen</span></span><span role="columnheader">File</span><span role="columnheader" class="size"
						>Size</span
					><span role="columnheader">Domain<button type="button" class="gp-help" aria-label="What the domain means" aria-expanded={helpOpen} onclick={() => (helpOpen = !helpOpen)}><CircleHelp size={13} /></button></span><span role="columnheader"
						>Genetic code<button type="button" class="gp-help" aria-label="What the genetic code means" aria-expanded={helpOpen} onclick={() => (helpOpen = !helpOpen)}><CircleHelp size={13} /></button></span
					><span role="columnheader" class="via">Gene caller<button type="button" class="gp-help" aria-label="How the gene caller is chosen" aria-expanded={helpOpen} onclick={() => (helpOpen = !helpOpen)}><CircleHelp size={13} /></button></span>{#if !backend.cluster}<span></span>{/if}
				</div>
				{#each ws.genomes as g (g.name)}
					<div class="tr" class:remote={backend.cluster} class:unchosen={!ws.isGenomeChosen(g.name)} role="row" onpointerenter={() => dragOver(g.name)}>
						<span role="cell" class="pickcell" title="Click, or press and drag over other rows" onpointerdown={(e) => dragStart(g.name, e)}>
							<input type="checkbox" aria-label="Annotate {g.name}" checked={ws.isGenomeChosen(g.name)} onclick={(e) => boxClick(g.name, e)} />
						</span>
						<span role="cell" class="file" title={g.name}>{g.name.replace(/\.[^.]+$/, '')}<span class="ext">{g.name.match(/\.[^.]+$/)?.[0] ?? ''}</span></span>
						<span role="cell" class="size">{formatBytes(g.size)}</span>
						<span role="cell">
							<select
								class="gp-badge"
								class:bac={g.domain === 'Bacteria'}
								class:arc={g.domain === 'Archaea'}
								class:unk={!g.domain}
								aria-label="Domain of {g.name}"
								title={DOMAIN_NOTE[g.domain ?? ''] ?? ''}
								value={g.domain} onchange={(e) => ws.edit(g.name, 'domain', e.currentTarget.value)}>
								<option value="">Unknown</option>
								<option value="Bacteria">Bacteria</option>
								<option value="Archaea">Archaea</option>
							</select>
						</span>
						<span role="cell">
							<input
								class="gp-badge gp-code"
								class:unk={!g.genetic_code}
								type="number"
								min="1"
								max="100"
								step="1"
								list="gp-codes"
								placeholder="Unknown"
								aria-label="Genetic code of {g.name}"
								title={CODE_NOTE[g.genetic_code ?? ''] ?? `Translation table ${g.genetic_code}`}
								value={g.genetic_code}
								onchange={(e) => setCode(g.name, e.currentTarget)}
							/>
						</span>
						<span role="cell" class="via" title={caller(g)}>{caller(g)}</span>
						<!-- Cluster files are removed in their folder there, not from here. -->
						{#if !backend.cluster}
							<button type="button" class="gp-x" aria-label="Remove {g.name}" title="Remove" onclick={() => ws.remove(g.name)}>
								<X size={14} />
							</button>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
		{#if backend.cluster}
			<p class="remote-note mg-note" class:first={!ws.genomes.length}>
				{ws.genomeFolder
					? 'Files added, uploaded or dropped here are kept in the input folder.'
					: 'Type the genome folder above, and its FASTA files show here.'}
			</p>
		{/if}

		{#if addRow && (!backend.cluster || ws.genomeFolder)}
			<div class="add" class:first={!ws.genomes.length}>
				<button type="button" class="mg-btn small" onclick={() => fileInput?.click()}>{backend.cluster ? 'Add FASTA files to the cluster' : 'Add FASTA files'}</button>
				<span class="mg-note">{dragging ? 'Drop to add' : 'or drop them here'}</span>
			</div>
		{/if}
	</div>
	<input
		bind:this={fileInput}
		type="file"
		multiple
		accept={backend.cluster ? '.fna,.fa,.fasta' : '.fna,.fa,.fasta,.fsa,.fas'}
		hidden
		onchange={(e) => {
			const files = [...(e.currentTarget.files ?? [])];
			e.currentTarget.value = '';
			ws.upload(files);
		}}
	/>
	<input bind:this={tableInput} type="file" accept=".tsv,.csv,.txt" hidden onchange={(e) => importTable(e.currentTarget.files)} />
{/snippet}

{#if bare}
	{@render body()}
{:else}
	<Panel id="genomes" meta={ws.genomes.length ? String(ws.genomes.length) : ''} {actions}>
		{@render body()}
	</Panel>
{/if}

<style>
	.drop {
		display: flex;
		flex-direction: column;
		flex-grow: 1;
		border-radius: var(--mg-r);
		outline: 1.5px dashed transparent;
		outline-offset: -4px;
		transition: background-color var(--mo-1, 140ms) ease;
	}
	.drop.over {
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
		outline-color: var(--mg-accent);
	}

	/* ---- toolbar: selection on the left, table tools on the right ---- */
	.gp-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 10px 16px;
		padding: 12px 14px;
		border-bottom: 1px solid var(--mg-border);
	}
	.gp-acts {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}
	/* The genetic code: a number from 1 to 100, typed or picked from the suggestions. */
	.gp-badge.gp-code {
		width: 112px;
		padding-right: 10px;
		text-align: left;
		/* A field to type in: the dot stays, the dropdown arrow and the spinner go. */
		background-image: radial-gradient(circle, var(--dot) 3.5px, transparent 4px);
		background-position: 9px 50%;
		-moz-appearance: textfield;
		appearance: textfield;
	}
	.gp-badge.gp-code::-webkit-inner-spin-button,
	.gp-badge.gp-code::-webkit-outer-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}
	/* The suggestions open on a click in the field; no arrow eats into the text. */
	.gp-badge.gp-code::-webkit-calendar-picker-indicator {
		display: none !important;
	}
	.gp-badge.gp-code::placeholder {
		color: inherit;
		opacity: 1;
	}
	.gp-fill-code {
		width: 90px;
	}
	/* What the columns mean: a ? on their heads, and a short panel over the table. */
	.gp-help {
		display: inline-grid;
		place-items: center;
		margin-left: 4px;
		padding: 0;
		border: none;
		background: none;
		color: var(--mg-text-3);
		vertical-align: -2px;
		cursor: pointer;
	}
	.gp-help:hover,
	.gp-help[aria-expanded='true'] {
		color: var(--mg-accent-ink);
	}
	.gp-explain {
		position: relative;
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 14px;
		margin: 10px 14px;
		padding: 12px 34px 12px 14px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 25%, var(--mg-border));
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-accent) 5%, var(--mg-surface));
		font-size: var(--mg-fs-xs);
		line-height: 1.5;
		color: var(--mg-text-2);
	}
	.gp-explain > div > b {
		display: block;
		margin-bottom: 3px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text);
	}
	.gp-explain p {
		margin: 0;
	}
	.gp-explain-x {
		position: absolute;
		top: 8px;
		right: 8px;
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border: none;
		border-radius: 50%;
		background: none;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.gp-explain-x:hover {
		background: var(--mg-surface-2);
		color: var(--mg-text);
	}
	@media (max-width: 1000px) {
		.gp-explain {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	/* The box's cell takes the press, so a drag can start anywhere in it. */
	.pickcell {
		cursor: pointer;
		touch-action: none;
	}
	.gtable.dragging {
		user-select: none;
		cursor: ns-resize;
	}
	/* More: a small menu under its button. */
	.gp-more {
		position: relative;
	}
	.gp-scrim {
		position: fixed;
		inset: 0;
		z-index: 20;
		border: none;
		background: transparent;
		cursor: default;
	}
	.gp-menu {
		position: absolute;
		top: calc(100% + 4px);
		right: 0;
		z-index: 21;
		display: flex;
		flex-direction: column;
		min-width: 230px;
		padding: 4px;
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.16);
	}
	.gp-menu button {
		padding: 7px 10px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-sm);
		text-align: left;
		cursor: pointer;
	}
	.gp-menu button:hover:not(:disabled) {
		background: var(--mg-surface-2);
	}
	.gp-menu button:disabled {
		color: var(--mg-text-3);
		cursor: not-allowed;
	}
	.gp-saving {
		font-size: var(--mg-fs-xs);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.gp-pill {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 28px;
		padding: 0 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-xs);
		font-weight: 400;
		white-space: nowrap;
		cursor: pointer;
		transition:
			border-color var(--mo-1, 140ms) ease,
			background-color var(--mo-1, 140ms) ease,
			color var(--mo-1, 140ms) ease;
	}
	.gp-pill:hover:not(:disabled) {
		border-color: var(--mg-border-strong);
		color: var(--mg-text);
	}
	.gp-pill[aria-pressed='true'] {
		border-color: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		background: color-mix(in srgb, var(--mg-accent) 7%, var(--mg-surface));
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.gp-pill:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.pick {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px 12px;
	}
	.pick-all {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 28px;
		padding: 0 12px 0 10px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
		font-weight: 400;
		font-variant-numeric: tabular-nums;
		cursor: pointer;
	}
	/* Pattern input and its two actions as one joined pill. */
	.pick-pattern {
		display: inline-flex;
		align-items: stretch;
		height: 28px;
		border: 1px solid var(--mg-border-strong);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		overflow: hidden;
	}
	.pick-pattern:focus-within {
		border-color: var(--mg-accent);
	}
	.pick-pattern input {
		width: 19ch;
		min-width: 0;
		padding: 0 12px;
		border: none;
		background: none;
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-xs);
		outline: none;
	}
	.gp-seg {
		padding: 0 11px;
		border: none;
		border-left: 1px solid var(--mg-border);
		background: none;
		color: var(--mg-accent-ink, var(--mg-accent));
		font: inherit;
		font-size: var(--mg-fs-xs);
		font-weight: 400;
		white-space: nowrap;
		cursor: pointer;
	}
	.gp-seg:hover:not(:disabled) {
		background: color-mix(in srgb, var(--mg-accent) 10%, transparent);
	}
	.gp-seg:disabled {
		color: var(--mg-text-3);
		cursor: default;
	}

	/* ---- paste / fill ---- */
	.pop {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 12px 14px;
		padding: 12px 14px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 5%, var(--mg-surface));
		animation: gp-pop 220ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
	}
	.row-end {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 10px 12px;
	}
	.drop > :global(.nest) {
		margin: 12px 14px 0;
	}

	/* ---- table ---- */
	.gtable {
		display: flex;
		flex-direction: column;
		container-type: inline-size;
	}
	.tr {
		display: grid;
		grid-template-columns: 20px minmax(0, 2.4fr) minmax(0, 0.7fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.2fr) 28px;
		gap: 14px;
		align-items: center;
		min-height: calc(var(--mg-row, 36px) + 6px);
		padding: 0 14px;
		border-top: 1px solid var(--mg-border);
		font-size: var(--mg-fs-sm);
		transition: background-color var(--mo-1, 140ms) ease;
	}
	/* No remove column on the cluster. */
	.tr.remote {
		grid-template-columns: 20px minmax(0, 2.4fr) minmax(0, 0.7fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.2fr);
	}
	.tr {
		border-top-color: var(--cr-rule, var(--mg-border));
	}
	.tr:not(.th):hover {
		background: color-mix(in srgb, var(--mg-accent) 4%, transparent);
	}
	.th {
		position: sticky;
		top: 0;
		z-index: 1;
		min-height: 34px;
		border-top: none;
		border-bottom: 1px solid var(--mg-border);
		background: var(--mg-surface);
		color: var(--cr-t3, var(--mg-text-3));
		font-size: var(--mg-fs-xs);
		font-weight: 400;
	}
	.th .size,
	.th .via {
		color: inherit;
	}
	.th + .tr {
		border-top: none;
	}
	.tr input[type='checkbox'] {
		margin: 0;
		accent-color: var(--mg-accent);
	}
	.file {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.file .ext {
		color: var(--mg-text-3);
	}
	.size {
		padding-right: 12px;
		text-align: right;
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-2);
	}
	.via {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--mg-text-2);
	}
	/* Deselected rows stay listed and editable. */
	.tr.unchosen .file,
	.tr.unchosen .size,
	.tr.unchosen .via {
		opacity: 0.45;
	}
	/* Domain and genetic code as outlined fields with a domain colour dot; unknown uses the warning colour. */
	.gp-badge {
		--dot: transparent;
		appearance: none;
		-webkit-appearance: none;
		max-width: 100%;
		height: 26px;
		padding: 0 24px 0 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background-color: var(--mg-surface);
		background-image:
			radial-gradient(circle, var(--dot) 3.5px, transparent 4px),
			linear-gradient(45deg, transparent 50%, var(--mg-text-3) 50%),
			linear-gradient(135deg, var(--mg-text-3) 50%, transparent 50%);
		background-position:
			9px 50%,
			calc(100% - 13px) 55%,
			calc(100% - 9px) 55%;
		background-size:
			8px 8px,
			4px 4px,
			4px 4px;
		background-repeat: no-repeat;
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-xs);
		cursor: pointer;
		transition: border-color var(--mo-1, 140ms) ease;
	}
	.gp-badge:hover {
		border-color: var(--mg-border-strong);
	}
	.gp-badge:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: 1px;
	}
	.gp-badge.bac,
	.gp-badge.arc,
	.gp-badge.unk {
		padding-left: 22px;
	}
	.gp-badge.bac {
		--dot: var(--mg-accent);
	}
	.gp-badge.arc {
		--dot: var(--mg-tier-0);
	}
	.gp-badge.unk {
		--dot: var(--mg-warn);
		border-color: color-mix(in srgb, var(--mg-warn) 45%, var(--mg-border));
		color: var(--mg-warn);
	}
	.gp-badge option {
		background: var(--mg-surface);
		color: var(--mg-text);
	}
	.gp-x {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border: 1px solid transparent;
		border-radius: 50%;
		background: none;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.gp-x:hover {
		border-color: color-mix(in srgb, var(--mg-danger) 45%, var(--mg-border));
		background: color-mix(in srgb, var(--mg-danger) 10%, transparent);
		color: var(--mg-danger);
	}
	/* Narrow: file name and the two selects only. */
	@container (max-width: 560px) {
		.tr {
			grid-template-columns: 20px minmax(0, 1.4fr) minmax(0, 1.1fr) minmax(0, 0.8fr) 26px;
			gap: 8px;
			padding: 0 10px;
		}
		.tr.remote {
			grid-template-columns: 20px minmax(0, 1.4fr) minmax(0, 1.1fr) minmax(0, 0.8fr);
		}
		.tr .size,
		.tr .via {
			display: none;
		}
		.gp-badge {
			padding-left: 9px;
			padding-right: 20px;
		}
	}
	/* Visually hidden, kept for screen readers. */
	.vh {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
	.add {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 14px 14px;
		border-top: 1px solid var(--mg-border);
	}
	.remote-note {
		margin: 0;
		padding: 10px 14px 12px;
		border-top: 1px solid var(--mg-border);
	}
	.remote-note.first,
	.add.first {
		border-top: none;
	}

	@keyframes gp-pop {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
	:global([data-motion='off']) .drop,
	:global([data-motion='off']) .drop * {
		animation: none !important;
		transition: none !important;
	}
</style>
