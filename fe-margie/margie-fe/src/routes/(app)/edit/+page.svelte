<script lang="ts">
	import { page } from '$app/state';
	import { beforeNavigate } from '$app/navigation';
	import { ArrowLeft, RotateCcw, Save } from 'lucide-svelte';
	import { api, post } from '$lib/api';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * For advanced users: a text file on the cluster edited by hand (?path=), such as config.yaml
	 * or the Snakemake workflow. Saving keeps the version it replaces beside it (<name>.bak-<time>);
	 * a YAML file (?check=yaml, or a .yaml/.yml name) must still parse, or nothing is written.
	 */
	const path = $derived(page.url.searchParams.get('path') ?? '');
	const name = $derived(path.split('/').filter(Boolean).at(-1) ?? path);
	const yamlFile = $derived(page.url.searchParams.get('check') === 'yaml' || /\.ya?ml$/i.test(name));
	const config = $derived(/\/\.config\/bioinformatics-tools\/config\.ya?ml$/.test(path) || path.endsWith('config.yaml'));
	const workflow = $derived(/\.smk$/i.test(name) || name === 'Snakefile');

	let saved = $state('');
	let text = $state('');
	let error = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let lastBackup = $state('');
	const changed = $derived(text !== saved);

	$effect(() => {
		const p = path;
		if (!p) return;
		loading = true;
		error = '';
		api<{ content: string; binary: boolean; truncated: boolean }>(`/files/text?path=${encodeURIComponent(p)}`)
			.then((d) => {
				if (d.binary) error = 'This is not a text file, so it cannot be edited here.';
				else if (d.truncated) error = 'This file is larger than 1 MB, so only its start could be read; edit it from the Terminal.';
				else {
					saved = d.content;
					text = d.content;
				}
			})
			.catch((e) => (error = e instanceof Error ? e.message : String(e)))
			.finally(() => (loading = false));
	});

	async function save() {
		if (!changed || saving) return;
		saving = true;
		try {
			const d = await post<{ path: string; backup: string | null }>('/files/edit', { path, content: text, check: yamlFile ? 'yaml' : null });
			saved = text;
			lastBackup = d.backup ?? '';
			ui.notify(`${name} saved${d.backup ? `; the old version is ${d.backup.split('/').at(-1)}` : ''}`, 'ok');
			// Settings and every page read config.yaml again.
			if (config) await Promise.allSettled([ws.loadSettings(), ws.loadOverview(), ws.loadTools(), ws.loadGenomes()]);
		} catch (e) {
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		} finally {
			saving = false;
		}
	}

	/** Tab indents (two spaces in YAML, four elsewhere) instead of leaving the field; Ctrl or Cmd + S saves. */
	function keys(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
			e.preventDefault();
			save();
			return;
		}
		if (e.key === 'Tab' && !e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey) {
			e.preventDefault();
			const el = e.currentTarget as HTMLTextAreaElement;
			const pad = yamlFile ? '  ' : '    ';
			const [a, b] = [el.selectionStart, el.selectionEnd];
			text = text.slice(0, a) + pad + text.slice(b);
			requestAnimationFrame(() => el.setSelectionRange(a + pad.length, a + pad.length));
		}
	}

	beforeNavigate(({ cancel, type }) => {
		if (type !== 'leave' && changed && !confirm(`${name} has changes that are not saved. Leave without saving them?`)) cancel();
	});
	const lines = $derived(text.split('\n').length);
</script>

<svelte:head><title>Edit {name} | MARGIE</title></svelte:head>
<svelte:window onbeforeunload={(e) => changed && e.preventDefault()} />

<div class="cr-page ed" data-shade="page-edit">
	<div class="cr-head">
		<h1 class="cr-title">Edit {name}</h1>
		<div class="cr-head-acts acts">
			<a class="mg-btn small" href={uiBase.to(config || workflow ? '/settings' : `/files?path=${encodeURIComponent(path.split('/').slice(0, -1).join('/') || '/')}`)}><ArrowLeft size={14} /> Back</a>
			<button type="button" class="mg-btn small" disabled={!changed || saving} onclick={() => (text = saved)}><RotateCcw size={14} /> Discard</button>
			<button type="button" class="mg-btn small primary" disabled={!changed || saving} onclick={save}><Save size={14} /> {saving ? 'Saving…' : 'Save'}</button>
		</div>
	</div>

	<p class="note" class:warn={workflow}>
		<span class="mg-mono">{path}</span>
		{#if config}
			· The settings MARGIE reads; Settings edits the same file. It must stay valid YAML, or it is not saved.
		{:else if workflow}
			· The workflow in your copy of MARGIE on the cluster (~/margie-project-2026): your edits apply to your runs. While it differs from
			MARGIE's, MARGIE does not update your copy (it never overwrites your edits).
		{/if}
		Each save keeps the version it replaces beside it, as <span class="mg-mono">{name}.bak-&lt;date-time&gt;</span>.
		{#if lastBackup}<span class="kept">Last kept: <span class="mg-mono">{lastBackup.split('/').at(-1)}</span></span>{/if}
	</p>

	{#if loading}
		<p class="mg-note">Reading {name}…</p>
	{:else if error}
		<p class="bad">{error}</p>
	{:else}
		<div class="box">
			<textarea
				class="mg-mono"
				bind:value={text}
				spellcheck="false"
				autocapitalize="off"
				autocomplete="off"
				aria-label="Contents of {name}"
				onkeydown={keys}
			></textarea>
			<div class="foot"><span>{lines.toLocaleString('en-US')} lines</span>{#if changed}<span class="dirty">unsaved changes</span>{/if}<span class="mg-grow"></span><span>Ctrl or Cmd + S saves</span></div>
		</div>
	{/if}
</div>

<style>
	.ed {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		padding-bottom: 16px;
	}
	.acts {
		display: flex;
		gap: 8px;
	}
	.note {
		margin: 0 0 10px;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.note.warn {
		color: color-mix(in srgb, var(--mg-warn) 80%, var(--mg-text));
	}
	.kept {
		margin-left: 8px;
		color: var(--mg-ok);
	}
	.box {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-height: 420px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		overflow: hidden;
	}
	textarea {
		flex: 1;
		min-height: 0;
		width: 100%;
		padding: 12px 14px;
		border: none;
		outline: none;
		resize: none;
		background: transparent;
		color: var(--mg-text);
		font-size: 12.5px;
		line-height: 1.55;
		tab-size: 4;
		white-space: pre;
	}
	.foot {
		display: flex;
		gap: 12px;
		padding: 5px 12px;
		border-top: 1px solid var(--mg-border);
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.dirty {
		color: var(--mg-warn);
		font-weight: 600;
	}
	.bad {
		color: var(--mg-danger);
	}
</style>
