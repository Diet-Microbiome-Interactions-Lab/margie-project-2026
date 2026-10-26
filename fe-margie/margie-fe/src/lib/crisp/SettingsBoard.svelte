<script lang="ts">
	import { even } from '$lib/workspace/even';
	import { pathComplete } from '$lib/workspace/path-complete';
	import Explain from '$lib/workspace/Explain.svelte';
	import { tick, untrack } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { Bot, CircleHelp, Cpu, FileCode, Database, Folder, FolderOpen, Folders, HardDrive, Layers, ListChecks, Lock, LockOpen, MemoryStick, RotateCcw, ScrollText, Server, SlidersHorizontal, Wrench } from 'lucide-svelte';
	import { api, formatBytes, post } from '$lib/api';
	import { LICENCE_LEGAL_NOTICE, LICENCE_STATEMENT, statementMatches } from '$lib/licence';
	import Switch from '$lib/workspace/Switch.svelte';
	import FolderPick from '$lib/workspace/FolderPick.svelte';
	import { advanced } from '$lib/workspace/advanced-lock.svelte';
	import { ws, type Setting } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import { CONFIRMED, GUARDED, isConfirmed, isGuarded, unlocks } from '$lib/workspace/guarded';
	import DatabasesPanel from '$lib/workspace/DatabasesPanel.svelte';
	import FreshDatabases from './FreshDatabases.svelte';
	import { DB_BACKUPS, DB_PARTS } from '$lib/cluster/backend';
	import { backend } from '$lib/workspace/backend.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { rangeOf } from './settingRange';

	/**
	 * Modern's Settings page: cards of sliders, switches and folder fields, with the
	 * same guards, licence form and #KEY anchors other pages link to. One section is
	 * open at a time (the chips at the top or its Show/Hide); edits stay marked
	 * unsaved until that section's Save.
	 */

	/** `closed`: folded until opened, for a group too long to read by default. */
	/** `wide`: a long run of numbers, given the board's full width below the other cards. */
	const GROUPS: { id: string; title: string; icon: typeof Cpu; match: (s: Setting) => boolean; closed?: boolean; wide?: boolean }[] = [
		{ id: 'steps', title: 'Steps', icon: ListChecks, match: (s) => s.group === 'Tools' && s.type === 'flag' },
		// A cluster's: the SLURM account and limits, and its job history.
		{ id: 'cluster', title: 'Cluster', icon: Server, match: (s) => s.group === 'Cluster' },
		{ id: 'runtime', title: 'Running', icon: Cpu, match: (s) => s.group === 'Runtime' },
		{ id: 'folders', title: 'Folders', icon: FolderOpen, match: (s) => s.group === 'Folders' || s.group === 'Setup' },
		{ id: 'tools', title: 'Tool options', icon: Wrench, match: (s) => s.group === 'Tools' && s.type !== 'flag' },
		// A cluster's: resources shared by every tool, per phase, and per tool.
		{ id: 'phases', title: 'Phases', icon: Layers, match: (s) => s.group === 'Phases', wide: true },
		{ id: 'per-tool', title: 'Per tool', icon: SlidersHorizontal, match: (s) => s.group === 'Per tool', closed: true, wide: true },
		// A cluster's: the databases a run reads and grows (your working copies) and where a first run copies them from.
		{ id: 'databases', title: 'Databases', icon: Database, match: (s) => s.group === 'Databases' },
		// Derived from the folders above; rarely changed.
		{ id: 'other-folders', title: 'Other folders', icon: Folders, match: (s) => s.group === 'Other folders' },
		// The built-in model for Chat with the genome.
		{ id: 'llm', title: 'Built-in model', icon: Bot, match: (s) => s.group === 'LLM' }
	];
	/*
	 * Only what applies where MARGIE runs now. On this computer, the SLURM
	 * account, partition and job sizes (phases, per tool) are the cluster's and
	 * are left out; on a cluster, this computer's own limits (LOCAL_...) are.
	 */
	const CLUSTER_ONLY = new Set(['Cluster', 'Phases', 'Per tool']);
	const applies = (s: Setting) =>
		backend.cluster ? !s.key.startsWith('LOCAL_') : !CLUSTER_ONLY.has(s.group) && !s.key.startsWith('SLURM_') && s.key !== 'PARALLEL_TOOLS';
	/** Databases: their parts in order (what every run needs, what runs read, where results go, backups). */
	const partRank = (s: Setting) => {
		const k = DB_PARTS.findIndex((p) => s.label.startsWith(`${p}: `));
		return k < 0 ? DB_PARTS.length : k;
	};
	const groups = $derived(
		GROUPS.map((g) => {
			const items = ws.settings.filter((s) => g.match(s) && applies(s));
			return { ...g, items: g.id === 'databases' ? [...items].sort((a, b) => partRank(a) - partRank(b)) : items };
		}).filter((g) => g.items.length)
	);

	/** This computer: what it has, and what MARGIE may use of it. */
	const machine = $derived(backend.cluster ? null : (ws.overview as { machine?: { chip?: string; cores?: number; memory?: number; diskFree?: number; os?: string } } | null)?.machine ?? null);
	/** The folders to jump to (on a cluster: home, scratch and depot among them). */
	let places = $state<{ label: string; path: string }[]>([]);
	$effect(() => {
		void backend.cluster;
		api<{ places: { label: string; path: string }[] }>('/files?places=1')
			.then((d) => (places = d.places.filter((p) => p.path && p.path !== '/')))
			.catch(() => (places = []));
	});
	const changed = $derived(groups.reduce((a, g) => a + g.items.filter((s) => s.overridden).length, 0));

	/**
	 * A group's settings as rows, with runs that share a "Phase: field" label
	 * gathered under the phase (Annotation: nodes, CPUs, memory, time). A
	 * description already shown in the group is not repeated under the next.
	 */
	type Chunk = { head: string | null; cells: boolean; items: { s: Setting; label: string; desc: boolean }[] };
	function chunks(id: string, items: Setting[]): Chunk[] {
		const out: Chunk[] = [];
		const seen = new Set<string>();
		for (const s of items) {
			const at = s.label.indexOf(': ');
			const head = at > 0 ? s.label.slice(0, at) : null;
			const label = head ? s.label.slice(at + 2).replace(/^\w/, (c) => c.toUpperCase()) : s.label;
			const cells = head !== null || id === 'per-tool';
			const last = out.at(-1);
			const item = { s, label, desc: !cells || !seen.has(s.description) };
			if (cells) seen.add(s.description);
			// Titled settings group under their title; untitled ones in a row run together.
			if (last && last.cells === cells && last.head === head) last.items.push(item);
			else out.push({ head, cells, items: [item] });
		}
		return out;
	}

	/**
	 * A wide group as a table: one row per phase (or tool), one column per
	 * field they share (Nodes, CPUs, Memory, Time limit), a gap where a row
	 * lacks one. Settings without a phase are left for the plain rows.
	 */
	type Row = { head: string; note: string; phase: number | null; at: Map<string, Chunk['items'][number]> };
	/** The pipeline phase a per-tool setting belongs to, from its description ("Phase 3: ..."). */
	const phaseOf = (s: Setting) => {
		const m = s.description.match(/^Phase\s+(\d+)/i);
		return m ? Number(m[1]) : null;
	};
	/** What each pipeline phase does, for the Phases and Per tool cards. */
	const PHASE_NAMES: Record<number, string> = {
		1: 'Assembly quality',
		2: 'Taxonomy',
		3: 'Gene calling',
		4: 'Annotation',
		5: 'Operons',
		6: 'Topology and signal peptides',
		7: 'Cell envelope',
		8: 'Localisation',
		9: 'Consolidation',
		10: 'Labeling',
		11: 'Fingerprints',
		12: 'Scoring',
		13: 'Fingerprint database',
		14: 'Comparisons',
		15: 'Evidence and the model'
	};
	/** A wide group's columns that hold folders or files (shown in full, below the numbers). */
	const pathCols = (t: { rows: Row[]; cols: string[] }) =>
		new Set(t.cols.filter((c) => t.rows.some((r) => r.at.get(c)?.s.type === 'path')));
	/** A text box that grows with what it holds, so a long path shows in full. */
	function autogrow(node: HTMLTextAreaElement, _value?: unknown) {
		const fit = () => {
			node.style.height = 'auto';
			// scrollHeight leaves out the borders, which the box's height includes.
			node.style.height = `${node.scrollHeight + node.offsetHeight - node.clientHeight}px`;
		};
		fit();
		node.addEventListener('input', fit);
		const seen = new ResizeObserver(fit);
		seen.observe(node);
		return {
			update: fit,
			destroy() {
				node.removeEventListener('input', fit);
				seen.disconnect();
			}
		};
	}
	function table(id: string, items: Setting[]) {
		const all = chunks(id, items);
		const rows: Row[] = [];
		const cols: string[] = [];
		for (const c of all) {
			if (!c.cells || !c.head) continue;
			const perTool = id === 'per-tool';
			// A phase's or tool's fields need not come together: they join its one row.
			const same = rows.find((r) => r.head === c.head);
			if (same) {
				for (const it of c.items) same.at.set(it.label, it);
				continue;
			}
			rows.push({
				head: c.head,
				// A tool's fields say the same thing ("Phase 1: ... for QUAST"); the phase heading says it once.
				// A phase's row needs no note: its fields are the columns.
				note: perTool || id === 'phases' ? '' : c.items[0].s.description,
				phase: perTool ? phaseOf(c.items[0].s) : null,
				at: new Map(c.items.map((it) => [it.label, it]))
			});
		}
		// Per tool: the tools in the order the pipeline runs them, under their phase.
		if (id === 'per-tool') rows.sort((a, b) => (a.phase ?? 99) - (b.phase ?? 99));
		// Phases in their own order: 1, 2, ... 15.
		if (id === 'phases') rows.sort((a, b) => Number(a.head.replace(/\D+/g, '')) - Number(b.head.replace(/\D+/g, '')));
		// The columns in the order of the fullest row, then any the others add; a partition first.
		for (const r of [...rows].sort((a, b) => b.at.size - a.at.size)) for (const k of r.at.keys()) if (!cols.includes(k)) cols.push(k);
		cols.sort((a, b) => Number(b === 'Partition') - Number(a === 'Partition'));
		return { rows, cols, rest: all.filter((c) => !c.cells || !c.head) };
	}

	/**
	 * The narrow cards dealt into equal columns, as many as the width holds:
	 * each goes, in order, to the column that is shortest so far (by a rough
	 * height from its settings), so the columns end close to level.
	 */
	let boardWidth = $state(0);
	/* One section is open at a time, so the sections stand in one column,
	   each the full width; the open one lays its settings out across it. */
	const ncols = 1;
	const weight = (items: Setting[]) => 1.4 + items.reduce((a, s) => a + (s.type === 'flag' ? 1 : s.type === 'path' ? 1.5 : 1.8), 0);
	type Slot = { g: (typeof groups)[number] | null; k: number };
	const columns = $derived.by(() => {
		const cols: Slot[][] = Array.from({ length: ncols }, () => []);
		const h = cols.map(() => 0);
		const put = (slot: Slot, w: number) => {
			const i = h.indexOf(Math.min(...h));
			cols[i].push(slot);
			h[i] += w;
		};
		groups.filter((g) => !g.wide).forEach((g, k) => put({ g, k }, weight(g.items)));
		if (licenceTools.length) put({ g: null, k: groups.length }, 6 + licenceTools.length * 0.4);
		return cols;
	});

	const budget = $derived(Number(ws.setting('LOCAL_MAX_CORES')) || null);

	// Unlocks last for this visit only, so none stays open on a shared machine.
	let unlocked = $state(false);
	let asking = $state<string | null>(null);
	/** Click-to-unlock settings opened this visit, and the one whose note is showing. */
	let opened = $state<Record<string, boolean>>({});
	let confirming = $state<string | null>(null);
	let phrase = $state('');
	let wrong = $state(false);
	const locked = (s: Setting) => (isConfirmed(s.key) && !opened[s.key]) || (isGuarded(s.key) && !unlocked);

	async function tryUnlock() {
		if (await unlocks(phrase)) {
			unlocked = true;
			asking = null;
			phrase = '';
			wrong = false;
			ui.notify('Unlocked for this visit', 'ok');
		} else {
			wrong = true;
			ui.notify('That is not the phrase', 'error');
		}
	}

	// ------------------------------------------------ one section open at a time
	// The chips along the top pick it; the first group shows until one is picked.
	let openId = $state<string | null>(null);
	const shownId = $derived(openId ?? groups[0]?.id ?? null);
	const isOpen = (id: string) => shownId === id;

	/** Sections whose ? is pressed: their explanations show in Simple mode too. */
	let help = $state<Record<string, boolean>>({});

	/** The path setting whose folder icon was pressed: its folder (or file) picker is open. */
	let pickFor = $state<Setting | null>(null);
	const isFilePath = (p: string) => /\.[a-z0-9]{1,8}$/i.test(p.trim());

	/** The files behind the settings and the runs, for editing by hand (Advanced). */
	const CONFIG_FILE = '~/.config/bioinformatics-tools/config.yaml';
	const WORKFLOW_FILE = '~/bioinformatics-tools/bioinformatics_tools/workflow_tools/margie_sb.smk';
	/** The two files open for editing (Unlock): advanced.open, shared with the viewer and the editor. */
	const filesOpen = $derived(advanced.open);
	/** The workflow has edits by hand: the copy of MARGIE takes updates again once it is restored. */
	let workflowEdited = $state(false);
	/** Which default is about to be put back, once confirmed. */
	let restoreAsk = $state<'' | 'config' | 'workflow'>('');
	let restoring = $state(false);
	/** Brings the account's copy of MARGIE up to date (as before a run) and learns whether its workflow has edits. */
	async function checkFiles() {
		try {
			workflowEdited = (await api<{ workflow_edited: boolean }>('/settings/advanced')).workflow_edited;
		} catch {
			workflowEdited = false;
		}
	}
	$effect(() => {
		if (backend.cluster) untrack(() => checkFiles());
	});
	async function openFiles() {
		advanced.set(true);
		await checkFiles();
	}
	async function restoreDefault() {
		const which = restoreAsk;
		if (!which) return;
		restoring = true;
		try {
			const d = await post<{ path: string; backup: string | null }>('/settings/restore-default', { which });
			const kept = d.backup ? `; yours is ${d.backup.split('/').at(-1)}` : '';
			ui.notify(which === 'config' ? `The default config.yaml is back${kept}` : `MARGIE's workflow is back${kept}`, 'ok');
			if (which === 'config') await ws.loadSettings();
			else workflowEdited = false;
			restoreAsk = '';
		} catch (e) {
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		} finally {
			restoring = false;
		}
	}

	// ------------------------------------------------ a cluster account without config.yaml
	let creating = $state(false);
	async function createConfig() {
		creating = true;
		await ws.createDefaultConfig();
		creating = false;
	}

	// ------------------------------------------------ edits, saved per section
	/* The values being edited. When the saved settings change, untouched values
	   follow them; edited ones stay as typed until saved or discarded. */
	let draft = $state<Record<string, string>>({});
	let savedAs: Record<string, string> = {};
	$effect(() => {
		const next = Object.fromEntries(ws.settings.map((s) => [s.key, s.value]));
		untrack(() => {
			const d = { ...draft };
			for (const [k, v] of Object.entries(next)) if (!(k in d) || d[k] === savedAs[k]) d[k] = v;
			draft = d;
			savedAs = next;
		});
	});
	const edited = (s: Setting) => String(draft[s.key] ?? s.value) !== s.value;
	const unsaved = (items: Setting[]) => items.filter(edited);
	const anyUnsaved = $derived(ws.settings.some(edited));

	let saving = $state<string | null>(null);
	async function saveGroup(g: { id: string; title: string; items: Setting[] }) {
		const todo = unsaved(g.items);
		if (!todo.length) return;
		saving = g.id;
		const ok = await ws.saveSettings(Object.fromEntries(todo.map((s) => [s.key, String(draft[s.key] ?? '')])));
		saving = null;
		if (ok) ui.notify(`${g.title}: ${todo.length === 1 ? '1 change' : `${todo.length} changes`} saved`, 'ok');
	}
	function discardGroup(g: { items: Setting[] }) {
		for (const s of g.items) draft[s.key] = s.value;
	}

	// Leaving the page with edits not saved asks first.
	beforeNavigate(({ cancel, type }) => {
		if (type !== 'leave' && anyUnsaved && !confirm('Some settings are changed but not saved. Leave without saving them?')) cancel();
	});

	const CHOICE: Record<string, string> = { '1': 'on', '0': 'off' };
	const folderHref = (p: string) => `${uiBase.path}/files?path=${encodeURIComponent(p)}`;

	// ------------------------------------------------ licences
	const licenceTools = $derived(ws.settings.filter((s) => s.key.startsWith('LICENCE_AGREED_')));
	const toolName = (s: Setting) => s.key.slice('LICENCE_AGREED_'.length).toLowerCase();
	const savedUse = $derived(ws.setting('LICENCE_INTENDED_USE'));
	const savedStatement = $derived(statementMatches(ws.setting('LICENCE_STATEMENT')));
	const savedOn = (s: Setting) => s.value === '1' && savedStatement && savedUse.trim() !== '';

	let use = $state('');
	let flags = $state<Record<string, boolean>>({});
	let typed = $state('');
	let savingLic = $state(false);
	$effect(() => {
		use = savedUse;
		flags = Object.fromEntries(licenceTools.map((s) => [s.key, savedOn(s)]));
		typed = '';
	});

	const licChanged = $derived(use.trim() !== savedUse.trim() || licenceTools.some((s) => flags[s.key] !== savedOn(s)));
	const anyOn = $derived(Object.values(flags).some(Boolean));
	/** Accepting a tool, or changing the intended use of accepted ones, needs the statement typed. */
	const needsStatement = $derived(anyOn && (licenceTools.some((s) => flags[s.key] && !savedOn(s)) || use.trim() !== savedUse.trim()));
	const typedOk = $derived(statementMatches(typed));
	const canSave = $derived(licChanged && !savingLic && (!anyOn || use.trim() !== '') && (!needsStatement || typedOk));

	async function saveLicences() {
		savingLic = true;
		const accepted = Object.fromEntries(licenceTools.map((s) => [toolName(s), !!flags[s.key]]));
		const added = await ws.saveLicences(use.trim(), accepted, typed);
		savingLic = false;
		if (added) ui.notify(added.length ? `Accepted: ${added.join(', ')}` : 'Licences saved', 'ok');
	}

	// ------------------------------------------------ going to one setting
	/** Opens the group holding `id` (a setting, a group or "licences"), scrolls to it and lights it up. */
	function reveal(id: string) {
		// A page's own name for a cluster setting (OUTPUT_ROOT) is listed under its real key.
		const alias = ws.settings.find((s) => s.key === id && !s.group);
		const real = alias ? (ws.settings.find((s) => s.group && s.label === alias.label && s.value === alias.value)?.key ?? id) : id;
		const group = real === 'licences' ? 'licences' : (GROUPS.find((g) => g.id === real || ws.settings.some((s) => s.key === real && g.match(s)))?.id ?? '');
		const wasShut = !!group && !isOpen(group);
		if (group) openId = group;
		const ready = wasShut ? new Promise((r) => setTimeout(r, ui.ms(420) + 40)) : tick();
		ready.then(() => {
			const el = document.getElementById(real);
			if (!el) return;
			// A section is brought to the top; one setting to the middle of the window.
			el.scrollIntoView({ block: real === group ? 'start' : 'center', behavior: ui.motion === 'off' ? 'auto' : 'smooth' });
			el.classList.add('flash');
			setTimeout(() => el.classList.remove('flash'), 2500);
		});
	}

	// A link like /settings#RUN_GTDBTK scrolls to that setting once the settings have loaded.
	let handled = '';
	$effect(() => {
		const id = page.url.hash.slice(1);
		if (!id || id === handled || !ws.settings.length) return;
		handled = id;
		reveal(decodeURIComponent(id));
	});
