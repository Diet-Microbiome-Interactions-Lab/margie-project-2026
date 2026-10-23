<script lang="ts">
	import { RefreshCw } from 'lucide-svelte';

	/** A labelled Refresh button: turns while `run` reads again; the label folds away on a phone. */
	let { run, title = 'Read it again' }: { run: () => Promise<unknown> | unknown; title?: string } = $props();
	let busy = $state(false);

	async function go() {
		busy = true;
		try {
			await run();
		} finally {
			setTimeout(() => (busy = false), 300);
		}
	}
</script>

<button type="button" class="mg-btn small rf" class:busy {title} aria-label="Refresh" disabled={busy} onclick={go}>
	<RefreshCw size={14} />
	<span class="rf-lbl">Refresh</span>
</button>

<style>
	.rf {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		flex: none;
	}
	.rf.busy :global(svg) {
		animation: rf-turn 700ms linear infinite;
	}
	@keyframes rf-turn {
		to {
			transform: rotate(360deg);
		}
	}
	@media (max-width: 560px) {
		.rf-lbl {
			display: none;
		}
	}
	:global([data-motion='off']) .rf.busy :global(svg) {
		animation: none;
	}
</style>
