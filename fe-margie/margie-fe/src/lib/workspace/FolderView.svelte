<script lang="ts" module>
	export interface FolderRoot {
		label: string;
		path: string;
	}

	/** Files and folders copied or cut on the cluster, waiting to be pasted into a folder (kept across folders). */
	const clip = $state<{ op: 'copy' | 'move'; paths: string[] }>({ op: 'copy', paths: [] });
</script>

<script lang="ts">
	import './viewers/tools.css';
	import { uiBase } from './base.svelte';
	import { untrack } from 'svelte';
	import { ArrowUp, Check, ChevronLeft, ChevronRight, ClipboardCopy, ClipboardPaste, Copy, CornerDownLeft, Download, Ellipsis, File, FileArchive, FileCode, FileImage, FilePlus, FileSpreadsheet, FileText, Folder, FolderOpen, FolderPlus, RefreshCw, Scissors, Trash2, X } from 'lucide-svelte';
	import { ApiError, api, fileUrl, formatBytes, post } from '$lib/api';
	import { ui } from './ui.svelte';
	import { pathComplete } from './path-complete';
	import { backend } from './backend.svelte';
	import { ws } from './data.svelte';
	import { ago } from './format';
	import { copyText } from './clipboard';

	/**
	 * File browser drawn as a tree with back, forward, up and a path box; polls while a run writes.
	 * `memory` restores the last folder, `start` opens a given one, `onpick` sends file clicks to a
	 * preview, `here` binds the shown folder (null: the roots), and `fill` takes the parent's height.
	 */
	let {
		roots,
		empty = 'Nothing here yet.',
		memory = '',
		start = '',
		picked = null,
		onpick,
		here = $bindable(null),
		fill = false
	}: {
		roots: FolderRoot[];
		empty?: string;
		memory?: string;
		start?: string;
		picked?: string | null;
		onpick?: (path: string) => void;
		here?: string | null;
		fill?: boolean;
	} = $props();

	interface Entry {
		name: string;
		type: 'file' | 'directory';
		size: number;
		mtime: string;
	}

	/** Current folder; null is the list of roots. */
	let at = $state<{ root: FolderRoot; path: string } | null>(null);
	const current = $derived(at ?? (roots.length === 1 ? { root: roots[0], path: roots[0].path } : null));
	let entries = $state<Entry[]>([]);
	let missing = $state(false);
	let error = $state('');
	let now = $state(Date.now());
	let spinning = $state(false);

	$effect(() => {
		here = current?.path ?? null;
	});

	async function load() {
		const c = current;
		now = Date.now();
		if (!c) return;
		try {
			const d = await api<{ entries: Entry[] }>(`/files?path=${encodeURIComponent(c.path)}`);
			if (current?.path !== c.path) return;
			entries = d.entries;
			missing = false;
			error = '';
		} catch (e) {
			if (current?.path !== c.path) return;
			entries = [];
			missing = e instanceof ApiError && e.status === 404;
			error = missing ? '' : e instanceof Error ? e.message : String(e);
		}
	}

	function refresh() {
		spinning = true;
		load().finally(() => setTimeout(() => (spinning = false), 400));
	}

	/** Returns the closest root that contains a path. */
	function holder(p: string): FolderRoot | undefined {
		let best: FolderRoot | undefined;
		for (const r of roots) {
			const inside = p === r.path || p.startsWith(r.path === '/' ? '/' : r.path + '/');
			if (inside && (!best || r.path.length > best.path.length)) best = r;
		}
		return best;
	}

	// A folder named in the link takes precedence over the remembered one.
	let opened = $state('');
	$effect(() => {
		if (!start || start === opened) return;
		const root = holder(start);
		if (!root) return;
		opened = start;
		saved = null;
		at = { root, path: start };
	});

	// Restores the last folder for this tab once it is listed.
	const storeKey = $derived(`margie.folder.${memory}`);
	let saved: { root: string; path: string } | null = untrack(() => {
		try {
			return memory ? JSON.parse(sessionStorage.getItem(`margie.folder.${memory}`) ?? 'null') : null;
		} catch {
			return null;
		}
	});
	$effect(() => {
		if (!saved) return;
		const root = roots.find((r) => r.path === saved?.root);
		if (!root) return;
		at = { root, path: saved.path };
		saved = null;
	});
	$effect(() => {
		if (!memory || !at) return;
		try {
			sessionStorage.setItem(storeKey, JSON.stringify({ root: at.root.path, path: at.path }));
		} catch {
			// not remembered
		}
	});

	// Stays inside a lone root even as the run creates more.
	$effect(() => {
		if (at === null && roots.length === 1 && !saved && !start) at = { root: roots[0], path: roots[0].path };
	});

	$effect(() => {
		void current?.path;
		load();
	});

	// Polls often while a run is going, rarely otherwise; a hidden tab waits.
	$effect(() => {
		const timer = setInterval(() => document.visibilityState === 'visible' && load(), ws.active ? 3000 : 15000);
		return () => clearInterval(timer);
	});

	const crumbs = $derived.by(() => {
		const c = current;
		if (!c) return [];
		let acc = c.root.path;
		const rest = c.path
			.slice(c.root.path.length)
			.split('/')
			.filter(Boolean)
			.map((seg) => ({ label: seg, path: (acc = `${acc === '/' ? '' : acc}/${seg}`) }));
		return [{ label: c.root.label, path: c.root.path }, ...rest];
	});
	/** Indent depth of the folder's contents. */
	const top = $derived(roots.length > 1 ? 1 : 0);
	const inner = $derived(top + crumbs.length);

	/** Opens files in the current interface's viewer. */
	const viewer = $derived(uiBase.to('/view'));
	// ---- paths outside the roots ----
	// The server does not restrict reads to the roots, so any path can be typed or walked up to.

	/** Builds a root for a path outside every known one. */
	function rootFor(p: string): FolderRoot {
		return holder(p) ?? { label: p.split('/').filter(Boolean).at(-1) || '/', path: p };
	}

	let trail = $state<string[]>([]);
	let step = $state(-1);
	let typed = $state('');

	const canBack = $derived(step > 0);
	const canForward = $derived(step >= 0 && step < trail.length - 1);

	function goto(path: string, remember = true) {
		const p = path.trim();
		if (!p) return;
		at = { root: rootFor(p), path: p };
		typed = p;
		if (remember && trail[step] !== p) {
			// Drops the forward history.
			trail = [...trail.slice(0, step + 1), p];
			step = trail.length - 1;
		}
	}

	/** Opens a folder from outside as a history step. */
	export function go(path: string) {
		goto(path);
	}

	const open = (path: string) => goto(path);

	function back() {
		if (canBack) goto(trail[--step], false);
	}
	function forward() {
		if (canForward) goto(trail[++step], false);
	}

	/** Goes up one folder, even past a root. */
	function up() {
		const p = current?.path;
		if (!p || p === '/') return;
		goto(p.replace(/\/+$/, '').split('/').slice(0, -1).join('/') || '/');
	}

	// Keeps the path box in sync with the shown folder.
	$effect(() => {
		const p = current?.path;
		if (p) typed = p;
	});
	const child = (name: string) => `${current?.path === '/' ? '' : current?.path}/${name}`;
	/** Shortens a path to the part that tells folders apart (".../live/output/x" -> "output/x"). */
	function shortPath(p: string): string {
		const root = ws.resultRoots.outputRoot;
		if (!root || !p.startsWith(root)) return p;
		return root.split('/').filter(Boolean).at(-1) + p.slice(root.length);
	}
	/** True when modified in the last minute. */
	const fresh = (e: Entry) => now - new Date(e.mtime).getTime() < 60_000;

	function iconOf(name: string) {
		if (/\.(tsv|tab|csv|xlsx?|gff3?|gtf)$/i.test(name)) return FileSpreadsheet;
		if (/\.(png|jpe?g|gif|webp|svg|pdf)$/i.test(name)) return FileImage;
		if (/\.(html?|json|ya?ml|py|sh|smk|R|js|ts|toml)$/i.test(name)) return FileCode;
		if (/\.(gz|zip|tar|bz2|xz|tgz|sif)$/i.test(name)) return FileArchive;
		if (/\.(txt|log|md|out|err|stderr|stdout|fa|fna|faa|fasta|ffn|gbk?|gb)$/i.test(name)) return FileText;
		return File;
	}

	// ------------------------------------------------ copy, cut and paste (cluster)
	const nameOf = (p: string) => p.split('/').filter(Boolean).at(-1) ?? p;
	/** Puts a path on the system clipboard (to paste into a terminal, a script or Settings); its button shows a tick for a moment. */
	let copiedPath = $state('');
	let copiedTimer: ReturnType<typeof setTimeout> | undefined;
	async function copyPath(p: string) {
		if (!(await copyText(p))) {
			ui.notify('Could not reach the clipboard', 'error');
			return;
		}
		copiedPath = p;
		clearTimeout(copiedTimer);
		copiedTimer = setTimeout(() => (copiedPath = ''), 1400);
	}

	/** Puts a path on the clipboard to copy or move; the same path again takes it off. */
	function take(op: 'copy' | 'move', path: string) {
		if (clip.op !== op) {
			clip.op = op;
			clip.paths = [path];
		} else clip.paths = clip.paths.includes(path) ? clip.paths.filter((x) => x !== path) : [...clip.paths, path];
	}
	interface Transfer {
		id: string | null;
		state: 'queued' | 'running' | 'done' | 'failed';
		where: 'slurm' | 'login' | null;
		job: string | null;
		results: { source: string; ok: boolean | null; message: string }[];
	}
	/** The paste under way: a job on SLURM (or the login node), followed until it ends. */
	let pasting = $state<Transfer | null>(null);
	const pastedSoFar = $derived(pasting ? pasting.results.filter((r) => r.ok !== null).length : 0);

	/** Copies or moves what is on the clipboard into the folder open here; nothing is overwritten. */
	async function paste() {
		const into = current?.path;
		if (!into || !clip.paths.length || pasting) return;
		const op = clip.op;
		try {
			let d = await post<Transfer>('/files/transfer', { op, sources: clip.paths, into });
			pasting = d;
			while (d.id && (d.state === 'queued' || d.state === 'running')) {
				await new Promise((r) => setTimeout(r, 2000));
				d = await api<Transfer>(`/files/transfer/${d.id}`);
				pasting = d;
			}
			const done = d.results.filter((r) => r.ok);
			const failed = d.results.filter((r) => r.ok === false);
			if (d.state === 'failed') ui.notify(`The ${op === 'copy' ? 'copy' : 'move'} job ended before it started (SLURM job ${d.job}); nothing was ${op === 'copy' ? 'copied' : 'moved'}.`, 'error');
			if (done.length) ui.notify(`${op === 'copy' ? 'Copied' : 'Moved'} ${done.length === 1 ? nameOf(done[0].source) : `${done.length} items`} into ${nameOf(into)}`, 'ok');
			for (const r of failed) ui.notify(`${nameOf(r.source)}: ${r.message}`, 'error');
			// What was moved is gone from where it was; a copy can be pasted again elsewhere.
			if (op === 'move') clip.paths = clip.paths.filter((p) => !done.some((r) => r.source === p));
			await load();
		} catch (e) {
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		} finally {
			pasting = null;
		}
	}

	// ------------------------------------------------ new folders and files (cluster)
	/** A new folder or text file being named in the open folder. */
	let making = $state<'folder' | 'file' | null>(null);
	let newName = $state('');
	let makingBusy = $state(false);
	function startMaking(kind: 'folder' | 'file') {
		making = making === kind ? null : kind;
		newName = '';
	}
	/** Makes a folder (and any above it) or an empty text file; a new file opens in the editor. */
	async function make(kind: 'folder' | 'file', path: string) {
		makingBusy = true;
		try {
			const d = await post<{ path: string; made: boolean }>('/files/make', { path, kind });
			making = null;
			if (kind === 'file') {
				ui.notify(`${nameOf(d.path)} created`, 'ok');
				location.assign(uiBase.to(`/edit?path=${encodeURIComponent(d.path)}`));
				return;
			}
			ui.notify(d.made ? `${nameOf(d.path)} created` : `${nameOf(d.path)} is already there`, 'ok');
			if (current && d.path === current.path) await load();
			else goto(d.path);
		} catch (e) {
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		} finally {
			makingBusy = false;
		}
	}
	$effect(() => {
		void current?.path;
		making = null;
	});

	// ------------------------------------------------ choosing several (cluster)
	/** Rows ticked in this folder, to copy or cut together; Shift-click ticks a run of them. */
	let selected = $state<string[]>([]);
	let lastTicked = -1;
	$effect(() => {
		void current?.path;
		selected = [];
		lastTicked = -1;
		asking = null;
	});
	function tick(e: MouseEvent, k: number, path: string) {
		const on = !selected.includes(path);
		if (e.shiftKey && lastTicked >= 0) {
			const [a, b] = [Math.min(lastTicked, k), Math.max(lastTicked, k)];
			const run = entries.slice(a, b + 1).map((x) => child(x.name));
			selected = on ? [...new Set([...selected, ...run])] : selected.filter((x) => !run.includes(x));
		} else selected = on ? [...selected, path] : selected.filter((x) => x !== path);
		lastTicked = k;
	}
	/** Puts the ticked rows on the clipboard, to copy or to move. */
	function takeSelected(op: 'copy' | 'move') {
		clip.op = op;
		clip.paths = [...selected];
		selected = [];
	}
	/** Every file and folder in this folder, to tick all at once. */
	const everything = $derived(entries.map((x) => child(x.name)));
	/** "3 folders | 12 files, 31 MB" for the folder open, leaving out what is none. */
	const tally = $derived.by(() => {
		const dirs = entries.filter((x) => x.type === 'directory').length;
		const files = entries.filter((x) => x.type !== 'directory');
		const bytes = files.reduce((n, x) => n + (x.size || 0), 0);
		return [
			dirs && `${dirs} folder${dirs === 1 ? '' : 's'}`,
			files.length && `${files.length} file${files.length === 1 ? '' : 's'}${bytes ? `, ${formatBytes(bytes)}` : ''}`
		]
			.filter(Boolean)
			.join(' | ');
	});

	/* A row's actions sit in one menu (the ⋯ beside Download), placed on the screen so a long list
	   cannot clip it and nothing lies over the names. */
	let menu = $state<{ path: string; name: string; dir: boolean; x: number; y: number; up: boolean } | null>(null);
	function openMenu(ev: MouseEvent, path: string, name: string, dir: boolean) {
		if (menu?.path === path) return (menu = null);
		const r = (ev.currentTarget as HTMLElement).getBoundingClientRect();
		const up = r.bottom + 220 > innerHeight;
		menu = { path, name, dir, x: Math.max(8, r.right - 210), y: up ? r.top - 4 : r.bottom + 4, up };
	}
	/** Mounts the menu at the interface's root: the folder view is a size container, which would
	   otherwise place a fixed menu relative to itself rather than the screen. */
	function toRoot(node: HTMLElement) {
		(node.closest('[data-mg-root]') ?? document.querySelector('[data-mg-root]') ?? document.body).appendChild(node);
		return { destroy: () => node.remove() };
	}
	function fromMenu(run: () => void) {
		run();
		menu = null;
	}
	const allTicked = $derived(everything.length > 0 && everything.every((p) => selected.includes(p)));
	function tickAll() {
		selected = allTicked ? [] : [...everything];
		lastTicked = -1;
	}

	// ------------------------------------------------ deleting (cluster)
	/** What waits on a yes before it is deleted. */
	let asking = $state<string[] | null>(null);
	/** The delete under way: a job on the login node, followed until it ends. */
	let deleting = $state<Transfer | null>(null);
	const askingFolders = $derived(asking ? asking.filter((p) => entries.some((x) => x.type === 'directory' && child(x.name) === p)).length : 0);
	function askDelete(paths: string[]) {
		if (paths.length && !deleting) asking = paths;
	}
	/** Deletes what was agreed to, everything in its folders too; the cluster refuses what the account may not delete. */
	async function remove() {
		const paths = asking;
		asking = null;
		if (!paths?.length) return;
		try {
			let d = await post<Transfer>('/files/delete', { paths });
			deleting = d;
			while (d.id && (d.state === 'queued' || d.state === 'running')) {
				await new Promise((r) => setTimeout(r, 1500));
				d = await api<Transfer>(`/files/transfer/${d.id}`);
				deleting = d;
			}
			const done = d.results.filter((r) => r.ok);
			const failed = d.results.filter((r) => r.ok === false);
			if (done.length) ui.notify(`Deleted ${done.length === 1 ? nameOf(done[0].source) : `${done.length} items`}`, 'ok');
			for (const r of failed) ui.notify(`${nameOf(r.source)}: ${r.message}`, 'error');
			const gone = new Set(done.map((r) => r.source));
			selected = selected.filter((p) => !gone.has(p));
			clip.paths = clip.paths.filter((p) => !gone.has(p));
			await load();
		} catch (e) {
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		} finally {
			deleting = null;
		}
	}

	/** Sends a plain click to `onpick`; a modified click opens the file page. */
	function pick(e: MouseEvent, path: string) {
		if (!onpick || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
		e.preventDefault();
		onpick(path);
	}
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key !== 'Escape') return;
		if (menu) menu = null;
		else if (asking) asking = null;
	}}
	onresize={() => (menu = null)}
