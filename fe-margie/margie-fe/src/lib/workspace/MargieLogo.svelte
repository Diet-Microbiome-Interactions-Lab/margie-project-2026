<script lang="ts">
	/**
	 * MARGIE's logo as Home and Sign in show it: one full, slow turn as it appears, eased in and
	 * out, then a gentle float and a glow that breathes behind it (held still with float off).
	 * It turns once more under the pointer, or with turn="click", once clockwise on a click and
	 * once anticlockwise on a double-click. Drawn from the 2048 px original at 1024 px, so it
	 * stays sharp on high-density screens.
	 */
	import { ui } from './ui.svelte';

	let { size = '240px', turn = 'hover', float = true }: { size?: string; turn?: 'hover' | 'click'; float?: boolean } = $props();

	let img = $state<HTMLImageElement>();
	/** A click waits this long for a second one, so a double-click turns the other way only. */
	const DOUBLE_MS = 240;
	let pending: ReturnType<typeof setTimeout> | undefined;

	/** One full, smooth turn, clockwise (1) or anticlockwise (-1), unless it is turning already. */
	function spin(way: 1 | -1, ms = 2600) {
		if (!img || ui.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		if (img.getAnimations().some((a) => a.playState === 'running')) return;
		img.animate([{ transform: 'rotate(0deg)' }, { transform: `rotate(${way * 360}deg)` }], { duration: ms, easing: 'cubic-bezier(0.65, 0, 0.35, 1)' });
	}
	function click() {
		clearTimeout(pending);
		pending = setTimeout(() => spin(1, 1500), DOUBLE_MS);
	}
	function doubleClick() {
		clearTimeout(pending);
		spin(-1, 1500);
	}
</script>

{#if turn === 'click'}
	<button
		type="button"
		class="logo click"
		class:still={!float}
		style:width={size}
		aria-label="BSP MARGIE logo: click to turn it, double-click to turn it back"
		title="Click to turn | double-click to turn back"
		onclick={click}
		ondblclick={doubleClick}
	>
		<span class="logo-glow" aria-hidden="true"></span>
		<img bind:this={img} class="logo-img" src="/home/margie-logo.webp" alt="" width="1024" height="1024" draggable="false" />
	</button>
{:else}
	<span class="logo" class:still={!float} role="img" aria-label="BSP MARGIE" style:width={size}>
		<span class="logo-glow" aria-hidden="true"></span>
		<img bind:this={img} class="logo-img" src="/home/margie-logo.webp" alt="" width="1024" height="1024" draggable="false" onpointerenter={() => spin(1)} />
	</span>
{/if}

<style>
	.logo {
		position: relative;
		display: inline-block;
		aspect-ratio: 1;
		animation: logo-float 7s ease-in-out 3.2s infinite alternate;
	}
	.click {
		padding: 0;
		border: none;
		border-radius: 50%;
		background: none;
		cursor: pointer;
		user-select: none;
		-webkit-tap-highlight-color: transparent;
	}
	.click:focus-visible {
		outline: 2px solid var(--mg-accent);
		outline-offset: 4px;
	}
	.logo-img {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		user-select: none;
		animation: logo-in 3.2s cubic-bezier(0.65, 0, 0.35, 1) backwards;
		will-change: transform;
	}
	.logo-glow {
		position: absolute;
		inset: 14%;
		border-radius: 50%;
		background: radial-gradient(circle, color-mix(in srgb, var(--mg-accent) 26%, transparent) 0%, transparent 68%);
		filter: blur(18px);
		animation:
			logo-fade 1.6s ease-out both,
			logo-breathe 5s ease-in-out 1.6s infinite alternate;
	}
	/* Still: the turn as it appears, then it rests. */
	.still {
		animation: none;
	}
	.still .logo-glow {
		animation: logo-fade 1.6s ease-out both;
	}
	@keyframes logo-in {
		from {
			opacity: 0;
			transform: scale(0.82) rotate(-360deg);
		}
		25% {
			opacity: 1;
		}
	}
	@keyframes logo-fade {
		from {
			opacity: 0;
		}
	}
	@keyframes logo-breathe {
		from {
			opacity: 0.55;
			transform: scale(0.94);
		}
		to {
			opacity: 1;
			transform: scale(1.06);
		}
	}
	@keyframes logo-float {
		to {
			transform: translateY(-6px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.logo,
		.logo * {
			animation: none !important;
		}
	}
	:global([data-motion='off']) .logo,
	:global([data-motion='off']) .logo * {
		animation: none !important;
	}
</style>
