<script lang="ts">
	import { Check, CircleHelp, KeyRound, Lock, LockOpen } from 'lucide-svelte';
	import { sharedColumns } from '$lib/workspace/even';
	import Switch from '$lib/workspace/Switch.svelte';
	import Fold from '$lib/workspace/motion/Fold.svelte';
	import FoldTitle from '$lib/workspace/motion/FoldTitle.svelte';
	import FoldToggle from '$lib/workspace/motion/FoldToggle.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws, type Depth } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * Analyze's boxes after the genomes, as Install's: gene calling (QUAST, GTDB-Tk, then RASTtk or
	 * Prodigal: phases 1 to 3) and the annotation tools by phase. Each box is locked with its saved
	 * choice, the recommended one until changed: Unlock opens a draft, Save keeps it for the next runs
	 * (with the account on the website) and locks the box again, Cancel drops it. A run uses the saved
	 * choice. Short titles; what each does shows in Guided mode or under a box's ?.
	 */

	let help = $state<Record<string, boolean>>({});
	// Both boxes fold away until opened; their heads say what is chosen.
	const CALLING = 'analyze:calling';
	const TOOLS = 'analyze:tools';
	const open = (id: string) => {
		if (ui.isFolded(id, true)) ui.toggleFold(id, true);
	};

	// ------------------------------------------------ gene calling
	type Calling = { quast: boolean; gtdbtk: boolean; caller: string };
	const savedGtdbtk = $derived(ws.setting('RUN_GTDBTK') === '1');
	const savedCaller = $derived(ws.setting('GENE_CALLER') || 'prodigal');
	let callingDraft = $state<Calling | null>(null);
	const calling = $derived<Calling>(callingDraft ?? { quast: ws.quast, gtdbtk: savedGtdbtk, caller: savedCaller });
	/** Recommended: GTDB-Tk works out each genome's domain and genetic code, so RASTtk calls each genome; QUAST off. */
	const callingRecommended = $derived(calling.gtdbtk && !calling.quast);
	/** RASTtk needs a known domain and genetic code: from the genome table, or from GTDB-Tk. */
	const known = $derived(ws.genomes.filter((g) => g.domain && g.domain !== 'Unknown' && g.genetic_code).length);
	const all = $derived(ws.genomes.length);
	/** On the cluster each genome gets RASTtk when both are known (or GTDB-Tk runs), Prodigal otherwise. */
	const byRast = $derived(calling.gtdbtk ? all : known);
	const quast = $derived(ws.tools.find((t) => t.name === 'quast'));
	// GTDB-Tk needs its own image and reference tree.
	const gtdbtkMissing = $derived(
		[ws.images.find((r) => r.name === 'gtdbtk'), ws.databases.find((r) => r.name === 'gtdbtk')].some((r) => r && r.status !== 'ok')
	);
	/** Before any genome is added: RASTtk with GTDB-Tk on (it gives each genome both), else per genome. */
	const defaultCaller = $derived(calling.gtdbtk ? 'rasttk' : '');
	const callers = $derived(
		backend.cluster
			? all
				? byRast === all
					? `RASTtk for all ${all}`
					: byRast
						? `RASTtk ${byRast}, Prodigal ${all - byRast}`
						: `Prodigal for all ${all}`
				: defaultCaller
					? 'RASTtk'
					: 'RASTtk or Prodigal, per genome'
			: calling.caller === 'rasttk'
				? 'RASTtk'
				: calling.caller === 'prodigal'
					? 'Prodigal'
					: 'RASTtk or Prodigal'
	);
	function unlockCalling() {
		callingDraft = { ...calling };
		open(CALLING);
	}
	let savingCalling = $state(false);
	async function saveCalling() {
		const d = callingDraft;
		if (!d || savingCalling) return;
		const changes: Record<string, string> = {};
		if (d.gtdbtk !== savedGtdbtk) changes.RUN_GTDBTK = d.gtdbtk ? '1' : '0';
		if (!backend.cluster && d.caller !== savedCaller) changes.GENE_CALLER = d.caller;
		savingCalling = true;
		const saved = !Object.keys(changes).length || (await ws.saveSettings(changes));
		savingCalling = false;
		// A failed save keeps the draft, so nothing typed is lost.
		if (!saved) return;
		ws.quast = d.quast;
		callingDraft = null;
		ui.notify('Saved: the next runs use this gene calling.', 'ok');
	}

	// ------------------------------------------------ the tools, by phase
	const PHASE_NAME: Record<number, string> = {
		4: 'Function',
		5: 'Operons',
		6: 'Membrane topology',
		7: 'Envelope',
		8: 'Location',
		9: 'Consolidation',
		10: 'Labeling',
		11: 'Fingerprints',
		12: 'Scoring',
		13: 'Fingerprint database',
		15: 'Gene report'
	};
	const BLURB: Record<string, string> = {
		kegg: 'Pathways, public KOfam data',
		cog: 'COG categories',
		eggnog: 'Orthologous groups',
		uniprot: 'Swiss-Prot matches',
		geneprop: 'Genome Properties',
		pfam: 'Protein families',
		tigrfam: 'TIGRFAM families',
		pgap: 'NCBI PGAP models',
		interpro: 'Member databases',
		dbcan: 'CAZymes',
		merops: 'Peptidases',
		tcdb: 'Transporters',
		deepsig: 'Signal peptides',
		signalp6: 'Signal peptides, v6',
		psortb: 'Cell location',
		phobius: 'Membrane topology',
		tmbed: 'Membrane helices',
		evidence: 'Evidence per gene'
	};
	const groups = $derived.by(() => {
		const by = new Map<number, typeof ws.tools>();
		for (const t of ws.tools) {
			const p = t.phase ?? 99;
			if (t.name === 'quast' || p < 4) continue;
			by.set(p, [...(by.get(p) ?? []), t]);
		}
		return [...by.entries()].sort((a, b) => a[0] - b[0]).map(([p, tools]) => ({ phase: p, tools }));
	});
	let groupsWidth = $state(0);
	const toolCols = $derived(sharedColumns(groups.map((g) => g.tools.length), Math.max(1, Math.floor((groupsWidth + 6) / 196))));
	type Tools = { depth: Depth; custom: string[] };
	let toolsDraft = $state<Tools | null>(null);
	const toolsView = $derived<Tools>(toolsDraft ?? { depth: ws.depth, custom: ws.custom });
	/** The tools shown ticked: the draft's while unlocked, else the saved choice's. */
	const inRun = $derived(new Set(ws.toolsFor(toolsView.depth, toolsView.custom, false)));
	const picked = $derived(groups.reduce((a, g) => a + g.tools.filter((t) => inRun.has(t.name)).length, 0));
	const offered = $derived(groups.reduce((a, g) => a + g.tools.length, 0));
	const locked = $derived(ws.tools.filter((t) => !t.licensed));
	/** What a tool's box says on hover: why it is in every run, or locked, or its licence accepted. */
	const hint = (t: (typeof ws.tools)[number]) =>
		t.required
			? 'Part of every run: labeling and the confidence score read it'
			: !t.licensed
				? `${t.label ?? t.name} is locked until its licence terms are accepted (Licence terms, on Analyze)`
				: t.gated
					? 'Licence accepted'
					: '';

	/** Some tools run every time (the cluster's); then "None" is not a choice. */
	const anyRequired = $derived(ws.tools.some((t) => t.required));
	const DEPTHS = $derived(
		(
			[
				{ value: 'standard', label: 'Recommended' },
				{ value: 'licensed', label: 'All' },
				{ value: 'quick', label: 'None' },
				{ value: 'custom', label: 'Custom' }
			] as { value: Depth; label: string }[]
		).filter((d) => !(anyRequired && d.value === 'quick'))
	);
	$effect(() => {
		if (anyRequired && ws.depth === 'quick') ws.depth = 'standard';
	});
	const depthLabel = $derived(DEPTHS.find((d) => d.value === toolsView.depth)?.label ?? 'Custom');
	function unlockTools() {
		toolsDraft = { depth: ws.depth, custom: [...ws.custom] };
		open(TOOLS);
	}
	/** A tool ticked by hand makes the draft Custom, from what was ticked; a required one stays on. */
	function toggle(name: string) {
		if (!toolsDraft || ws.tools.find((t) => t.name === name)?.required) return;
		const now = [...inRun];
		toolsDraft = { depth: 'custom', custom: now.includes(name) ? now.filter((x) => x !== name) : [...now, name] };
	}
	function saveTools() {
		const d = toolsDraft;
		if (!d) return;
		ws.custom = d.custom;
		ws.depth = d.depth;
		toolsDraft = null;
		ui.notify('Saved: the next runs use these tools.', 'ok');
	}
