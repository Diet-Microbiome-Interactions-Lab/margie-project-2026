<script lang="ts">
	/**
	 * Picks a folder on the cluster, or a file for a setting that names one: places to start from,
	 * the folder open with what is inside it, up one folder, and a path to type. Settings opens it
	 * from a folder field's icon.
	 */
	import { onMount } from 'svelte';
	import { ArrowUp, ExternalLink, File, Folder, X } from 'lucide-svelte';
	import { api } from '$lib/api';
	import { uiBase } from './base.svelte';

	let {
		start = '',
		files = false,
		title = 'Choose a folder',
		onpick,
		onclose
	}: { start?: string; files?: boolean; title?: string; onpick: (path: string) => void; onclose: () => void } = $props();

	type Entry = { name: string; type: 'file' | 'directory' };
	type Place = { label: string; path: string };

	let dialog = $state<HTMLDialogElement | null>(null);
	let places = $state<Place[]>([]);
	let at = $state('');
	let typed = $state('');
	let entries = $state<Entry[]>([]);
	let picked = $state('');
	let loading = $state(true);
	let problem = $state('');

	const join = (folder: string, name: string) => (folder === '/' ? `/${name}` : `${folder}/${name}`);
	const parent = (p: string) => p.replace(/\/+$/, '').replace(/\/[^/]*$/, '') || '/';
	const looksLikeFile = (p: string) => /\.[a-z0-9]{1,8}$/i.test(p);

	async function open(path: string) {
		loading = true;
		problem = '';
		try {
			const d = await api<{ path?: string; entries: Entry[] }>(`/files?path=${encodeURIComponent(path)}`);
			at = (d.path || path).replace(/\/+$/, '') || '/';
			typed = at;
			picked = '';
			entries = d.entries
				.filter((e) => e.type === 'directory' || files)
				.sort((a, b) => Number(b.type === 'directory') - Number(a.type === 'directory') || a.name.localeCompare(b.name));
		} catch (e) {
			problem = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	}

	function choose() {
		onpick(files ? picked : at);
		dialog?.close();
	}

	onMount(() => {
		dialog?.showModal();
		api<{ places: Place[] }>('/files?places=1')
			.then((d) => (places = d.places ?? []))
			.catch(() => (places = []));
		// Opens at the setting's folder (a file's own folder), else at home.
		const s = start.trim();
		open(s.startsWith('/') || s.startsWith('~') ? (looksLikeFile(s) ? parent(s) : s) : '~').then(() => {
			// A file setting starts with its own file picked.
			if (files && s.startsWith('/') && entries.some((e) => join(at, e.name) === s)) picked = s;
		});
	});
</script>

<dialog
	bind:this={dialog}
	class="fp"
	aria-labelledby="fp-title"
	{onclose}
	onclick={(e) => {
		if (e.target === dialog) dialog?.close();
	}}
>
	<div class="fp-box">
		<header>
			<h2 id="fp-title">{title}</h2>
			<button type="button" class="fp-x" aria-label="Close" onclick={() => dialog?.close()}><X size={16} /></button>
		</header>
		{#if places.length}
			<nav class="fp-places" aria-label="Places">
				{#each places as p (p.path)}
					<button type="button" class:on={at === p.path} title={p.path} onclick={() => open(p.path)}>{p.label}</button>
				{/each}
			</nav>
		{/if}
		<form
			class="fp-path"
			onsubmit={(e) => {
				e.preventDefault();
				open(typed.trim() || at);
			}}
		>
			<button type="button" class="mg-btn small icon" title="Up one folder" aria-label="Up one folder" disabled={at === '/' || loading} onclick={() => open(parent(at))}><ArrowUp size={14} /></button>
			<input class="mg-input mg-mono" aria-label="Folder" spellcheck="false" bind:value={typed} />
			<button type="submit" class="mg-btn small">Go</button>
		</form>
		<ul class="fp-list" aria-busy={loading}>
			{#if loading}
				<li class="fp-note">Reading the folder…</li>
			{:else if problem}
				<li class="fp-note bad">{problem}</li>
			{:else if !entries.length}
				<li class="fp-note">{files ? 'An empty folder.' : 'A folder with files only.'}</li>
			{:else}
				{#each entries as e (e.name)}
					{@const path = join(at, e.name)}
					<li>
						<button
							type="button"
							class:on={picked === path}
							title={e.type === 'directory' ? `Open ${e.name}` : `Pick ${e.name}`}
							onclick={() => (e.type === 'directory' ? open(path) : (picked = path))}
							ondblclick={() => {
								if (e.type === 'file') {
									picked = path;
									choose();
								}
							}}
						>
							{#if e.type === 'directory'}<Folder size={14} />{:else}<File size={14} />{/if}
							<span>{e.name}</span>
						</button>
					</li>
				{/each}
			{/if}
		</ul>
		<footer>
			<a class="mg-link fp-files" href={uiBase.to(`/files?path=${encodeURIComponent(at)}`)}><ExternalLink size={13} />Open in Files</a>
			<span class="mg-grow"></span>
			<button type="button" class="mg-btn small" onclick={() => dialog?.close()}>Cancel</button>
			<button type="button" class="mg-btn small primary" disabled={loading || !!problem || (files && !picked)} onclick={choose}>
				{files ? (picked ? `Choose ${picked.split('/').pop()}` : 'Pick a file') : 'Choose this folder'}
			</button>
		</footer>
	</div>
</dialog>

<style>
	.fp {
		margin: auto;
		width: min(640px, calc(100vw - 32px));
		max-height: min(720px, calc(100vh - 48px));
		padding: 0;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		color: var(--mg-text);
		box-shadow: var(--mg-shadow-lg, 0 18px 48px rgba(0, 0, 0, 0.18));
	}
	.fp::backdrop {
		background: color-mix(in srgb, #000 28%, transparent);
	}
	.fp-box {
		display: flex;
		flex-direction: column;
		gap: 10px;
		max-height: inherit;
		padding: 14px 16px;
	}
	header {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	h2 {
		flex: 1;
		margin: 0;
		font-size: var(--mg-fs);
		font-weight: 650;
	}
	.fp-x {
		display: inline-grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.fp-x:hover {
		background: color-mix(in srgb, var(--mg-text) 7%, transparent);
	}
	.fp-places {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.fp-places button {
		padding: 3px 10px;
		border: 1px solid var(--mg-border);
		border-radius: 999px;
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-xs);
		cursor: pointer;
	}
	.fp-places button.on,
	.fp-places button:hover {
		border-color: var(--mg-accent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.fp-path {
		display: flex;
		gap: 6px;
	}
	.fp-path input {
		flex: 1;
		min-width: 0;
	}
	.fp-list {
		flex: 1 1 auto;
		min-height: 160px;
		max-height: 360px;
		margin: 0;
		padding: 4px;
		overflow: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		list-style: none;
	}
	.fp-list button {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px 8px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text);
		font: inherit;
		font-size: var(--mg-fs-sm);
		text-align: left;
		cursor: pointer;
	}
	.fp-list button span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.fp-list button :global(svg) {
		flex: none;
		color: var(--mg-accent);
	}
	.fp-list button:hover {
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
	}
	.fp-list button.on {
		background: color-mix(in srgb, var(--mg-accent) 12%, transparent);
	}
	.fp-note {
		padding: 10px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-3);
	}
	.fp-note.bad {
		color: var(--mg-danger, #c0392b);
	}
	footer {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.fp-files {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: var(--mg-fs-xs);
	}
</style>
