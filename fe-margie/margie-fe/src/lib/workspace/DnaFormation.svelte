<script lang="ts">
	import { onMount } from 'svelte';
	import { ui } from './ui.svelte';

	/**
	 * The DNA film (dna-formation.js) in a box its parent sizes: atoms to a double helix that closes
	 * into the MARGIE logo. It plays once and holds the logo; a click plays it again. With motion off
	 * it shows the last frame.
	 */
	let { label = 'Atoms form bases, sugars and phosphates, which join into two strands, a double helix and a circular genome: the MARGIE logo' }: { label?: string } = $props();

	let el = $state<HTMLCanvasElement | null>(null);
	let film: { replay(): void; retheme(): void; destroy(): void } | null = null;

	onMount(() => {
		let gone = false;
		// Loaded here, on the browser only: the film draws on a canvas.
		import('./dna-formation.js').then((m) => {
			if (gone || !el) return;
			film = m.mount(el, { logoSrc: '/home/margie-logo.webp', dark: () => ui.dark, still: ui.motion === 'off' });
		});
		return () => {
			gone = true;
			film?.destroy();
		};
	});

	// A theme change redraws with the page's new colours, once they apply.
	$effect(() => {
		void ui.dark;
		void ui.vars;
		requestAnimationFrame(() => film?.retheme());
	});
</script>

<button type="button" class="dna" title="Play again" aria-label="{label}. Press to play it again." onclick={() => film?.replay()}>
	<canvas bind:this={el} aria-hidden="true"></canvas>
</button>

<style>
	.dna {
		all: unset;
		position: relative;
		display: block;
		width: 100%;
		height: 100%;
		cursor: pointer;
		border-radius: var(--mg-r-sm);
	}
	.dna:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: 4px;
	}
	canvas {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		display: block;
	}
</style>