</script>

{#snippet control(s: Setting, wrap?: boolean)}
	{@const r = rangeOf(s, budget)}
	{#if isConfirmed(s.key) && !opened[s.key]}
		{#if confirming === s.key}
			<div class="sb-confirm">
				<span class="mg-note">{CONFIRMED[s.key].why}</span>
				<span class="sb-btns">
					<button
						type="button"
						class="mg-link quiet"
						onclick={() => {
							opened = { ...opened, [s.key]: true };
							confirming = null;
						}}>Unlock</button
					>
					<button type="button" class="mg-link quiet" onclick={() => (confirming = null)}>Cancel</button>
				</span>
			</div>
		{:else}
			<span class="sb-locked">
				<Lock size={13} aria-hidden="true" />
				<span class="mg-mono" title={s.value || s.default}>{s.value || s.default || 'Not set'}</span>
			</span>
			<button type="button" class="mg-link quiet" title={CONFIRMED[s.key].title} onclick={() => (confirming = s.key)}>Unlock</button>
		{/if}
	{:else if isGuarded(s.key) && !unlocked}
		<!-- Shown, never hidden: only changing it by accident needs guarding. -->
		{#if asking === s.key}
			<form
				class="sb-unlock"
				onsubmit={(e) => {
					e.preventDefault();
					tryUnlock();
				}}
			>
				<input
					class="mg-input"
					type="password"
					bind:value={phrase}
					placeholder="Phrase"
					aria-label={GUARDED[s.key].title}
					aria-invalid={wrong || undefined}
					spellcheck="false"
				/>
				<button type="submit" class="mg-link quiet" disabled={!phrase.trim()}>OK</button>
				<button
					type="button"
					class="mg-link quiet"
					onclick={() => {
						asking = null;
						phrase = '';
						wrong = false;
					}}>Cancel</button
				>
			</form>
		{:else}
			<span class="sb-locked">
				<Lock size={13} aria-hidden="true" />
				<span class="mg-mono" title={s.value}>{s.value || 'Not set'}</span>
			</span>
			<button type="button" class="mg-link quiet" title={GUARDED[s.key].why} onclick={() => (asking = s.key)}>Unlock</button>
		{/if}
	{:else if s.type === 'flag'}
		<Switch label={s.label} checked={draft[s.key] === '1'} onchange={(on) => (draft[s.key] = on ? '1' : '0')} />
	{:else if s.type === 'choice' && (s.choices?.length ?? 0) <= 5}
		<div class="sb-seg" role="radiogroup" aria-label={s.label}>
			{#each s.choices ?? [] as c (c)}
				<button
					type="button"
					role="radio"
					aria-checked={draft[s.key] === c}
					onclick={() => (draft[s.key] = c)}>{CHOICE[c] ?? c}</button
				>
			{/each}
		</div>
	{:else if s.type === 'choice'}
		<select class="mg-select" aria-label={s.label} bind:value={draft[s.key]}>
			{#each s.choices ?? [] as c (c)}<option value={c}>{c}</option>{/each}
		</select>
	{:else if r}
		<!-- A number typed, not slid: within its limits, with its unit. -->
		<span class="sb-num">
			<input
				class="mg-input"
				type={s.type === 'int' ? 'number' : 'text'}
				min={s.type === 'int' ? r.min : undefined}
				max={s.type === 'int' ? r.max : undefined}
				step={s.type === 'int' ? r.step : undefined}
				aria-label={s.label}
				title={s.type === 'int' ? `${r.min} to ${r.max}${r.unit ? ` ${r.unit}` : ''}` : undefined}
				placeholder={s.default}
				spellcheck="false"
				bind:value={draft[s.key]}
				onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
			/>
			{#if s.type === 'int' && r.unit}<span class="sb-unit">{r.unit}</span>{/if}
		</span>
	{:else if s.type === 'path'}
		{@const p = String(draft[s.key] || s.default || '')}
		<div class="sb-path">
			<button type="button" class="sb-folder" title={isFilePath(p) ? 'Pick the file' : 'Pick the folder'} aria-label="Pick {s.label}" disabled={locked(s)} onclick={() => (pickFor = s)}>
				<Folder size={15} />
			</button>
			{#if wrap}
				<!-- In a card: the whole path, wrapping, never cut off. -->
				<textarea
					class="mg-input mg-mono sb-path-area"
					rows="1"
					aria-label={s.label}
					placeholder={s.default}
					spellcheck="false"
					bind:value={draft[s.key]}
					use:pathComplete
					use:autogrow={draft[s.key]}
					onkeydown={(e) => {
						if (e.key === 'Enter') {
							e.preventDefault();
							e.currentTarget.blur();
						}
					}}
				></textarea>
			{:else}
				<input
					class="mg-input mg-mono"
					aria-label={s.label}
					placeholder={s.default}
					spellcheck="false"
					bind:value={draft[s.key]}
					use:pathComplete
					onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
				/>
			{/if}
		</div>
	{:else}
		<input
			class="mg-input sb-text-in"
			class:sb-short={s.type === 'int'}
			type={s.type === 'int' ? 'number' : 'text'}
			min={s.type === 'int' ? 1 : undefined}
			aria-label={s.label}
			placeholder={s.default}
			spellcheck="false"
			bind:value={draft[s.key]}
			onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
		/>
	{/if}
{/snippet}

{#snippet reset(s: Setting)}
	{#if String(draft[s.key] ?? s.value) !== s.default && s.type !== 'flag' && !locked(s)}
		<button type="button" class="sb-reset" title="Back to the default{s.default ? `: ${s.default}` : ''} (saved with the section)" onclick={() => (draft[s.key] = s.default)}>
			<RotateCcw size={12} aria-hidden="true" />Reset
		</button>
	{/if}
{/snippet}

<!-- In a card: the same, as a small icon beside the field's name, so the cards stay level. -->
{#snippet undo(s: Setting)}
	{#if String(draft[s.key] ?? s.value) !== s.default && s.type !== 'flag' && !locked(s)}
		<button type="button" class="sb-undo" aria-label="Back to the default for {s.label}" title="Back to the default{s.default ? `: ${s.default}` : ''} (saved with the section)" onclick={() => (draft[s.key] = s.default)}>
			<RotateCcw size={11} aria-hidden="true" />
		</button>
	{/if}
{/snippet}

{#snippet dot(s: Setting)}
	{#if edited(s)}<span class="sb-dot sb-unsaved" title="Changed, not saved yet"></span>
	{:else if s.overridden}<span class="sb-dot" title="Changed from the default"></span>{/if}
{/snippet}

<!-- Simple mode: a section's ? shows what its settings do (Guided mode always does). -->
{#snippet helpButton(id: string)}
	{#if !ui.explain}
		<button type="button" class="sb-help" aria-pressed={!!help[id]} aria-label="What these settings do" title="What these settings do" onclick={() => (help[id] = !help[id])}>
			<CircleHelp size={15} />
		</button>
	{/if}
{/snippet}

{#snippet card(g: (typeof groups)[number], k: number)}
	{@const pending = unsaved(g.items).length}
	{#if isOpen(g.id)}
	{@const t = g.wide ? table(g.id, g.items) : null}
	{@const parts = t ? t.rest : chunks(g.id, g.items)}
	<section class="sb-card" id={g.id} data-shade={g.id} data-help={help[g.id] ? 'on' : undefined} style="--i: {k}">
		<header class="sb-head">
			<span class="sb-ico" aria-hidden="true"><g.icon size={14} /></span>
			<h2 class="sb-title">{g.title}</h2>
			<span class="sb-count">{g.items.length} setting{g.items.length === 1 ? '' : 's'}</span>
			{#if pending}<span class="sb-pending">{pending} unsaved</span>{/if}
			<span class="mg-grow"></span>
			{@render helpButton(g.id)}
		</header>
		<div class="sb-body">
			{#if t && t.rows.length}
				{#if t.cols.length > 1}
					{@const tools = g.id === 'per-tool'}
					{@const paths = pathCols(t)}
					{@const numbers = t.cols.filter((c) => !paths.has(c))}
					{@const loose = t.rest.flatMap((c) => c.items)}
					<!-- Cards, not a long table: tools two to a row in the order they run (each wearing its
					     phase), phases three or four to a row; numbers side by side, a folder or file in full. -->
					<div class="sb-grid" class:tools role="list" aria-label={g.title}>
						{#if loose.length}
							<!-- The group's own settings without a phase: one card across the top. -->
							<article class="sb-tc sb-tc-loose" role="listitem" aria-label="For every tool">
								<header class="sb-tc-head"><span class="sb-tc-num">all</span><b>{tools ? 'Every tool' : 'Every tool, unless set under Per tool'}</b></header>
								<div class="sb-tc-fields">
									{#each loose as it (it.s.key)}
										<div class="sb-tf" id={it.s.key} title={it.s.description}>
											<span class="sb-tf-lbl"><span>{it.label}</span>{@render dot(it.s)}<span class="mg-grow"></span>{@render undo(it.s)}</span>
											<div class="sb-field">{@render control(it.s, true)}</div>
										</div>
									{/each}
								</div>
							</article>
						{/if}
						{#each t.rows as row (row.head)}
							{@const n = tools ? row.phase : Number(row.head.replace(/\D+/g, '')) || null}
							{@const mine = tools ? [...numbers, ...paths] : t.cols.filter((c) => row.at.has(c))}
							<article class="sb-tc" role="listitem" aria-label={row.head}>
								<header class="sb-tc-head">
									{#if tools}
										<b>{row.head}</b>
										<span class="mg-grow"></span>
										{#if n}<span class="sb-tc-phase" title="Phase {n}"><span class="sb-tc-num">{n}</span>{PHASE_NAMES[n] ?? ''}</span>{/if}
									{:else}
										<span class="sb-tc-num">{n ?? '·'}</span><b>{(n && PHASE_NAMES[n]) || row.head}</b>
									{/if}
								</header>
								<div class="sb-tc-fields" style="--path-span: {4 - (numbers.length % 4) || 4}">
									{#each mine as col (col)}
										{@const it = row.at.get(col)}
										{#if it}
											<div class="sb-tf" class:path={paths.has(col)} id={it.s.key} title={it.s.description}>
												<span class="sb-tf-lbl"><span>{col}</span>{@render dot(it.s)}<span class="mg-grow"></span>{@render undo(it.s)}</span>
												<div class="sb-field">{@render control(it.s, true)}</div>
											</div>
										{:else}
											<div class="sb-tf sb-tf-none" class:path={paths.has(col)} aria-label="{col}: not used by {row.head}">
												<span class="sb-tf-lbl"><span>{col}</span></span>
												<span class="sb-tf-dash" aria-hidden="true">not used</span>
											</div>
										{/if}
									{/each}
								</div>
							</article>
						{/each}
					</div>
				{:else}
					<ul class="sb-tiles">
						{#each t.rows as row (row.head)}
							{#each [...row.at.values()] as { s, label } (s.key)}
								<li class="sb-cell" id={s.key}>
									<div class="sb-cell-top">
										<span class="sb-tile-name">{row.head}</span>
										<span class="sb-lbl">{label}</span>{@render dot(s)}
										<span class="mg-grow"></span>
										{@render reset(s)}
									</div>
									<div class="sb-field">{@render control(s)}</div>
									{#if s.description}<span class="sb-desc mg-explain">{s.description}</span>{/if}
								</li>
							{/each}
						{/each}
					</ul>
				{/if}
			{/if}
			<ul class="sb-list" class:sb-empty={t ? !t.rest.length || (t.rows.length > 0 && t.cols.length > 1) : false} class:sb-parts={parts.some((c) => c.cells && c.head)}>
				{#each parts as c, j (c.items[0].s.key + j)}
					{#if c.cells && g.id === 'databases' && c.head === DB_BACKUPS}
						<li class="sb-sub sb-sub-fold">
							<details class="sb-backups">
								<summary><h3 class="sb-subhead">Backups</h3><span class="sb-desc mg-explain">where backups go, the first copies, and your copies' backups</span></summary>
								<ul class="sb-cells" use:even={[300, 2]}>
									{#each c.items as { s, label } (s.key)}
										<li class="sb-cell" id={s.key} title={s.description}>
											<div class="sb-cell-top">
												<span class="sb-lbl">{label}</span>{@render dot(s)}
												<span class="mg-grow"></span>
												{@render reset(s)}
											</div>
											<div class="sb-field">{@render control(s)}</div>
										</li>
									{/each}
								</ul>
								{#if backend.cluster}<div class="sb-db"><DatabasesPanel /></div>{/if}
							</details>
						</li>
					{:else if c.cells}
						<li class="sb-sub">
							{#if c.head}<h3 class="sb-subhead">{c.head}</h3>{/if}
							<ul class="sb-cells" use:even={[300, 2]}>
								{#each c.items as { s, label, desc } (s.key)}
									<li class="sb-cell" id={s.key} title={desc ? undefined : s.description}>
										<div class="sb-cell-top">
											<span class="sb-lbl">{label}</span>{@render dot(s)}
											<span class="mg-grow"></span>
											{@render reset(s)}
										</div>
										<div class="sb-field">{@render control(s)}</div>
										{#if desc && s.description}<span class="sb-desc mg-explain">{s.description}</span>{/if}
									</li>
								{/each}
							</ul>
						</li>
					{:else}
						<li class="sb-sub sb-plain">
							<ul class="sb-cells" use:even={[300, 2]}>
								{#each c.items as { s } (s.key)}
									{@const flag = s.type === 'flag' && !locked(s)}
									<li class="sb-cell" id={s.key}>
										<div class="sb-cell-top">
											<span class="sb-lbl">{s.label}</span>{@render dot(s)}
											<span class="mg-grow"></span>
											{#if flag}{@render control(s)}{:else}{@render reset(s)}{/if}
										</div>
										{#if !flag}<div class="sb-field">{@render control(s)}</div>{/if}
										{#if s.description}<span class="sb-desc mg-explain">{s.description}</span>{/if}
									</li>
								{/each}
							</ul>
						</li>
					{/if}
				{/each}
			</ul>
			{#if g.id === 'databases' && backend.cluster}<FreshDatabases />{/if}
			<footer class="sb-save">
				{#if pending}<span class="sb-desc">{pending === 1 ? '1 change' : `${pending} changes`} not saved yet</span>{/if}
				<span class="mg-grow"></span>
				<button type="button" class="mg-btn small" disabled={!pending || saving === g.id} onclick={() => discardGroup(g)}>Discard</button>
				<button type="button" class="mg-btn small primary" disabled={!pending || saving === g.id} onclick={() => saveGroup(g)}>
					{saving === g.id ? 'Saving…' : 'Save'}
				</button>
			</footer>
		</div>
	</section>
	{/if}
{/snippet}

<div class="sb">
	{#if backend.cluster && ws.configMissing}
		<div class="sb-missing" role="status">
			<span><b>No configuration on the cluster yet.</b> MARGIE reads her folders, databases and SLURM account from a config.yaml in your home folder; write the default one, then set your SLURM account under Cluster.</span>
			<button type="button" class="mg-btn small primary" disabled={creating} onclick={createConfig}>{creating ? 'Writing…' : 'Write the default configuration'}</button>
		</div>
	{/if}
	<nav class="sb-nav" aria-label="Settings groups" use:even={118}>
		{#each groups as g (g.id)}
			<button type="button" class="sb-chip" aria-pressed={isOpen(g.id)} onclick={() => reveal(g.id)}>
				<g.icon size={13} aria-hidden="true" />{g.title}<span class="sb-n">{g.items.length}</span>
				{#if unsaved(g.items).length}<span class="sb-dot sb-unsaved" title="Unsaved changes"></span>{/if}
			</button>
		{/each}
		{#if licenceTools.length}
			<button type="button" class="sb-chip" aria-pressed={isOpen('licences')} onclick={() => reveal('licences')}>
				<ScrollText size={13} aria-hidden="true" />Licences<span class="sb-n">{licenceTools.filter(savedOn).length}/{licenceTools.length}</span>
			</button>
		{/if}
		<span class="mg-grow"></span>
		<span class="sb-changed" title={changed ? `${changed} changed from the default` : 'Every setting is at its default'}>
			{#if changed}<span class="sb-dot" aria-hidden="true"></span>{changed} changed{:else}All defaults{/if}
		</span>
	</nav>

	<!-- where MARGIE runs: this computer's resources, and the folders to jump to -->
	<div class="sb-here">
		{#if machine}
			<div class="sb-machine" aria-label="This computer">
				<span class="sb-here-t">This computer</span>
				{#if machine.chip}<span class="sb-fact"><Cpu size={14} />{machine.chip}</span>{/if}
				{#if machine.cores}<span class="sb-fact"><b>{machine.cores}</b> cores{budget ? ` | MARGIE may use ${budget}` : ''}</span>{/if}
				{#if machine.memory}<span class="sb-fact"><MemoryStick size={14} /><b>{formatBytes(machine.memory)}</b> memory{ws.setting('LOCAL_MAX_MEMORY_GB') ? ` | MARGIE may use ${ws.setting('LOCAL_MAX_MEMORY_GB')} GB` : ''}</span>{/if}
				{#if machine.diskFree}<span class="sb-fact"><HardDrive size={14} /><b>{formatBytes(machine.diskFree)}</b> free on the databases disk</span>{/if}
			</div>
		{:else if backend.cluster}
			<div class="sb-machine"><span class="sb-here-t">On the HPC{backend.host ? `, ${backend.host}` : ''}</span><span class="sb-fact">Resources are set per job below (SLURM).</span></div>
		{/if}
		{#if backend.cluster}
			<!-- For advanced users: the files behind the settings and the runs, edited by hand once unlocked. -->
			<div class="sb-places" aria-label="Advanced">
				<span class="sb-here-t">Advanced</span>
				{#if filesOpen}
					<a class="sb-place" href={uiBase.to(`/edit?path=${encodeURIComponent(CONFIG_FILE)}&check=yaml`)} title="Edit {CONFIG_FILE} by hand"><FileCode size={13} />Edit config.yaml</a>
					<a class="sb-place" href={uiBase.to(`/edit?path=${encodeURIComponent(WORKFLOW_FILE)}`)} title="Edit {WORKFLOW_FILE} by hand"><FileCode size={13} />Edit the workflow (Snakemake)</a>
					<button type="button" class="sb-place" aria-pressed={restoreAsk === 'config'} onclick={() => (restoreAsk = 'config')}><RotateCcw size={13} />Restore the default config.yaml</button>
					<button type="button" class="sb-place" aria-pressed={restoreAsk === 'workflow'} onclick={() => (restoreAsk = 'workflow')}><RotateCcw size={13} />Restore the default workflow</button>
					<button type="button" class="mg-link quiet" onclick={() => (advanced.set(false), (restoreAsk = ''))}><Lock size={13} aria-hidden="true" />Lock</button>
				{:else}
					<a class="sb-place" href={uiBase.to(`/view?path=${encodeURIComponent(CONFIG_FILE)}`)} title="Read {CONFIG_FILE}"><FileCode size={13} />View config.yaml</a>
					<a class="sb-place" href={uiBase.to(`/view?path=${encodeURIComponent(WORKFLOW_FILE)}`)} title="Read {WORKFLOW_FILE}"><FileCode size={13} />View the workflow (Snakemake)</a>
					<button type="button" class="sb-place" onclick={openFiles}><LockOpen size={13} />Unlock to edit</button>
				{/if}
				<p class="sb-adv-note">
					The buttons and fields below make changes to config.yaml. If you know how to edit Snakemake and config.yaml, unlock the two files to edit them directly here.
					{#if filesOpen}Each save, and each restore, keeps the file it replaces beside it.{/if}
				</p>
				{#if filesOpen && workflowEdited}
					<p class="sb-adv-note mg-note">The workflow has your edits: your copy of MARGIE takes MARGIE's updates again once the default workflow is restored.</p>
				{/if}
				{#if restoreAsk}
					<div class="sb-confirm sb-adv-ask">
						<span class="mg-note">
							{restoreAsk === 'config'
								? 'Replace config.yaml with the default? Every setting goes back to its default; your file is kept beside it.'
								: "Put back MARGIE's workflow? Your edited file is kept beside it."}
						</span>
						<span class="sb-btns">
							<button type="button" class="mg-link quiet" disabled={restoring} onclick={restoreDefault}>{restoring ? 'Restoring…' : 'Restore'}</button>
							<button type="button" class="mg-link quiet" onclick={() => (restoreAsk = '')}>Cancel</button>
						</span>
					</div>
				{/if}
			</div>
		{/if}
		<!-- On the cluster, Files lists these same places. -->
		{#if places.length && !backend.cluster}
			<div class="sb-places" aria-label="Folders">
				<span class="sb-here-t">{backend.cluster ? 'Your folders on the cluster' : 'Folders'}</span>
				{#each places as p (p.path)}
					<a class="sb-place" href={folderHref(p.path)} title="Open {p.path} in Files"><Folder size={13} />{p.label}</a>
				{/each}
				<span class="sb-desc mg-explain">Change where these point under Folders.</span>
			</div>
		{/if}
	</div>

	{#snippet licences()}
			{#if isOpen('licences')}
			<section class="sb-card" id="licences" data-shade="licences" data-help={help.licences ? 'on' : undefined} style="--i: {groups.length}">
				<header class="sb-head">
					<span class="sb-ico" aria-hidden="true"><ScrollText size={14} /></span>
					<h2 class="sb-title">Licences</h2>
					<span class="sb-count">{licenceTools.filter(savedOn).length} of {licenceTools.length} accepted</span>
					{#if licChanged}<span class="sb-pending">unsaved</span>{/if}
					<span class="mg-grow"></span>
					{@render helpButton('licences')}
				</header>
				<div class="sb-body">
					<div class="sb-lic">
						<Explain>
						<p class="sb-desc">
							These tools carry academic or non-commercial terms, and stay off until you accept them. Read each tool's terms in
							<a class="mg-link" href={uiBase.to('/install')}>Install</a>
							first.
						</p>
						</Explain>

						<label class="sb-use">
							<span class="sb-lbl">Intended use</span>
							<input class="mg-input" bind:value={use} placeholder="e.g. academic research at your institution" />
						</label>

						<ul class="sb-tools" use:even={150}>
							{#each licenceTools as s (s.key)}
								<li class:on={!!flags[s.key]}>
									<span class="mg-mono">{toolName(s)}</span>
									<span class="mg-grow"></span>
									<Switch label="Accept the {toolName(s)} licence" checked={!!flags[s.key]} onchange={(on) => (flags[s.key] = on)} />
								</li>
							{/each}
						</ul>

						{#if needsStatement}
							<div class="sb-agree">
								<p class="sb-legal">{LICENCE_LEGAL_NOTICE}</p>
								<label for="licence-statement" class="sb-lbl">Type this statement to accept</label>
								<p class="sb-statement">{LICENCE_STATEMENT}</p>
								<textarea
									id="licence-statement"
									class="mg-input"
									rows="2"
									spellcheck="false"
									autocomplete="off"
									bind:value={typed}
									onpaste={(e) => e.preventDefault()}
								></textarea>
								<span class="sb-desc" class:sb-match={typedOk}
									>{typed ? (typedOk ? 'Matches' : 'Keep typing: it must match the statement above.') : 'Pasting is turned off.'}</span
								>
							</div>
						{/if}

						<div class="sb-end">
							{#if anyOn && !use.trim()}<span class="sb-desc">Describe your intended use first.</span>{/if}
							<button type="button" class="mg-btn small primary" disabled={!canSave} onclick={saveLicences}>
								{needsStatement ? 'Accept and save' : 'Save'}
							</button>
						</div>
					</div>
				</div>
			</section>
			{/if}
	{/snippet}

	<div class="sb-cols" bind:clientWidth={boardWidth} style="--n: {ncols}">
		{#each columns as col, ci (ci)}
			<div class="sb-col">
				{#each col as slot (slot.g?.id ?? 'licences')}
					{#if slot.g}{@render card(slot.g, slot.k)}{:else}{@render licences()}{/if}
				{/each}
			</div>
		{/each}
	</div>

	{#each groups.filter((g) => g.wide) as g, k (g.id)}{@render card(g, k + groups.length)}{/each}
</div>

{#if pickFor}
	{@const value = String(draft[pickFor.key] || pickFor.default || '')}
	<FolderPick
		start={value}
		files={isFilePath(value)}
		title={`${isFilePath(value) ? 'Pick a file' : 'Pick a folder'}: ${pickFor.label}`}
		onpick={(path) => pickFor && (draft[pickFor.key] = path)}
		onclose={() => (pickFor = null)}
	/>
{/if}

<style>
	/* No frame of its own: the chips, where MARGIE runs, and the section shown are boxes side by side. */
	.sb {
		display: flex;
		flex-direction: column;
		gap: var(--cr-stack, 16px);
		color: var(--mg-text);
	}
	.sb-missing {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px 16px;
		padding: 12px 16px;
		border: 1px solid color-mix(in srgb, var(--mg-warn) 45%, var(--mg-border));
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-warn) 7%, var(--cr-card, var(--mg-surface)));
		font-size: var(--mg-fs-sm);
	}
	.sb-missing span {
		flex: 1 1 380px;
	}

	/* ---- the chips along the top ---- */
	/* The chips share the width evenly, the tally of changes as the last one. */
	/* Where MARGIE runs: one line of this computer's resources, one of folders to jump to. */
	.sb-here {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: var(--cr-note-pad, 10px 18px);
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		font-size: var(--mg-fs-sm);
	}
	.sb-here:empty {
		display: none;
	}
	.sb-machine,
	.sb-places {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px 16px;
	}
	.sb-here-t {
		font-size: var(--mg-fs-xs);
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.sb-fact {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--mg-text-2);
	}
	.sb-fact b {
		font-weight: 500;
		color: var(--mg-text);
	}
	.sb-place {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 3px 10px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		color: var(--mg-accent-ink, var(--mg-accent));
		text-decoration: none;
	}
	.sb-place:hover {
		border-color: var(--mg-accent);
	}
	button.sb-place {
		background: none;
		font: inherit;
		cursor: pointer;
	}
	.sb-place[aria-pressed='true'] {
		border-color: var(--mg-accent);
		background: color-mix(in srgb, var(--mg-accent) 8%, transparent);
	}
	/* Advanced: what the fields change, and how to edit the files themselves. */
	.sb-adv-note {
		flex-basis: 100%;
		margin: 2px 0 0;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.sb-adv-ask {
		flex-basis: 100%;
	}
	.sb-nav {
		display: grid;
		grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
		align-items: center;
		gap: 8px;
	}
	.sb-nav > .mg-grow {
		display: none;
	}
	.sb-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 7px;
		min-width: 0;
		white-space: nowrap;
		height: 30px;
		padding: 0 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
		transition:
			border-color 160ms,
			color 160ms,
			transform 160ms;
	}
	.sb-chip[aria-pressed='true'] {
		border-color: var(--mg-accent);
		background: color-mix(in srgb, var(--mg-accent) 10%, var(--mg-surface));
		color: var(--mg-accent-ink, var(--mg-accent));
		font-weight: 600;
	}
	.sb-chip:hover {
		border-color: color-mix(in srgb, var(--mg-accent) 60%, var(--mg-border));
		color: var(--mg-text);
	}
	.sb-chip :global(svg) {
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.sb-n {
		font-size: var(--mg-fs-xs);
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-3);
	}
	.sb-changed {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 7px;
		height: 30px;
		padding: 0 12px;
		border: 1px dashed var(--mg-border-strong);
		border-radius: var(--mg-r-sm);
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.sb-dot {
		display: inline-block;
		flex: none;
		width: 7px;
		height: 7px;
		margin-left: 7px;
		border-radius: 50%;
		background: var(--mg-accent);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-accent) 22%, transparent);
		vertical-align: middle;
	}
	.sb-dot.sb-unsaved {
		background: var(--mg-warn);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-warn) 22%, transparent);
	}
	.sb-pending {
		padding: 1px 8px;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-warn) 16%, transparent);
		color: var(--mg-warn);
		font-size: var(--mg-fs-xs);
		font-weight: 600;
	}
	/* Each section's own Save, at its foot. */
	.sb-save {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 2px;
		padding: 4px var(--cr-box-x, 18px) 14px;
	}
	@media (min-width: 1000px) {
		.sb > .sb-card .sb-sub.sb-sub-fold {
			display: block;
		}
	}
	.sb-changed .sb-dot {
		margin-left: 0;
	}

	/* ---- the cards, in as many columns as fit ---- */
	/* Equal columns; the last card of each stretches so their feet line up. */
	.sb-cols {
		display: grid;
		grid-template-columns: repeat(var(--n, 1), minmax(0, 1fr));
		gap: var(--cr-stack, 16px);
		align-items: stretch;
	}
	.sb-col {
		display: flex;
		flex-direction: column;
		gap: var(--mg-pad);
		min-width: 0;
	}
	.sb-col > .sb-card:last-child {
		flex: 1;
	}
	.sb-card {
		display: flex;
		flex-direction: column;
		min-width: 0;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		transition:
			border-color 200ms,
			box-shadow 600ms;
	}
	.sb-card:global(.flash) {
		border-color: var(--mg-accent);
		box-shadow: 0 0 0 1px var(--mg-accent), 0 8px 26px color-mix(in srgb, var(--mg-accent) 20%, transparent);
	}
	.sb-head {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 12px var(--cr-box-x, 18px);
	}
	.sb-ico {
		display: grid;
		place-items: center;
		width: 24px;
		height: 24px;
		flex: none;
		border-radius: 7px;
		background: color-mix(in srgb, var(--mg-accent) 16%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	/* A small label at the top of the box, as on Home's drawing of the page. */
	.sb-head .sb-title {
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		line-height: 1.2;
		text-transform: uppercase;
		color: var(--mg-text-2);
	}
	.sb-help {
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
	.sb-help:hover,
	.sb-help[aria-pressed='true'] {
		border-color: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.sb-count {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.sb-list {
		display: flex;
		flex-direction: column;
		padding: 0 0 6px;
	}

	/* ---- a setting ---- */
	.sb-cell:global(.flash) {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		transition: none;
	}
	.sb-lbl {
		font-size: var(--mg-fs);
		font-weight: 600;
	}
	.sb-desc {
		max-width: 64ch;
		font-size: var(--mg-fs-xs);
		line-height: 1.45;
		color: var(--mg-text-3);
	}
	.sb-field {
		display: flex;
		align-items: center;
		gap: 10px;
		flex: 1 1 auto;
		min-width: 0;
	}
	.sb-reset {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		flex: none;
		padding: 2px 8px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-xs);
		cursor: pointer;
		transition:
			border-color 160ms,
			color 160ms;
	}
	.sb-reset:hover {
		border-color: var(--mg-accent);
		color: var(--mg-text);
	}
	.sb-reset:hover :global(svg) {
		transform: rotate(-120deg);
	}
	.sb-reset :global(svg) {
		transition: transform 300ms ease;
	}

	/* ---- a phase's settings, side by side ---- */
	.sb-sub {
		padding: 12px var(--cr-box-x, 18px) 14px;
	}
	/* Databases → Backups: folded until opened. */
	.sb-backups > summary {
		display: flex;
		align-items: baseline;
		gap: 10px;
		list-style: none;
		cursor: pointer;
	}
	.sb-backups > summary::-webkit-details-marker {
		display: none;
	}
	.sb-backups > summary::before {
		content: '▸';
		color: var(--mg-text-3);
		transition: transform 120ms ease;
	}
	.sb-backups[open] > summary::before {
		transform: rotate(90deg);
	}
	.sb-backups > summary .sb-subhead {
		margin: 0;
	}
	.sb-backups[open] > summary {
		margin-bottom: 8px;
	}
	.sb-db {
		margin-top: 12px;
	}
	.sb-subhead {
		margin: 0 0 8px;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	/* Two across at most, so long paths stay readable; each cell spans three of the grid's rows
	   (name, field, note), so the fields of a row line up whatever the names' lengths. */
	.sb-cells {
		display: grid;
		grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
		column-gap: 10px;
		row-gap: 4px;
	}
	.sb-cell {
		display: grid;
		grid-row: span 3;
		grid-template-rows: subgrid;
		align-items: end;
		min-width: 0;
		margin-bottom: 4px;
		padding: 7px 10px 8px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-surface) 60%, transparent);
		transition: background-color 1200ms ease;
	}
	.sb-cell-top {
		display: flex;
		align-items: center;
		gap: 6px;
		min-height: 22px;
	}
	.sb-cell .sb-lbl {
		font-size: var(--mg-fs-sm);
	}
	.sb-cell .sb-dot {
		margin-left: 0;
	}

	.sb-num {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		flex: none;
	}
	.sb-num input {
		width: 92px;
		font-variant-numeric: tabular-nums;
	}
	.sb-cell .sb-num input {
		width: 84px;
	}
	.sb-unit {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.sb-short {
		width: 92px;
	}
	.sb-text-in:not(.sb-short) {
		width: 100%;
	}
	.sb-cell .sb-text-in {
		width: 100%;
	}
	.sb-path {
		position: relative;
		display: flex;
		align-items: center;
		width: 100%;
		min-width: 0;
	}
	.sb-folder {
		position: absolute;
		left: 1px;
		top: 1px;
		bottom: 1px;
		z-index: 1;
		display: grid;
		place-items: center;
		width: 34px;
		padding: 0;
		border: none;
		border-radius: var(--mg-r-sm) 0 0 var(--mg-r-sm);
		background: none;
		color: var(--mg-accent-ink, var(--mg-accent));
		cursor: pointer;
	}
	.sb-folder:hover:not(:disabled) {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
	}
	.sb-folder:disabled {
		color: var(--mg-text-3);
		cursor: default;
	}
	.sb-path input {
		width: 100%;
		min-width: 0;
		padding-left: 38px;
		font-size: var(--mg-fs-xs);
	}
	.sb-seg {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 3px;
		padding: 3px;
		border: 1px solid var(--mg-border);
		border-radius: 16px;
		background: var(--mg-surface);
	}
	.sb-seg button {
		height: 26px;
		padding: 0 12px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
		transition:
			background-color 180ms,
			color 180ms;
	}
	.sb-seg button:hover {
		color: var(--mg-text);
	}
	.sb-seg button[aria-checked='true'] {
		background: var(--mg-accent);
		color: var(--mg-on-accent, #fff);
		font-weight: 600;
	}
	.sb-field :global(.mg-select) {
		width: min(100%, 24em);
	}
	.sb-locked {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		flex: 1 1 auto;
		min-width: 0;
		height: var(--mg-ctl-sm, 32px);
		padding: 0 10px;
		border: 1px dashed var(--mg-border-strong);
		border-radius: var(--mg-r-sm);
		color: var(--mg-text-2);
		font-size: var(--mg-fs-xs);
	}
	.sb-locked :global(svg) {
		flex: none;
		color: var(--mg-warn);
	}
	.sb-locked .mg-mono {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.sb-unlock {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		min-width: 0;
	}
	.sb-unlock .mg-input {
		flex: 1 1 auto;
		min-width: 0;
	}
	.sb-confirm {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}
	.sb-btns {
		display: flex;
		gap: 14px;
	}

	/* ---- a wide group as cards: phases three or four to a row, tools two ---- */
	.sb-empty {
		display: none;
	}
	.sb-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 290px), 1fr));
		gap: 10px;
		padding: 14px var(--cr-box-x, 18px) 16px;
	}
	.sb-grid.tools {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px 12px;
	}
	/* A tool's phase, small, at the right of its card's head. */
	.sb-tc-phase {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		overflow: hidden;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-3);
		white-space: nowrap;
		text-overflow: ellipsis;
	}
	/* The group's settings without a phase: one card across the top, its fields at most so wide. */
	.sb-tc-loose {
		grid-column: 1 / -1;
		background: color-mix(in srgb, var(--mg-accent) 4%, var(--mg-surface));
	}
	.sb-tc-loose .sb-tc-fields > .sb-tf {
		flex: 0 1 220px;
	}
	.sb-tc-num {
		display: inline-grid;
		place-items: center;
		flex: none;
		min-width: 20px;
		height: 20px;
		padding: 0 5px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0;
		font-variant-numeric: tabular-nums;
	}
	.sb-tc {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
		padding: 11px 13px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		transition:
			border-color 160ms ease,
			box-shadow 160ms ease;
	}
	.sb-tc:hover {
		border-color: var(--mg-border-strong);
	}
	.sb-tc:focus-within {
		border-color: color-mix(in srgb, var(--mg-accent) 60%, var(--mg-border));
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-accent) 12%, transparent);
	}
	.sb-tc-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}
	.sb-tc-head b {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-sm);
		font-weight: 650;
	}
	/* A phase's few fields side by side; a tool's on a four-column grid, its folder or file
	   finishing the last row (--path-span), so every tool card has the same shape. */
	.sb-tc-fields {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 10px;
	}
	.sb-tc-fields > .sb-tf {
		flex: 1 1 120px;
	}
	.tools .sb-tc-fields {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}
	.tools .sb-tf.path {
		grid-column: span var(--path-span, 4);
	}
	.sb-tf {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
		border-radius: var(--mg-r-sm);
		transition: background-color 1200ms ease;
	}
	.sb-tf:global(.flash) {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		transition: none;
	}
	.sb-tf-lbl {
		display: flex;
		align-items: center;
		gap: 5px;
		min-height: 18px;
		font-size: 10.5px;
		font-weight: 650;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
		white-space: nowrap;
	}
	.sb-tf-lbl > span:first-child {
		overflow: hidden;
		text-overflow: ellipsis;
	}
	/* Fields in a card start at the top, so a one-line box lines up with a path's first line. */
	.sb-tf .sb-field {
		flex: none;
		align-items: flex-start;
	}
	.sb-tf .sb-num {
		display: flex;
		width: 100%;
	}
	.sb-tf .sb-num input,
	.sb-tf .sb-text-in {
		width: 100%;
		min-width: 0;
	}
	/* The field's name carries the unit ("Memory (MB)"). */
	.sb-tf .sb-unit {
		display: none;
	}
	.sb-tf-none .sb-tf-dash {
		display: flex;
		align-items: center;
		height: var(--mg-ctl-sm, 30px);
		padding: 0 10px;
		border: 1px dashed var(--mg-border);
		border-radius: var(--mg-r-sm);
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.sb-path-area {
		display: block;
		width: 100%;
		min-height: var(--mg-ctl-sm, 30px);
		padding: 6px 10px 6px 38px;
		overflow: hidden;
		resize: none;
		line-height: 1.4;
		font-size: var(--mg-fs-xs);
		/* Breaks where a path allows (after - or /) before anywhere else. */
		overflow-wrap: anywhere;
		white-space: pre-wrap;
	}
	.sb-tf .sb-path {
		align-items: flex-start;
	}
	.sb-tf .sb-folder {
		bottom: auto;
		height: calc(var(--mg-ctl-sm, 30px) - 2px);
	}
	.sb-undo {
		display: inline-grid;
		place-items: center;
		width: 18px;
		height: 18px;
		padding: 0;
		border: none;
		border-radius: 999px;
		background: none;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.sb-undo:hover {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.sb-undo :global(svg) {
		transition: transform 300ms ease;
	}
	.sb-undo:hover :global(svg) {
		transform: rotate(-120deg);
	}

	/* ---- a wide group of one field each: even tiles ---- */
	.sb-tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 10px;
		padding: 14px var(--cr-box-x, 18px) var(--mg-pad);
		border-top: 1px solid var(--mg-border);
	}
	.sb-tile-name {
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.sb-tiles .sb-lbl {
		font-weight: 500;
		color: var(--mg-text-2);
	}

	/* ---- licences ---- */
	.sb-lic {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 14px var(--cr-box-x, 18px) var(--mg-pad);
		border-top: 1px solid var(--mg-border);
	}
	.sb-use {
		display: flex;
		flex-direction: column;
		gap: 6px;
		max-width: 520px;
	}
	.sb-tools {
		display: grid;
		grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
		gap: 8px;
	}
	.sb-tools li {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 36px;
		padding: 0 10px 0 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		font-size: var(--mg-fs-sm);
		transition: border-color 200ms;
	}
	.sb-tools li.on {
		border-color: color-mix(in srgb, var(--mg-ok) 55%, var(--mg-border));
	}
	.sb-agree {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 14px 16px;
		border: 1px solid var(--mg-border-strong);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
	}
	.sb-legal {
		font-size: var(--mg-fs-sm);
		font-weight: 600;
	}
	.sb-statement {
		font-size: var(--mg-fs-sm);
		font-style: italic;
		color: var(--mg-text-2);
	}
	.sb-agree textarea {
		width: 100%;
	}
	.sb-match {
		color: var(--mg-ok);
	}
	.sb-end {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 16px;
	}

	/* Full width, a phase's name sits to the left of its settings. */
	@media (min-width: 1000px) {
		.sb > .sb-card .sb-sub:not(.sb-plain) {
			display: grid;
			grid-template-columns: 11em minmax(0, 1fr);
			gap: 16px;
		}
		.sb > .sb-card .sb-subhead {
			margin: 10px 0 0;
		}
	}

	:global([data-motion='off']) .sb * {
		animation: none !important;
		transition: none !important;
	}

	@media (max-width: 1000px) {
		.sb-grid.tools {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	@media (max-width: 520px) {
		.tools .sb-tc-fields {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.tools .sb-tf.path {
			grid-column: 1 / -1;
		}
	}
	@media (max-width: 600px) {
		.sb {
			padding: 10px;
		}
		.sb-nav {
			display: flex;
			flex-wrap: wrap;
		}
		.sb-chip {
			flex: 1 1 auto;
		}
		.sb-changed {
			flex: 1 1 100%;
		}
		.sb-head,
		.sb-sub {
			padding-left: 12px;
			padding-right: 12px;
		}
	}
</style>
