<script lang="ts">
	/**
	 * MARGIE's logo as Home and Sign in show it: one full, slow turn as it appears, eased in and
	 * out, then a gentle float and a glow that breathes behind it (held still with float off).
	 * It turns once more under the pointer. With turn="click" it is a fidget ring: a drag turns it
	 * in place and lets it spin on at the hand's speed, slowing as it goes; a click spins it fast,
	 * clockwise right of the centre and anticlockwise left of it, and a click while it spins stops
	 * it. Stopped upright, it settles straight and glows. Drawn from the 2048 px original at
	 * 1024 px, so it stays sharp on high-density screens.
	 */
	import { ui } from './ui.svelte';

	let { size = '240px', turn = 'hover', float = true }: { size?: string; turn?: 'hover' | 'click'; float?: boolean } = $props();

	let img = $state<HTMLImageElement>();
	const calm = () => ui.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches;

	/** One full, smooth turn, clockwise (1) or anticlockwise (-1), unless it is turning already. */
	function spin(way: 1 | -1, ms = 2600) {
		if (!img || ui.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		if (img.getAnimations().some((a) => a.playState === 'running')) return;
		img.animate([{ transform: 'rotate(0deg)' }, { transform: `rotate(${way * 360}deg)` }], { duration: ms, easing: 'cubic-bezier(0.65, 0, 0.35, 1)' });
	}

	// ---- The fidget ring (turn="click")
	/** A click's spin, degrees a second; the fastest a hand can throw it; how fast it slows (per second). */
	const SPIN = 1500;
	const FASTEST = 3200;
	const FRICTION = 0.5;
	/** Degrees either side of upright that count as upright. */
	const UPRIGHT = 8;
	let btn = $state<HTMLButtonElement>();
	let angle = $state(0);
	let win = $state(false);
	let vel = 0;
	let frame = 0;
	let winTimer: ReturnType<typeof setTimeout> | undefined;
	let hand: { last: number; moved: number; wasSpinning: boolean; trail: { t: number; a: number }[] } | null = null;

	const wrap = (d: number) => ((d % 360) + 540) % 360 - 180;
	function pointerAngle(e: PointerEvent): number {
		const r = btn!.getBoundingClientRect();
		return (Math.atan2(e.clientY - (r.top + r.height / 2), e.clientX - (r.left + r.width / 2)) * 180) / Math.PI;
	}
	function spinOn() {
		cancelAnimationFrame(frame);
		let last = performance.now();
		const step = (now: number) => {
			const dt = Math.min(0.05, (now - last) / 1000);
			last = now;
			angle += vel * dt;
			vel *= Math.exp(-FRICTION * dt);
			if (Math.abs(vel) < 12) return settle();
			frame = requestAnimationFrame(step);
		};
		frame = requestAnimationFrame(step);
	}
	/** Stops it; upright, it sets straight and glows. */
	function settle() {
		cancelAnimationFrame(frame);
		vel = 0;
		const off = wrap(angle);
		if (Math.abs(off) > UPRIGHT) return;
		angle -= off;
		win = true;
		clearTimeout(winTimer);
		winTimer = setTimeout(() => (win = false), 2800);
	}
	function down(e: PointerEvent) {
		if (e.button !== 0) return;
		btn!.setPointerCapture(e.pointerId);
		// A touch while it spins stops it, as a finger on a ring does.
		const wasSpinning = vel !== 0;
		cancelAnimationFrame(frame);
		vel = 0;
		hand = { last: pointerAngle(e), moved: 0, wasSpinning, trail: [{ t: performance.now(), a: angle }] };
	}
	function move(e: PointerEvent) {
		if (!hand) return;
		const a = pointerAngle(e);
		const d = wrap(a - hand.last);
		hand.last = a;
		hand.moved += Math.abs(d);
		angle += d;
		const now = performance.now();
		hand.trail = [...hand.trail.filter((x) => now - x.t < 120), { t: now, a: angle }];
	}
	function up(e: PointerEvent) {
		if (!hand) return;
		const h = hand;
		hand = null;
		if (h.moved > 3) {
			// Let go: it spins on at the hand's speed.
			const now = performance.now();
			const first = h.trail[0];
			const dt = (now - first.t) / 1000;
			vel = dt > 0.012 ? Math.max(-FASTEST, Math.min(FASTEST, (angle - first.a) / dt)) : 0;
			if (calm() || Math.abs(vel) < 40) settle();
			else spinOn();
		} else if (h.wasSpinning || calm()) {
			settle();
		} else {
			const r = btn!.getBoundingClientRect();
			vel = (e.clientX >= r.left + r.width / 2 ? 1 : -1) * SPIN;
			spinOn();
		}
	}
	/** From the keyboard: Enter or Space spins it clockwise, or stops it. */
	function key(e: MouseEvent) {
		if (e.detail !== 0) return;
		if (vel !== 0 || calm()) return settle();
		vel = SPIN;
		spinOn();
	}
</script>

{#if turn === 'click'}
	<button
		bind:this={btn}
		type="button"
		class="logo click"
		class:still={!float}
		class:win
		style:width={size}
		aria-label="BSP MARGIE logo, a ring to spin: click to spin it, click again to stop it, or drag to turn it"
		title="Drag to turn it | click to spin it, click again to stop it upright"
		onpointerdown={down}
		onpointermove={move}
		onpointerup={up}
		onpointercancel={() => (hand = null)}
		onclick={key}
	>
		<span class="logo-glow" aria-hidden="true"></span>
		<span class="logo-turn" style:transform="rotate({angle}deg)">
			<img bind:this={img} class="logo-img" src="/home/margie-logo.webp" alt="" width="1024" height="1024" draggable="false" />
		</span>
		{#if win}<span class="logo-win" role="status">Successful!</span>{/if}
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
	.click {
		touch-action: none;
	}
	.logo-turn {
		position: absolute;
		inset: 0;
		will-change: transform;
	}
	/* Stopped upright: a bright glow and the word. */
	.win .logo-glow {
		animation: logo-win 2.8s ease-out both;
		background: radial-gradient(circle, color-mix(in srgb, var(--mg-ok) 55%, transparent) 0%, transparent 70%);
	}
	.logo-win {
		position: absolute;
		left: 50%;
		bottom: -6px;
		padding: 3px 12px;
		border-radius: 999px;
		background: var(--mg-ok);
		color: #fff;
		font-size: var(--cr-fs-meta);
		font-weight: 700;
		white-space: nowrap;
		transform: translateX(-50%);
		animation: logo-fade 0.3s ease-out both;
		pointer-events: none;
	}
	@keyframes logo-win {
		0% {
			opacity: 0.4;
			transform: scale(0.9);
		}
		25% {
			opacity: 1;
			transform: scale(1.22);
		}
		100% {
			opacity: 0.8;
			transform: scale(1.08);
		}
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
