<script lang="ts">
	import { Check, ClipboardCopy } from 'lucide-svelte';
	import { copyText } from '../clipboard';
	import { ui } from '../ui.svelte';

	/** A small button that puts a path on the system clipboard, to paste into a terminal, a script or Settings. */
	let { path, label = 'Copy path' }: { path: string; label?: string } = $props();
	let done = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	async function copy(e: MouseEvent) {
		// Inside a row that opens or selects on click: only the path is copied.
		e.stopPropagation();
		e.preventDefault();
		if (!(await copyText(path))) {
			ui.notify('Could not reach the clipboard', 'error');
			return;
		}
		done = true;
		clearTimeout(timer);
		timer = setTimeout(() => (done = false), 1400);
	}
</script>

<button type="button" class="cp" class:done title={done ? 'Copied' : `${label}: ${path}`} aria-label="{label}: {path}" onclick={copy}>
	{#if done}<Check size={13} strokeWidth={2.6} />{:else}<ClipboardCopy size={13} strokeWidth={2.2} />{/if}
</button>

<style>
	.cp {
		display: inline-grid;
		flex: none;
		place-items: center;
		width: 24px;
		height: 24px;
		padding: 0;
		border: 1px solid transparent;
		border-radius: var(--mg-r-sm);
		background: transparent;
		color: var(--mg-text-3);
		cursor: pointer;
		transition:
			color 120ms,
			background-color 120ms;
	}
	.cp:hover {
		border-color: var(--mg-border);
		background: var(--mg-surface-2);
		color: var(--mg-text);
	}
	.cp.done {
		color: var(--mg-ok);
	}
</style>