/>

<div class="fv" class:fill>
	<div class="vw-bar fv-bar">
		<div class="vw-group" role="group" aria-label="History">
			<button type="button" class="vw-btn icon" title="Back" aria-label="Back" disabled={!canBack} onclick={back}><ChevronLeft size={16} /></button>
			<button type="button" class="vw-btn icon" title="Forward" aria-label="Forward" disabled={!canForward} onclick={forward}><ChevronRight size={16} /></button>
			<button type="button" class="vw-btn icon" title="Up one folder" aria-label="Up one folder" disabled={!current || current.path === '/'} onclick={up}
				><ArrowUp size={15} /></button
			>
		</div>
		<form
			class="vw-field fv-where"
			onsubmit={(e) => {
				e.preventDefault();
				goto(typed);
			}}
		>
			<FolderOpen size={15} />
			<input
				bind:value={typed}
				spellcheck="false"
				autocapitalize="off"
				autocorrect="off"
				aria-label="Folder to open"
				placeholder="/path/to/a/folder (Tab completes)"
				use:pathComplete={{ dirs: true }}
				onkeydown={(e) => e.key === 'Escape' && current && (typed = current.path)}
			/>
			{#if typed.trim() && typed.trim() !== current?.path}
				<button type="submit" class="fv-go" title="Open this folder" aria-label="Open this folder"><CornerDownLeft size={14} /></button>
			{/if}
		</form>
		{#if ws.active}<span class="fv-live" title="Updating as the run writes"><i></i>Live</span>{/if}
		{#if backend.cluster && current && !missing}
			<button type="button" class="vw-pill icon" title="New folder here" aria-label="New folder here" aria-pressed={making === 'folder'} onclick={() => startMaking('folder')}><FolderPlus size={15} /></button>
			<button type="button" class="vw-pill icon" title="New text file here" aria-label="New text file here" aria-pressed={making === 'file'} onclick={() => startMaking('file')}><FilePlus size={15} /></button>
		{/if}
		{#if current && !missing}
			<button type="button" class="vw-pill icon" title="Copy this folder's path" aria-label="Copy this folder's path" onclick={() => current && copyPath(current.path)}>
				{#if copiedPath === current.path}<Check size={15} />{:else}<ClipboardCopy size={15} />{/if}
			</button>
		{/if}
		<button type="button" class="vw-pill fv-refresh" class:spin={spinning} title="Read this folder again" aria-label="Refresh" onclick={refresh}
			><RefreshCw size={15} /><span class="fv-lbl">Refresh</span></button
		>
	</div>

	{#if menu}
		{@const m = menu}
		<div class="fv-menu-wrap" use:toRoot>
		<button type="button" class="fv-menu-scrim" aria-label="Close the menu" onclick={() => (menu = null)}></button>
		<div class="fv-menu" class:up={m.up} role="menu" aria-label="{m.name}" style="left: {m.x}px; top: {m.y}px">
			{#if !m.dir || backend.cluster}
				<!-- A folder on the cluster comes zipped (lib/cluster/downloads). -->
				<a role="menuitem" href={fileUrl(m.path)} download onclick={() => (menu = null)}><Download size={14} />{m.dir ? 'Download as a zip' : 'Download'}</a>
			{/if}
			<button type="button" role="menuitem" onclick={() => fromMenu(() => copyPath(m.path))}><ClipboardCopy size={14} />Copy path</button>
			{#if backend.cluster}
				<button type="button" role="menuitem" onclick={() => fromMenu(() => take('copy', m.path))}><Copy size={14} />Copy</button>
				<button type="button" role="menuitem" onclick={() => fromMenu(() => take('move', m.path))}><Scissors size={14} />Cut, to move it</button>
				<button type="button" role="menuitem" class="danger" disabled={!!deleting} onclick={() => fromMenu(() => askDelete([m.path]))}><Trash2 size={14} />Delete</button>
			{/if}
		</div>
		</div>
	{/if}

	{#if backend.cluster && clip.paths.length}
		<!-- What is waiting to be pasted, and where it would go. -->
		<div class="fv-clip" role="status">
			{#if clip.op === 'copy'}<Copy size={14} />{:else}<Scissors size={14} />{/if}
			<span class="fv-clip-what" title={clip.paths.join('\n')}>
				{clip.op === 'copy' ? 'Copy' : 'Move'}
				<b>{clip.paths.length === 1 ? nameOf(clip.paths[0]) : `${clip.paths.length} items`}</b>
				{current ? `into ${nameOf(current.path) || '/'}` : ': open a folder to paste into'}
			</span>
			{#if pasting}
				<span class="fv-clip-job">
					{pasting.where === 'slurm' ? `SLURM job ${pasting.job}${pasting.state === 'queued' ? ', waiting' : ''}` : 'on the login node'}{pasting.results.length > 1 ? ` | ${pastedSoFar} of ${pasting.results.length}` : ''}
				</span>
			{/if}
			<button type="button" class="vw-pill fv-paste" disabled={!current || !!pasting} onclick={paste}><ClipboardPaste size={14} />{pasting ? (clip.op === 'copy' ? 'Copying…' : 'Moving…') : 'Paste here'}</button>
			<button type="button" class="vw-btn icon" title="Clear" aria-label="Clear" disabled={!!pasting} onclick={() => (clip.paths = [])}><X size={14} /></button>
		</div>
	{/if}
	{#if backend.cluster && deleting}
		<div class="fv-clip fv-sel" role="status">
			<Trash2 size={14} />
			<span class="fv-clip-what">
				Deleting <b>{deleting.results.length === 1 ? nameOf(deleting.results[0].source) : `${deleting.results.length} items`}</b>
				{deleting.results.length > 1 ? ` | ${deleting.results.filter((r) => r.ok !== null).length} of ${deleting.results.length} done` : '…'}
			</span>
		</div>
	{:else if backend.cluster && selected.length}
		<!-- The rows ticked here: copy, cut or delete them together. -->
		<div class="fv-clip fv-sel" role="status">
			<span class="fv-clip-what fv-count"><b>{selected.length}</b> of {everything.length} selected</span>
			{#if !allTicked}<button type="button" class="mg-link quiet" onclick={tickAll}>Select all</button>{/if}
			<span class="mg-grow"></span>
			<button type="button" class="vw-pill" title="Copy the selected" onclick={() => takeSelected('copy')}><Copy size={14} /><span class="fv-lbl">Copy</span></button>
			<button type="button" class="vw-pill" title="Cut the selected, to move them" onclick={() => takeSelected('move')}><Scissors size={14} /><span class="fv-lbl">Cut</span></button>
			<button type="button" class="vw-pill fv-danger" title="Delete the selected" onclick={() => askDelete([...selected])}><Trash2 size={14} /><span class="fv-lbl">Delete</span></button>
			<button type="button" class="vw-btn icon" title="Clear the selection" aria-label="Clear the selection" onclick={() => (selected = [])}><X size={14} /></button>
		</div>
	{/if}

	<div class="fv-scroll">
		<ul class="fv-tree" aria-label="Folder">
			{#if roots.length > 1}
				<li class="fv-row fv-crumb" style="--d: 0">
					{#if current}
						<button type="button" class="fv-name" onclick={() => (at = null)}><Folder size={16} /><span>All folders</span></button>
					{:else}
						<span class="fv-name here"><FolderOpen size={16} /><span>All folders</span></span>
					{/if}
				</li>
			{/if}
			{#each crumbs as c, i (c.path)}
				<li class="fv-row fv-crumb" style="--d: {top + i}">
					{#if i === crumbs.length - 1}
						<span class="fv-name here" title={c.path}><FolderOpen size={16} /><span>{c.label}</span></span>
						{#if tally && !missing && !error}<span class="fv-tally" title="In this folder">{tally}</span>{/if}
					{:else}
						<button type="button" class="fv-name" title={c.path} onclick={() => open(c.path)}><Folder size={16} /><span>{c.label}</span></button>
					{/if}
				</li>
			{/each}

			{#if current && making}
					<li class="fv-row fv-note" style="--d: {inner}">
						<form
							class="fv-make"
							onsubmit={(e) => {
								e.preventDefault();
								if (current && newName.trim()) make(making as 'folder' | 'file', child(newName.trim()));
							}}
						>
							{#if making === 'folder'}<FolderPlus size={15} />{:else}<FilePlus size={15} />{/if}
							<!-- svelte-ignore a11y_autofocus -->
							<input
								class="mg-input"
								bind:value={newName}
								placeholder={making === 'folder' ? 'New folder name' : 'new-file.txt'}
								aria-label={making === 'folder' ? 'New folder name' : 'New file name'}
								spellcheck="false"
								autofocus
								onkeydown={(e) => e.key === 'Escape' && (making = null)}
							/>
							<button type="submit" class="vw-pill" disabled={!newName.trim() || newName.includes('/') || makingBusy}>{makingBusy ? 'Creating…' : 'Create'}</button>
							<button type="button" class="vw-btn icon" aria-label="Cancel" onclick={() => (making = null)}><X size={14} /></button>
						</form>
					</li>
			{/if}
			{#if !current}
				{#each roots as r (r.path)}
					<li class="fv-row fv-place" style="--d: {inner}">
						<button type="button" class="fv-name dir" title={r.label} onclick={() => (at = { root: r, path: r.path })}><Folder size={16} /><span>{r.label}</span></button>
						<span class="fv-path" title={r.path}>{shortPath(r.path)}</span>
						<button type="button" class="fv-pcopy" class:done={copiedPath === r.path} title="Copy the path of {r.label}" aria-label="Copy the path of {r.label}" onclick={() => copyPath(r.path)}>
							{#if copiedPath === r.path}<Check size={14} />{:else}<ClipboardCopy size={14} />{/if}
						</button>
					</li>
				{:else}
					<li class="fv-row fv-note" style="--d: {inner}">{empty}</li>
				{/each}
			{:else if error}
				<li class="fv-row fv-note bad" style="--d: {inner}">{error}</li>
			{:else if missing}
				<li class="fv-row fv-note" style="--d: {inner}">
					{#if backend.cluster}
						<span class="fv-missing">
							This folder does not exist yet.
							<button type="button" class="vw-pill" disabled={makingBusy} onclick={() => current && make('folder', current.path)}><FolderPlus size={14} />{makingBusy ? 'Creating…' : 'Create it'}</button>
						</span>
					{:else}
						Not created yet. It appears here when the run writes it.
					{/if}
				</li>
			{:else if !entries.length}
				<li class="fv-row fv-note" style="--d: {inner}">
					Empty so far.
					{#if backend.cluster && !making}
						<button type="button" class="mg-link quiet" onclick={() => startMaking('folder')}>New folder</button>
						<button type="button" class="mg-link quiet" onclick={() => startMaking('file')}>New file</button>
					{/if}
				</li>
			{:else}
				<li class="fv-row fv-cols" style="--d: {inner}">
					{#if backend.cluster}
						<span class="fv-namecell fv-colname">
							<input
								type="checkbox"
								class="fv-tick shown"
								checked={allTicked}
								indeterminate={selected.length > 0 && !allTicked}
								aria-label="Select everything in this folder"
								title={allTicked ? 'Clear the selection' : 'Select everything in this folder'}
								onclick={tickAll}
							/>
							<span aria-hidden="true">Name</span>
						</span>
					{:else}
						<span aria-hidden="true">Name</span>
					{/if}
					<span aria-hidden="true">Size</span><span aria-hidden="true">Modified</span><span></span>
				</li>
				{#each entries as e, k (e.name)}
					{@const p = child(e.name)}
					<li class="fv-row" class:picked={picked === p} class:clipped={clip.paths.includes(p)} class:cut={clip.op === 'move'} class:ticked={selected.includes(p)} style="--d: {inner}">
						<span class="fv-namecell">
							{#if backend.cluster}
								<input type="checkbox" class="fv-tick" class:shown={selected.length > 0} checked={selected.includes(p)} aria-label="Select {e.name}" title="Select (Shift-click for a run)" onclick={(ev) => tick(ev, k, p)} />
							{/if}
							{#if e.type === 'directory'}
								<button type="button" class="fv-name dir" title={e.name} onclick={() => open(p)}><Folder size={16} /><span>{e.name}</span></button>
							{:else}
								{@const Icon = iconOf(e.name)}
								<a class="fv-name" title={e.name} href="{viewer}?path={encodeURIComponent(p)}" aria-current={picked === p ? 'true' : undefined} onclick={(ev) => pick(ev, p)}
									><Icon size={16} /><span>{e.name}</span></a
								>
							{/if}
						</span>
						<span class="fv-size">{e.type === 'directory' ? '' : formatBytes(e.size)}</span>
						<span class="fv-when" class:fresh={fresh(e)} title={new Date(e.mtime).toLocaleString()}>{ago(e.mtime)}</span>
						<span class="fv-acts">
							<button
								type="button"
								class="fv-dl fv-more"
								class:on={menu?.path === p || clip.paths.includes(p) || copiedPath === p}
								title="Download, copy path, copy, cut or delete {e.name}"
								aria-label="More for {e.name}"
								aria-haspopup="menu"
								aria-expanded={menu?.path === p}
								onclick={(ev) => openMenu(ev, p, e.name, e.type === 'directory')}
							>
								{#if copiedPath === p}<Check size={14} />{:else if clip.paths.includes(p)}{#if clip.op === 'copy'}<Copy size={14} />{:else}<Scissors size={14} />{/if}{:else}<Ellipsis size={15} />{/if}
							</button>
						</span>
					</li>
				{/each}
			{/if}
		</ul>
	</div>

	{#if asking}
		<!-- Deleting asks first: what goes, and that it cannot come back. -->
		<div class="fv-ask-back" role="presentation" onclick={() => (asking = null)}></div>
		<div class="fv-ask" role="alertdialog" aria-modal="true" aria-labelledby="fv-ask-t" aria-describedby="fv-ask-d" tabindex="-1">
			<h3 id="fv-ask-t">
				<Trash2 size={16} />
				Delete {asking.length === 1 ? nameOf(asking[0]) : `${asking.length} items`}?
			</h3>
			<p id="fv-ask-d">
				{#if askingFolders}{asking.length === 1 ? 'Everything in it goes too.' : askingFolders === 1 ? 'Everything in the folder goes too.' : 'Everything in the folders goes too.'}{/if}
				Deleted files cannot be recovered.
			</p>
			{#if asking.length > 1}
				<ul class="fv-ask-list">
					{#each asking.slice(0, 6) as p (p)}<li class="mg-mono">{nameOf(p)}</li>{/each}
					{#if asking.length > 6}<li>and {asking.length - 6} more</li>{/if}
				</ul>
			{/if}
			<div class="fv-ask-acts">
				<!-- svelte-ignore a11y_autofocus -->
				<button type="button" class="vw-pill" autofocus onclick={() => (asking = null)}>Cancel</button>
				<button type="button" class="vw-pill fv-danger solid" onclick={remove}><Trash2 size={14} />Delete</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.fv {
		container-type: inline-size;
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-width: 0;
		font-size: var(--mg-fs-sm);
	}
	.fv.fill {
		height: 100%;
		min-height: 0;
	}
	.fv.fill .fv-scroll {
		flex: 1 1 auto;
		min-height: 0;
		overflow: auto;
		margin: 0 -6px;
		padding: 0 6px 6px;
	}

	/* ---- toolbar ---- */
	.fv-bar {
		flex-wrap: nowrap;
	}
	.fv-refresh {
		flex: none;
		gap: 6px;
	}
	@container (max-width: 560px) {
		.fv-bar {
			flex-wrap: wrap;
		}
		.fv-where {
			order: 10;
			flex-basis: 100%;
		}
		.fv-bar > :global(.vw-group) {
			margin-right: auto;
		}
	}
	.fv-where {
		flex: 1 1 auto;
	}
	.fv-where input {
		font-size: var(--mg-fs-xs);
	}
	.fv-go {
		display: grid;
		place-items: center;
		flex-shrink: 0;
		width: 24px;
		height: 24px;
		margin-right: -8px;
		padding: 0;
		border: none;
		border-radius: var(--mg-r-sm);
		background: var(--mg-accent);
		color: var(--mg-on-accent);
		cursor: pointer;
	}
	.fv-live {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		flex-shrink: 0;
		height: 26px;
		padding: 0 10px;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-ok) 14%, transparent);
		color: var(--mg-ok);
		font-size: var(--mg-fs-xs);
		font-weight: 600;
	}
	.fv-live i {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: currentColor;
	}
	.spin :global(svg) {
		animation: fv-turn 500ms ease;
	}

	/* ---- tree ---- */
	.fv-tree {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.fv-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 76px 84px auto;
		align-items: center;
		gap: 12px;
		min-height: 34px;
		padding: 0 6px 0 calc(6px + min(var(--d, 0), 5) * 14px);
		border-radius: var(--mg-r-sm);
		transition: background-color 120ms ease;
	}
	.fv-row:not(.fv-note):hover {
		background: color-mix(in srgb, var(--mg-text) 5%, transparent);
	}
	.fv-row.picked {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		box-shadow: inset 3px 0 0 var(--mg-accent);
	}
	.fv-row.picked:hover {
		background: color-mix(in srgb, var(--mg-accent) 18%, transparent);
	}
	.fv-crumb,
	.fv-note {
		grid-template-columns: minmax(0, 1fr);
	}
	/* The folder open: its name, and what is in it at the right. */
	.fv-crumb:has(.fv-tally) {
		grid-template-columns: minmax(0, 1fr) auto;
	}
	.fv-place {
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) auto;
	}
	.fv-pcopy {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		padding: 0;
		border: none;
		border-radius: var(--mg-r-sm);
		background: transparent;
		color: var(--mg-text-3);
		cursor: pointer;
		opacity: 0.55;
	}
	.fv-row:hover .fv-pcopy,
	.fv-pcopy:focus-visible {
		opacity: 1;
	}
	.fv-pcopy:hover {
		background: color-mix(in srgb, var(--mg-text) 8%, transparent);
		color: var(--mg-text);
	}
	.fv-pcopy.done {
		opacity: 1;
		color: var(--mg-ok);
	}
	/* Vertical guide line per level. */
	.fv-row:not(.fv-crumb) {
		background-image: linear-gradient(var(--mg-border), var(--mg-border));
		background-size: 1px 100%;
		background-position: calc(14px + (min(var(--d, 0), 8) - 1) * 18px) 0;
		background-repeat: no-repeat;
	}
	.fv-row[style*='--d: 0'] {
		background-image: none;
	}
	.fv-name {
		display: flex;
		align-items: center;
		gap: 9px;
		min-width: 0;
		padding: 5px 0;
		border: none;
		background: none;
		color: var(--mg-text);
		font: inherit;
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}
	.fv-name > span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.fv-name :global(svg) {
		flex-shrink: 0;
		color: var(--mg-text-3);
	}
	.fv-name.dir :global(svg),
	.fv-crumb .fv-name :global(svg) {
		color: color-mix(in srgb, var(--mg-accent) 75%, var(--mg-text-3));
		fill: color-mix(in srgb, var(--mg-accent) 18%, transparent);
	}
	.fv-crumb .fv-name {
		color: var(--mg-text-2);
	}
	.fv-crumb button.fv-name:hover {
		color: var(--mg-text);
	}
	.fv-name.here {
		color: var(--mg-text);
		font-weight: 650;
		cursor: default;
	}
	.fv-name.here :global(svg) {
		color: var(--mg-accent);
	}
	a.fv-name:hover,
	.fv-name.dir:hover {
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.fv-row.picked .fv-name {
		color: var(--mg-accent-ink, var(--mg-accent));
		font-weight: 600;
	}
	.fv-row.picked .fv-name :global(svg) {
		color: var(--mg-accent);
	}
	.fv-size,
	.fv-when,
	.fv-path {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		font-variant-numeric: tabular-nums;
		color: var(--mg-text-3);
	}
	.fv-size {
		text-align: right;
	}
	.fv-when.fresh {
		color: var(--mg-ok);
		font-weight: 600;
	}
	.fv-dl {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border-radius: var(--mg-r-sm);
		color: var(--mg-text-3);
		opacity: 0.55;
		transition:
			opacity 120ms ease,
			background-color 120ms ease;
	}
	/* Download and the ⋯ menu each take their own room at the row's end, so nothing lies over the name. */
	.fv-acts {
		display: flex;
		gap: 2px;
		justify-content: flex-end;
	}
	button.fv-dl {
		padding: 0;
		border: none;
		background: none;
		cursor: pointer;
	}
	.fv-row:is(:hover, :focus-within, .picked) :is(a, button).fv-dl {
		opacity: 1;
	}
	.fv-dl:hover {
		background: color-mix(in srgb, var(--mg-text) 8%, transparent);
	}
	.fv-tally {
		padding-left: 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-xs);
		font-weight: 400;
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.fv-menu-scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
		border: none;
		background: transparent;
		cursor: default;
	}
	.fv-menu {
		position: fixed;
		z-index: 61;
		display: flex;
		flex-direction: column;
		width: 210px;
		padding: 4px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: var(--cr-pop-shadow, 0 8px 24px rgb(0 0 0 / 0.14));
	}
	.fv-menu.up {
		transform: translateY(-100%);
	}
	.fv-menu :is(button, a) {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 32px;
		padding: 0 10px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-sm);
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}
	.fv-menu :is(button, a):hover:not(:disabled) {
		background: color-mix(in srgb, var(--mg-text) 7%, transparent);
	}
	.fv-menu button.danger {
		color: var(--mg-danger);
	}
	.fv-menu button.danger:hover:not(:disabled) {
		background: color-mix(in srgb, var(--mg-danger) 12%, transparent);
	}
	.fv-menu button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.fv-dl.on {
		opacity: 1;
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	/* On the clipboard: an outline, dashed when it is to be moved. */
	.fv-row.clipped {
		outline: 1px solid color-mix(in srgb, var(--mg-accent) 55%, transparent);
		outline-offset: -1px;
	}
	.fv-row.clipped.cut {
		outline-style: dashed;
		opacity: 0.75;
	}
	.fv-clip {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0 0 8px;
		padding: 6px 8px 6px 12px;
		border: 1px solid color-mix(in srgb, var(--mg-accent) 40%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 7%, var(--mg-surface));
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: var(--mg-fs-sm);
	}
	.fv-clip-what {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--mg-text-2);
	}
	.fv-make {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.fv-make input {
		flex: 1;
		min-width: 0;
		height: 30px;
	}
	.fv-missing {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}
	.fv-clip-job {
		flex: none;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
		white-space: nowrap;
	}
	.fv-sel {
		color: var(--mg-text-2);
	}
	/* A tick box before each name: shown under the pointer, or for all once one is ticked. */
	.fv-namecell {
		display: flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}
	.fv-namecell > .fv-name {
		flex: 1;
		min-width: 0;
	}
	.fv-tick {
		flex: none;
		width: 14px;
		height: 14px;
		margin: 0;
		accent-color: var(--mg-accent);
		opacity: 0;
		cursor: pointer;
	}
	.fv-tick.shown,
	.fv-tick:checked,
	.fv-tick:focus-visible,
	.fv-row:hover .fv-tick {
		opacity: 1;
	}
	.fv-row.ticked {
		background: color-mix(in srgb, var(--mg-accent) 9%, transparent);
	}
	.fv-clip-what b {
		font-weight: 600;
		color: var(--mg-text);
	}
	:is(a, button).fv-dl:hover {
		background: color-mix(in srgb, var(--mg-accent) 14%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	/* Column headers over a folder's contents. */
	.fv-row.fv-cols {
		min-height: 26px;
		background-image: none;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.fv-row.fv-cols:hover {
		background-color: transparent;
	}
	.fv-cols > span:nth-child(2) {
		text-align: right;
	}
	/* The count of what is ticked never shrinks away; in a narrow tree the buttons keep only their icons. */
	.fv-count {
		flex: none;
	}
	@container (max-width: 460px) {
		.fv-sel {
			gap: 6px;
			padding-left: 10px;
		}
		.fv-sel .fv-lbl {
			display: none;
		}
		.fv-sel .vw-pill {
			min-width: 0;
			padding: 0 7px;
		}
	}
	.fv-cols > span:first-child:not(.fv-colname),
	.fv-colname > span {
		padding-left: 25px;
	}
	.fv-danger {
		color: var(--mg-danger);
	}
	.fv-danger.solid {
		border-color: var(--mg-danger);
		background: var(--mg-danger);
		color: var(--mg-on-accent, #fff);
	}
	/* The question before deleting: a small card over the folder, the folder dimmed behind it. */
	.fv-ask-back {
		position: absolute;
		inset: 0;
		z-index: 20;
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-bg, var(--mg-surface)) 55%, transparent);
	}
	.fv-ask {
		position: absolute;
		top: 52px;
		left: 50%;
		z-index: 21;
		display: flex;
		flex-direction: column;
		gap: 10px;
		width: min(400px, calc(100% - 24px));
		padding: 16px 18px 14px;
		border: 1px solid color-mix(in srgb, var(--mg-danger) 40%, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: 0 12px 32px rgb(0 0 0 / 0.18);
		transform: translateX(-50%);
		animation: fv-pop 140ms ease-out;
	}
	.fv-ask h3 {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		overflow-wrap: anywhere;
		font-size: var(--mg-fs-md, 15px);
		font-weight: 650;
		color: var(--mg-text);
	}
	.fv-ask h3 :global(svg) {
		flex: none;
		color: var(--mg-danger);
	}
	.fv-ask p {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.fv-ask-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		max-height: 150px;
		margin: 0;
		padding: 6px 10px;
		overflow: auto;
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-text) 4%, transparent);
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
		list-style: none;
	}
	.fv-ask-list li {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.fv-ask-acts {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}
	@keyframes fv-pop {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(-6px);
		}
	}
	.fv-note {
		min-height: 40px;
		color: var(--mg-text-3);
	}
	.fv-note.bad {
		color: var(--mg-danger);
	}

	@container (max-width: 560px) {
		.fv-row {
			grid-template-columns: minmax(0, 1fr) 70px auto;
			gap: 8px;
			padding-left: calc(4px + min(var(--d, 0), 6) * 14px);
		}
		.fv-row:not(.fv-crumb) {
			background-position: calc(11px + (min(var(--d, 0), 6) - 1) * 14px) 0;
		}
		.fv-size,
		.fv-cols > span:nth-child(2) {
			display: none;
		}
		.fv-place {
			grid-template-columns: minmax(0, 1fr) auto;
		}
		.fv-path {
			display: none;
		}
	}

	@keyframes fv-turn {
		to {
			transform: rotate(360deg);
		}
	}
	:global([data-motion='off']) .fv * {
		animation: none !important;
		transition: none !important;
	}
</style>