</script>

{#snippet helpButton(id: string, what: string, foldId: string)}
	{#if !ui.explain && !ui.isFolded(foldId, true)}
		<button type="button" class="rs-help" aria-pressed={!!help[id]} aria-label={what} title={what} onclick={() => (help[id] = !help[id])}>
			<CircleHelp size={15} />
		</button>
	{/if}
{/snippet}

<!-- Locked: the saved choice and Unlock. Unlocked: Cancel and Save. -->
{#snippet lockControls(unlocked: boolean, unlock: () => void, cancel: () => void, save: () => void, busy = false)}
	{#if unlocked}
		<button type="button" class="mg-link quiet" disabled={busy} onclick={cancel}>Cancel</button>
		<button type="button" class="mg-btn small primary rs-save" disabled={busy} onclick={save}>{busy ? 'Saving' : 'Save'}</button>
	{:else}
		<button type="button" class="rs-unlock" title="Unlock to change these settings" onclick={unlock}><Lock size={13} /> Unlock</button>
	{/if}
{/snippet}

{#snippet notice(unlocked: boolean, recommended: boolean, saved: string)}
	<p class="rs-notice" class:open={unlocked}>
		{#if unlocked}
			<LockOpen size={14} />
			<span>Unlocked: change what you need, then <b>Save</b>. Runs use the saved choice until you save.</span>
		{:else if recommended}
			<Lock size={14} />
			<span><b>Recommended settings are applied.</b> Change them only if you know what you are doing.</span>
		{:else}
			<Lock size={14} />
			<span><b>Your saved choice is applied</b>{saved ? `: ${saved}` : ''}. Unlock to change it.</span>
		{/if}
	</p>
{/snippet}

<!-- ------------------------------------------------ gene calling -->
<section class="mg-card rs-card" data-shade="calling" aria-labelledby="rs-calling">
	<header class="mg-card-head">
		<FoldTitle id={CALLING} closed headingId="rs-calling">Gene calling</FoldTitle>
		<span class="mg-note">{callingDraft ? 'Unlocked' : callingRecommended ? 'Recommended' : 'Saved choice'}{callers ? ` | ${callers}` : ''}</span>
		<span class="mg-grow"></span>
		{@render helpButton('calling', 'How gene calling works', CALLING)}
		{@render lockControls(!!callingDraft, unlockCalling, () => (callingDraft = null), saveCalling, savingCalling)}
		<FoldToggle id={CALLING} closed />
	</header>
	<Fold id={CALLING} closed>
		<div class="rs-body" data-help={help.calling ? 'on' : undefined}>
			{@render notice(!!callingDraft, callingRecommended, [calling.gtdbtk ? 'GTDB-Tk on' : 'GTDB-Tk off', calling.quast ? 'QUAST on' : ''].filter(Boolean).join(', '))}
			<ol class="rs-phases" class:locked={!callingDraft} inert={!callingDraft}>
				<li>
					<span class="rs-ph">Phase 1 | Quality</span>
					<div class="rs-row">
						<b>QUAST</b>
						<span class="mg-grow"></span>
						{#if quast}
							<Switch label="Check assembly quality with QUAST" checked={calling.quast} onchange={(on) => callingDraft && (callingDraft = { ...callingDraft, quast: on })} />
						{:else}<span class="mg-note">not offered</span>{/if}
					</div>
					<p class="mg-note mg-explain">Assembly statistics (contigs, N50, length) for each genome. Optional; nothing later depends on it.</p>
				</li>
				<li>
					<span class="rs-ph">Phase 2 | Taxonomy</span>
					<div class="rs-row">
						<b>GTDB-Tk</b>
						<span class="mg-grow"></span>
						<Switch label="Work out domain and genetic code with GTDB-Tk" checked={calling.gtdbtk} onchange={(on) => callingDraft && (callingDraft = { ...callingDraft, gtdbtk: on })} />
					</div>
					{#if calling.gtdbtk && gtdbtkMissing}
						<p class="mg-note warn">Needs its image and reference tree. <a class="mg-link" href={uiBase.to('/install#installed')}>Install</a></p>
					{/if}
					<p class="mg-note mg-explain">
						Places each genome in the GTDB taxonomy, which gives RASTtk its domain and genetic code. Use it when you do not know them. It
						needs a highmem node (about 400 GB) and adds hours; off, the genome table supplies both.
					</p>
				</li>
				<li>
					<span class="rs-ph">Phase 3 | Gene caller</span>
					{#if backend.cluster}
						<div class="rs-split" aria-label="Gene caller by genome">
							{#if all}
								<span class="rs-cell" class:on={byRast > 0}><b>RASTtk</b><span>{byRast} genome{byRast === 1 ? '' : 's'}</span></span>
								<span class="rs-cell" class:on={all - byRast > 0}><b>Prodigal</b><span>{all - byRast} genome{all - byRast === 1 ? '' : 's'}</span></span>
							{:else}
								<span class="rs-cell" class:on={defaultCaller === 'rasttk'}><b>RASTtk</b><span>{defaultCaller ? 'default' : 'domain and code known'}</span></span>
								<span class="rs-cell"><b>Prodigal</b><span>{defaultCaller ? 'not needed' : 'the rest'}</span></span>
							{/if}
						</div>
						{#if !calling.gtdbtk && known < all}
							<p class="mg-note">
								{all - known} with an unknown domain or genetic code go to Prodigal. Fill them in on the genome table or turn on GTDB-Tk
								for RASTtk.
							</p>
						{/if}
					{:else}
						<div class="rs-seg" role="radiogroup" aria-label="Gene caller" style="--k: 3">
							{#each [{ v: 'auto', l: 'Per genome' }, { v: 'rasttk', l: 'RASTtk' }, { v: 'prodigal', l: 'Prodigal' }] as o (o.v)}
								<button type="button" role="radio" aria-checked={calling.caller === o.v} onclick={() => callingDraft && (callingDraft = { ...callingDraft, caller: o.v })}
									>{o.l}</button
								>
							{/each}
						</div>
					{/if}
					<p class="mg-note mg-explain">
						RASTtk is recommended when a genome's domain and genetic code are known (from the table or GTDB-Tk): it calls the genes and
						annotates them too. Prodigal is unsupervised and fast, needs neither, but calls genes only.
					</p>
				</li>
			</ol>
		</div>
	</Fold>
</section>

<!-- ------------------------------------------------ annotation tools -->
<section class="mg-card rs-card" id="tools" data-shade="tools" aria-labelledby="rs-tools">
	<header class="mg-card-head">
		<FoldTitle id={TOOLS} closed headingId="rs-tools">Annotation tools</FoldTitle>
		<span class="mg-note">{toolsDraft ? 'Unlocked' : depthLabel} | {picked} of {offered}</span>
		<span class="mg-grow"></span>
		{@render helpButton('tools', 'What the tools do', TOOLS)}
		{@render lockControls(!!toolsDraft, unlockTools, () => (toolsDraft = null), saveTools)}
		<FoldToggle id={TOOLS} closed />
	</header>
	<Fold id={TOOLS} closed>
		<div class="rs-body" data-help={help.tools ? 'on' : undefined}>
			<div class="rs-notice-row">
				{@render notice(!!toolsDraft, toolsView.depth === 'standard', depthLabel.toLowerCase())}
				{#if toolsDraft}
					<div class="rs-seg" role="radiogroup" aria-label="Which tools" style="--k: {DEPTHS.length}">
						{#each DEPTHS as d (d.value)}
							<button type="button" role="radio" aria-checked={toolsDraft.depth === d.value} onclick={() => toolsDraft && (toolsDraft = { ...toolsDraft, depth: d.value })}
								>{d.label}</button
							>
						{/each}
					</div>
				{/if}
			</div>
			<p class="mg-note mg-explain">
				{#if anyRequired}
					COG, KEGG, eggNOG, UniProt, Pfam, TIGRFAM, PGAP, InterPro and dbCAN are part of every run: labeling and the confidence score
					read them, so every run's scores mean the same. MEROPS, TCDB and GenProp are yours to add: MEROPS and TCDB add peptidase and
					transporter calls, and need their licence terms accepted. KEGG uses only the public KOfam data. Gene calling, operons,
					consolidation, labeling, fingerprints and scoring are part of every run.
				{:else}
					Recommended runs the phase 4 tools, which the envelope stage and scoring read. MEROPS and TCDB add peptidase and
					transporter calls. Tools with licence terms (MEROPS and TCDB) stay off until you accept their
					terms; add them yourself. KEGG uses only the public KOfam data. Gene calling, operons, consolidation, labeling, fingerprints and
					scoring are part of every run.
				{/if}
			</p>

			<div class="rs-groups" class:locked={!toolsDraft} inert={!toolsDraft} bind:clientWidth={groupsWidth} style="--cols: {toolCols}">
				{#each groups as g (g.phase)}
					<section class="rs-group" aria-label="Phase {g.phase}">
						<h3>
							Phase {g.phase}{PHASE_NAME[g.phase] ? ` | ${PHASE_NAME[g.phase]}` : ''}
							{#if g.phase === 4 && !anyRequired}<span class="rs-rec">recommended</span>{/if}
							<span class="rs-gcount">{g.tools.filter((t) => inRun.has(t.name)).length} of {g.tools.length}</span>
						</h3>
						<ul class="rs-even mg-even">
							{#each g.tools as t (t.name)}
								{@const on = inRun.has(t.name)}
								<li title={hint(t)}>
									<button
										type="button"
										class="rs-tool"
										class:on
										class:locked={!t.licensed}
										class:required={t.required}
										aria-pressed={on}
										disabled={!t.licensed || t.required}
										title={hint(t)}
										onclick={() => toggle(t.name)}
									>
										<span class="rs-box-mark" aria-hidden="true">{#if on}<Check size={12} strokeWidth={3.2} />{/if}</span>
										<span class="rs-tname">
											<span>{t.label ?? t.name}</span>
											{#if BLURB[t.name]}<small>{BLURB[t.name]}</small>{/if}
										</span>
										{#if t.required && t.licensed}
											<span class="rs-required">required</span>
										{:else if !t.licensed}
											<span class="rs-lic need" aria-label="Locked until its licence terms are accepted"><Lock size={11} /></span>
										{:else if t.gated}
											<span class="rs-lic" aria-label="Licence accepted"><KeyRound size={11} /></span>
										{/if}
									</button>
								</li>
							{/each}
						</ul>
					</section>
				{/each}
			</div>
			{#if locked.length}
				<p class="mg-note rs-locked">
					<Lock size={11} /> {locked.length} need their licence terms accepted first:
					{locked.map((t) => t.label ?? t.name).join(', ')}.
					{#if backend.cluster}<a class="mg-link" href="#licence">Licence terms</a>{:else}<a class="mg-link" href={uiBase.to('/settings#licences')}>Licences</a>{/if}
				</p>
			{/if}
		</div>
	</Fold>
</section>

<style>
	/* Each box as Install's: a card with a named head; its body pads like the head. */
	.rs-card {
		color: var(--mg-text);
	}
	.rs-card :global(.mg-card-head) {
		flex-wrap: wrap;
		row-gap: 6px;
	}
	.rs-body {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: var(--cr-pad, 16px 18px);
	}
	.rs-body > .mg-note {
		margin: 0;
	}
	/* The lock: a quiet line over the settings, and the settings shown but not changeable. */
	.rs-notice-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 8px 16px;
	}
	.rs-notice {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.rs-notice :global(svg) {
		flex: none;
		color: var(--mg-text-3);
	}
	.rs-notice b {
		font-weight: 600;
		color: var(--mg-text);
	}
	.rs-notice.open :global(svg) {
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.locked {
		opacity: 0.8;
	}
	.rs-unlock {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 28px;
		padding: 0 12px;
		border: 1px solid var(--mg-border-strong);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		cursor: pointer;
	}
	.rs-unlock:hover {
		border-color: var(--mg-accent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.rs-help {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		padding: 0;
		border: 1px solid transparent;
		border-radius: 50%;
		background: none;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.rs-help:hover,
	.rs-help[aria-pressed='true'] {
		border-color: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		color: var(--mg-accent-ink, var(--mg-accent));
	}

	/* ---- gene calling: the three phases in even cells ---- */
	.rs-phases {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.rs-phases > li {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
		padding: 10px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
	}
	.rs-phases .mg-note {
		margin: 0;
	}
	.rs-ph {
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-3);
	}
	.rs-row {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 28px;
		font-size: var(--mg-fs-sm);
	}
	.rs-split {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 6px;
	}
	.rs-cell {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 6px;
		padding: 4px 8px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-3);
	}
	.rs-cell span {
		font-size: var(--mg-fs-xs);
	}
	.rs-cell.on {
		border-color: var(--mg-accent);
		background: var(--mg-accent);
		color: var(--mg-on-accent, #fff);
	}
	.warn {
		color: var(--mg-warn);
	}

	/* ---- pills ---- */
	.rs-seg {
		display: inline-grid;
		grid-template-columns: repeat(var(--k), minmax(0, auto));
		gap: 2px;
		max-width: 100%;
		padding: 3px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
	}
	.rs-seg button {
		height: 26px;
		padding: 0 12px;
		border: 0;
		border-radius: var(--mg-r-sm);
		background: transparent;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		white-space: nowrap;
		cursor: pointer;
	}
	.rs-seg button[aria-checked='true'] {
		background: var(--mg-accent);
		color: var(--mg-on-accent, #fff);
	}

	/* ---- the tools: one column count for every phase, rows full ---- */
	.rs-groups {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.rs-group h3 {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 0 0 6px;
		font-size: var(--mg-fs-xs);
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.rs-rec {
		padding: 1px 7px;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-ok) 14%, transparent);
		color: var(--mg-ok);
		font-weight: 600;
		letter-spacing: 0;
		text-transform: none;
	}
	.rs-gcount {
		font-weight: 500;
		letter-spacing: 0;
		text-transform: none;
	}
	.rs-even {
		gap: 6px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.rs-tool {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 9px;
		width: 100%;
		min-height: 40px;
		padding: 5px 10px 5px 9px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-text-2);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.rs-tool:hover:not(:disabled) {
		border-color: var(--mg-border-strong);
	}
	/* Picked: a faint wash, so the choice shows quietly. */
	.rs-tool.on {
		border-color: color-mix(in srgb, var(--mg-accent) 25%, var(--mg-border));
		background: color-mix(in srgb, var(--mg-accent) 3%, var(--mg-surface));
		color: var(--mg-text);
	}
	.rs-tool.locked {
		border-style: dashed;
		opacity: 0.6;
		cursor: not-allowed;
	}
	/* A disabled button shows no tooltip: its box (the li) carries the hint. */
	.rs-tool:disabled {
		pointer-events: none;
	}
	/* In every run, so not a choice: plain, with a grey tick, apart from the tools to pick. */
	.rs-tool.required:disabled {
		border-color: var(--mg-border);
		background: var(--mg-surface);
		opacity: 1;
		color: var(--mg-text);
		cursor: default;
	}
	.rs-required {
		flex: none;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-xs);
		font-weight: 500;
	}
	.rs-box-mark {
		display: grid;
		place-items: center;
		width: 16px;
		height: 16px;
		border: 2px solid var(--mg-border-strong);
		border-radius: 5px;
		color: var(--mg-on-accent, #fff);
	}
	.on .rs-box-mark {
		border-color: var(--mg-accent);
		background: var(--mg-accent);
	}
	.required .rs-box-mark {
		border-color: var(--mg-text-3);
		background: var(--mg-text-3);
	}
	.rs-tname {
		display: flex;
		flex-direction: column;
		min-width: 0;
		line-height: 1.25;
		font-size: var(--mg-fs-sm);
		font-weight: 600;
	}
	.rs-tname small {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		font-weight: 400;
		color: var(--mg-text-3);
	}
	.rs-lic {
		display: inline-flex;
		align-items: center;
		padding: 2px 5px;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 12%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.rs-lic.need {
		background: color-mix(in srgb, var(--mg-warn) 16%, transparent);
		color: var(--mg-warn);
	}
	.rs-locked :global(svg) {
		display: inline;
		vertical-align: -1px;
	}
	@media (max-width: 900px) {
		.rs-phases {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
