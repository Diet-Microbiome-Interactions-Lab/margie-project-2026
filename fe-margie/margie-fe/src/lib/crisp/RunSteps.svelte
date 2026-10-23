<script lang="ts">
	import { Check, CircleHelp, KeyRound, Lock } from 'lucide-svelte';
	import { sharedColumns } from '$lib/workspace/even';
	import Switch from '$lib/workspace/Switch.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws, type Depth } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * Analyze's steps after the genomes: 2, gene calling (QUAST, GTDB-Tk, then RASTtk or
	 * Prodigal: phases 1 to 3), and 3, the annotation tools by phase (phase 4 recommended).
	 * Short titles; what each does shows in Guided mode or under a step's ?.
	 */

	const save = async (key: string, value: string) => {
		if (value === ws.setting(key)) return;
		if (await ws.saveSettings({ [key]: value })) ui.notify('Saved', 'ok');
	};
	let help = $state<Record<string, boolean>>({});
	// Both steps fold away until opened; their heads say what is chosen.
	const CALLING = 'analyze:calling';
	const TOOLS = 'analyze:tools';

	// ------------------------------------------------ gene calling
	const gtdbtk = $derived(ws.setting('RUN_GTDBTK') === '1');
	const caller = $derived(ws.setting('GENE_CALLER') || 'prodigal');
	/** RASTtk needs a known domain and genetic code: from the genome table, or from GTDB-Tk. */
	const known = $derived(ws.genomes.filter((g) => g.domain && g.domain !== 'Unknown' && g.genetic_code).length);
	const all = $derived(ws.genomes.length);
	/** On the cluster each genome gets RASTtk when both are known (or GTDB-Tk runs), Prodigal otherwise. */
	const byRast = $derived(gtdbtk ? all : known);
	const quast = $derived(ws.tools.find((t) => t.name === 'quast'));
	const quastOn = $derived(ws.chosenTools.includes('quast'));
	// GTDB-Tk needs its own image and reference tree.
	const gtdbtkMissing = $derived(
		[ws.images.find((r) => r.name === 'gtdbtk'), ws.databases.find((r) => r.name === 'gtdbtk')].some((r) => r && r.status !== 'ok')
	);

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
		merops: 'Peptidases; not used in scoring',
		tcdb: 'Transporters; not used in scoring',
		deepsig: 'Signal peptides',
		signalp4: 'Signal peptides, v4',
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
	const inRun = $derived(new Set(ws.chosenTools));
	const picked = $derived(groups.reduce((a, g) => a + g.tools.filter((t) => inRun.has(t.name)).length, 0));
	const offered = $derived(groups.reduce((a, g) => a + g.tools.length, 0));
	const locked = $derived(ws.tools.filter((t) => !t.licensed));

	const DEPTHS: { value: Depth; label: string }[] = [
		{ value: 'standard', label: 'Recommended' },
		{ value: 'licensed', label: 'All' },
		{ value: 'quick', label: 'None' },
		{ value: 'custom', label: 'Custom' }
	];
	/** A tool ticked by hand makes the choice Custom, from what was chosen. */
	function toggle(name: string) {
		const now = ws.chosenTools;
		ws.custom = now.includes(name) ? now.filter((x) => x !== name) : [...now, name];
		ws.depth = 'custom';
	}
</script>

