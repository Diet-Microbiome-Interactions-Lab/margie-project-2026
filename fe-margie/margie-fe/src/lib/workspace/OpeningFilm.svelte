<script lang="ts">
	import { onMount } from 'svelte';
	import { ui } from './ui.svelte';
	import { motionScale } from './prefs';

	/**
	 * One of Home's films in a box its parent sizes: it plays once and holds its last frame, the
	 * MARGIE logo; a click plays it again. It follows the motion and speed settings, read on each
	 * frame (motion off shows the last frame), and redraws with the theme's colours.
	 */
	let { film }: { film: 'dna' | 'circular' | 'confidence' } = $props();

	const FILMS = {
		dna: {
			load: () => import('./dna-formation.js'),
			label: 'Atoms form bases, sugars and phosphates, which join into two strands and a double helix that bends into a circular genome: the MARGIE logo'
		},
		circular: {
			load: () => import('./dna-circular.js'),
			label: 'Atoms swirl in and form nucleotides, which spiral onto a circle as two strands, pair and coil into a circular genome: the MARGIE logo'
		},
		confidence: {
			load: () => import('./genome-confidence.js'),
			label: "A genome's genes gather evidence from the annotation databases and take the colours of their confidence tiers, then close into a genome map around the MARGIE logo"
		}
	} as const;

	let el = $state<HTMLCanvasElement | null>(null);
	let player: { replay(): void; retheme(): void; destroy(): void } | null = null;
	/** Film seconds per second: the inverse of the site's duration scale; 0 with motion off. */
	const rate = () => {
		const k = motionScale(ui.motion, ui.prefs.speed);
		return k > 0 ? 1 / k : 0;
	};

	onMount(() => {
		let gone = false;
		// Loaded here, on the browser only: the films draw on a canvas.
		FILMS[film].load().then((m) => {
			if (gone || !el) return;
			player = m.mount(el, { logoSrc: '/home/margie-logo.webp', dark: () => ui.dark, rate });
		});
		return () => {
			gone = true;
			player?.destroy();
		};
	});

	// A theme or palette change redraws with the page's new colours, once they apply.
	$effect(() => {
		void ui.dark;
		void ui.vars;
		requestAnimationFrame(() => player?.retheme());
	});
</script>

<button type="button" class="film" title="Play again" aria-label="{FILMS[film].label}. Press to play it again." onclick={() => player?.replay()}>
	<canvas bind:this={el} aria-hidden="true"></canvas>
</button>

<style>
	.film {
		all: unset;
		position: relative;
		display: block;
		width: 100%;
		height: 100%;
		cursor: pointer;
		border-radius: var(--mg-r-sm);
	}
	.film:focus-visible {
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
