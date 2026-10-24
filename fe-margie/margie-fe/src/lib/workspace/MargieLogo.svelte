<script lang="ts">
	/**
	 * MARGIE's logo as Home and Sign in show it: one full, slow turn as it appears, eased in and
	 * out, then a gentle float and a glow that breathes behind it; a pointer over it turns it once
	 * more. Drawn from the 2048 px original at 1024 px, so it stays sharp on high-density screens.
	 */
	import { ui } from './ui.svelte';

	let { size = '240px' }: { size?: string } = $props();

	/** One more full, smooth turn under the pointer (not while one is turning). */
	function spinOnce(e: PointerEvent) {
		const img = e.currentTarget as HTMLElement;
		if (ui.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		if (img.getAnimations().some((a) => a.playState === 'running')) return;
		img.animate([{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }], { duration: 2600, easing: 'cubic-bezier(0.65, 0, 0.35, 1)' });
	}
</script>

<span class="logo" role="img" aria-label="BSP MARGIE" style:width={size}>
	<span class="logo-glow" aria-hidden="true"></span>
	<img class="logo-img" src="/home/margie-logo.webp" alt="" width="1024" height="1024" draggable="false" onpointerenter={spinOnce} />
</span>

<style>
	.logo {
		position: relative;
		display: inline-block;
		aspect-ratio: 1;
		animation: logo-float 7s ease-in-out 3.2s infinite alternate;
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
