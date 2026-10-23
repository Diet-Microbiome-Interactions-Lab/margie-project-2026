<script lang="ts">
	import { untrack, type Snippet } from 'svelte';
	import { CircleHelp, FolderOpen } from 'lucide-svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { pathComplete } from '$lib/workspace/path-complete';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * A folder setting edited in place (Analyze's folders): the same setting Settings shows, saved
	 * on Enter or on leaving the field, Escape undoing; Tab completes the path, and the folder
	 * opens in Files. With `help`, a ? beside the label opens a few lines on what the folder is.
	 */
	let {
		label,
		key,
		value,
		placeholder = '/path/to/a/folder',
		onsaved,
		help
	}: { label: string; key: string; value: string; placeholder?: string; onsaved?: () => void; help?: Snippet } = $props();
	let helpOpen = $state(false);

	let typed = $state('');
	let saving = $state(false);
	$effect(() => {
		const now = value;
		untrack(() => {
			if (!saving) typed = now;
		});
	});

	async function save() {
		const next = typed.trim();
		if (!next || next === value) {
			typed = value;
			return;
		}
		saving = true;
		const ok = await ws.saveSettings({ [key]: next });
		saving = false;
		ui.notify(ok ? `${label} saved` : `${label}: that folder could not be used`, ok ? 'ok' : 'error');
		if (ok) onsaved?.();
		else typed = value;
	}
</script>

<label class="ff">
	<span class="ff-lbl">
		{label}
		{#if value}<a class="ff-open" href={uiBase.to(`/files?path=${encodeURIComponent(value)}`)} title="Open {value} in Files" aria-label="Open {label} in Files"><FolderOpen size={13} /></a>{/if}
		{#if help}
			<button type="button" class="ff-q" aria-expanded={helpOpen} aria-label="What is this folder?" title="What is this folder?" onclick={(e) => (e.preventDefault(), (helpOpen = !helpOpen))}
				><CircleHelp size={14} /></button
			>
		{/if}
	</span>
	<input
		class="mg-input mg-mono"
		bind:value={typed}
		{placeholder}
		spellcheck="false"
		autocomplete="off"
		disabled={saving}
		title="{value || placeholder}. Enter or leaving the field saves it; Tab completes the path."
		use:pathComplete={{ dirs: true }}
		onblur={save}
		onkeydown={(e) => {
			if (e.key === 'Enter') e.currentTarget.blur();
			if (e.key === 'Escape') {
				typed = value;
				e.currentTarget.blur();
			}
		}}
	/>
</label>
{#if help && helpOpen}
	<div class="ff-help" role="note">{@render help()}</div>
{/if}

<style>
	.ff-q {
		display: inline-grid;
		place-items: center;
		width: 20px;
		height: 20px;
		padding: 0;
		border: none;
		border-radius: 50%;
		background: transparent;
		color: var(--mg-text-3);
		cursor: pointer;
	}
	.ff-q:hover,
	.ff-q[aria-expanded='true'] {
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.ff-help {
		grid-column: 1 / -1;
		margin-top: 6px;
		padding: 10px 12px;
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.ff-help :global(p) {
		margin: 0 0 6px;
	}
	.ff-help :global(p:last-child) {
		margin-bottom: 0;
	}
	.ff {
		display: flex;
		flex-direction: column;
		gap: 5px;
		min-width: 0;
	}
	.ff-lbl {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-2);
	}
	.ff-open {
		display: inline-flex;
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.ff input {
		width: 100%;
		height: 36px;
	}
</style>