{#snippet helpButton(id: string, what: string)}
	{#if !ui.explain}
		<button type="button" class="rs-help" aria-pressed={!!help[id]} aria-label={what} title={what} onclick={() => (help[id] = !help[id])}>
			<CircleHelp size={15} />
		</button>
	{/if}
{/snippet}

<!-- ------------------------------------------------ 2. gene calling -->
<section class="rs-box" class:folded={ui.isFolded(CALLING, true)} aria-labelledby="rs-calling" data-help={help.calling ? 'on' : undefined}>
	<header class="rs-head">
		<span class="rs-n">2</span>
		<h2 id="rs-calling">Gene calling</h2>
		<span class="rs-sum">
			{#if backend.cluster}
				{all ? (byRast === all ? `RASTtk for all ${all}` : byRast ? `RASTtk ${byRast}, Prodigal ${all - byRast}` : `Prodigal for all ${all}`) : ''}
			{:else}
				{caller === 'rasttk' ? 'RASTtk' : caller === 'prodigal' ? 'Prodigal' : 'RASTtk or Prodigal'}
			{/if}
		</span>
		<span class="mg-grow"></span>
		{#if !ui.isFolded(CALLING, true)}{@render helpButton('calling', 'How gene calling works')}{/if}
		<button type="button" class="mg-link quiet" aria-expanded={!ui.isFolded(CALLING, true)} onclick={() => ui.toggleFold(CALLING, true)}>{ui.isFolded(CALLING, true) ? 'Show' : 'Hide'}</button>
	</header>

	{#if !ui.isFolded(CALLING, true)}
	<ol class="rs-phases">
		<li>
			<span class="rs-ph">Phase 1 | Quality</span>
			<div class="rs-row">
				<b>QUAST</b>
				<span class="mg-grow"></span>
				{#if quast}<Switch label="Check assembly quality with QUAST" checked={quastOn} onchange={() => toggle('quast')} />{:else}<span class="mg-note">not offered</span>{/if}
			</div>
			<p class="mg-note mg-explain">Assembly statistics (contigs, N50, length) for each genome. Optional; nothing later depends on it.</p>
		</li>
		<li>
			<span class="rs-ph">Phase 2 | Taxonomy</span>
			<div class="rs-row">
				<b>GTDB-Tk</b>
				<span class="mg-grow"></span>
				<Switch label="Work out domain and genetic code with GTDB-Tk" checked={gtdbtk} onchange={(on) => save('RUN_GTDBTK', on ? '1' : '0')} />
			</div>
			{#if gtdbtk && gtdbtkMissing}
				<p class="mg-note warn">Needs its image and reference tree. <a class="mg-link" href={uiBase.to('/install#installed')}>Install</a></p>
			{/if}
			<p class="mg-note mg-explain">
				Places each genome in the GTDB taxonomy, which gives RASTtk its domain and genetic code. Use it when you do not know them. It needs
				a highmem node (about 400 GB) and adds hours; off, the genome table supplies both.
			</p>
		</li>
		<li>
			<span class="rs-ph">Phase 3 | Gene caller</span>
			{#if backend.cluster}
				<div class="rs-split" aria-label="Gene caller by genome">
					<span class="rs-cell" class:on={byRast > 0}><b>RASTtk</b><span>{byRast} genome{byRast === 1 ? '' : 's'}</span></span>
					<span class="rs-cell" class:on={all - byRast > 0}><b>Prodigal</b><span>{all - byRast} genome{all - byRast === 1 ? '' : 's'}</span></span>
				</div>
				{#if !gtdbtk && known < all}
					<p class="mg-note">
						{all - known} without a domain and genetic code go to Prodigal.
						<a class="mg-link" href="#genomes">Fill them in</a> or turn on GTDB-Tk for RASTtk.
					</p>
				{/if}
			{:else}
				<div class="rs-seg" role="radiogroup" aria-label="Gene caller" style="--k: 3">
					{#each [{ v: 'auto', l: 'Per genome' }, { v: 'rasttk', l: 'RASTtk' }, { v: 'prodigal', l: 'Prodigal' }] as o (o.v)}
						<button type="button" role="radio" aria-checked={caller === o.v} onclick={() => save('GENE_CALLER', o.v)}>{o.l}</button>
					{/each}
				</div>
			{/if}
			<p class="mg-note mg-explain">
				RASTtk is recommended when a genome's domain and genetic code are known (from the table or GTDB-Tk): it calls the genes and
				annotates them too. Prodigal is unsupervised and fast, needs neither, but calls genes only.
			</p>
		</li>
	</ol>
	{/if}
</section>

<!-- ------------------------------------------------ 3. annotation tools -->
<section class="rs-box" id="tools" class:folded={ui.isFolded(TOOLS, true)} aria-labelledby="rs-tools" data-help={help.tools ? 'on' : undefined}>
	<header class="rs-head">
		<span class="rs-n">3</span>
		<h2 id="rs-tools">Annotation tools</h2>
		<span class="rs-sum">{picked} of {offered}{ui.isFolded(TOOLS, true) ? `, ${DEPTHS.find((d) => d.value === ws.depth)?.label.toLowerCase()}` : ''}</span>
		<span class="mg-grow"></span>
		{#if !ui.isFolded(TOOLS, true)}
			<div class="rs-seg" role="radiogroup" aria-label="Which tools" style="--k: {DEPTHS.length}">
				{#each DEPTHS as d (d.value)}
					<button type="button" role="radio" aria-checked={ws.depth === d.value} onclick={() => (ws.depth = d.value)}>{d.label}</button>
				{/each}
			</div>
		{/if}
		{#if !ui.isFolded(TOOLS, true)}{@render helpButton('tools', 'What the tools do')}{/if}
		<button type="button" class="mg-link quiet" aria-expanded={!ui.isFolded(TOOLS, true)} onclick={() => ui.toggleFold(TOOLS, true)}>{ui.isFolded(TOOLS, true) ? 'Show' : 'Hide'}</button>
	</header>
	{#if !ui.isFolded(TOOLS, true)}
	<p class="mg-note mg-explain">
		Recommended runs the phase 4 tools, which the envelope stage and scoring read. MEROPS and TCDB are not used in scoring but add
		peptidase and transporter calls. Tools with licence terms (MEROPS, Phobius, SignalP and others) stay off until you accept their terms;
		add them yourself. KEGG uses only the public KOfam data. Gene calling, operons, consolidation, labeling, fingerprints and scoring always
		run.
	</p>

	<div class="rs-groups" bind:clientWidth={groupsWidth} style="--cols: {toolCols}">
		{#each groups as g (g.phase)}
			<section class="rs-group" aria-label="Phase {g.phase}">
				<h3>
					Phase {g.phase}{PHASE_NAME[g.phase] ? ` | ${PHASE_NAME[g.phase]}` : ''}
					{#if g.phase === 4}<span class="rs-rec">recommended</span>{/if}
					<span class="rs-gcount">{g.tools.filter((t) => inRun.has(t.name)).length} of {g.tools.length}</span>
				</h3>
				<ul class="rs-even mg-even">
					{#each g.tools as t (t.name)}
						{@const on = inRun.has(t.name)}
						<li>
							<button
								type="button"
								class="rs-tool"
								class:on
								class:locked={!t.licensed}
								aria-pressed={on}
								disabled={!t.licensed}
								title={t.licensed ? (t.gated ? 'Licence accepted' : '') : 'Accept its licence terms first'}
								onclick={() => toggle(t.name)}
							>
								<span class="rs-box-mark" aria-hidden="true">{#if on}<Check size={12} strokeWidth={3.2} />{/if}</span>
								<span class="rs-tname">
									<span>{t.label ?? t.name}</span>
									{#if BLURB[t.name]}<small>{BLURB[t.name]}</small>{/if}
								</span>
								{#if !t.licensed}
									<span class="rs-lic need"><Lock size={11} /></span>
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
	{/if}
</section>

<style>
	.rs-box {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 16px 18px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text);
	}
	.rs-box > .mg-note {
		margin: 0;
	}
	/* Folded: one slim line. */
	.rs-box.folded {
		padding-top: 10px;
		padding-bottom: 10px;
	}
	.rs-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 10px;
	}
	.rs-n {
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
	.rs-head h2 {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.rs-sum {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
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
		border-color: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		color: var(--mg-text);
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
	.rs-tool.on {
		border-color: color-mix(in srgb, var(--mg-accent) 55%, var(--mg-border));
		background: color-mix(in srgb, var(--mg-accent) 8%, var(--mg-surface));
		color: var(--mg-text);
	}
	.rs-tool.locked {
		border-style: dashed;
		opacity: 0.6;
		cursor: not-allowed;
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
