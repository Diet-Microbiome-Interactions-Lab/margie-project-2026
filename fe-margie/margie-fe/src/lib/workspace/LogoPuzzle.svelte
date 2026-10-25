<script lang="ts">
	import { Shuffle, Undo2, Puzzle } from 'lucide-svelte';
	import MargieLogo from './MargieLogo.svelte';
	import { ui } from './ui.svelte';

	/**
	 * Home's logo as a jigsaw. A click breaks it into 3 × 3 pieces scattered round it; a click on a
	 * piece breaks it smaller (up to 8 × 8); a piece dropped near its place snaps in; a double-click
	 * puts it back together, and Shuffle scatters the pieces across the space. Pieces are cut from
	 * the one logo image in the browser, on a pale card, with interlocking tabs (clip-path).
	 */
	let { size = '260px' }: { size?: string } = $props();

	const GRIDS = [3, 4, 5, 6, 7, 8];
	const LOGO = '/home/margie-logo.webp';
	/** Two taps within this many ms make a double-click. */
	const DOUBLE_MS = 300;

	type Piece = { id: number; r: number; c: number; x: number; y: number; z: number; placed: boolean };

	let level = $state(-1);
	let pieces = $state<Piece[]>([]);
	/** Tab direction per inner edge: +1 out of the upper (left) piece, -1 into it. */
	let hEdge: number[][] = [];
	let vEdge: number[][] = [];
	let S = $state(0);
	let area = $state<HTMLElement>();
	let box = $state<HTMLElement>();
	let homing = $state(false);
	let moves = $state(0);
	let started = 0;
	let solved = $state<{ pieces: number; moves: number; time: string } | null>(null);
	let note = $state('');
	let topZ = 1;

	const broken = $derived(level >= 0);
	const n = $derived(broken ? GRIDS[level] : 3);
	const cw = $derived(S / n);
	const pad = $derived(cw * 0.26);
	const placed = $derived(pieces.filter((p) => p.placed).length);
	const calm = $derived(ui.motion === 'off' || (typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches));

	/** One edge of a piece, from (x, y) along (dx, dy); a tab bulges out (b = 1) or in (b = -1). */
	function edge(x: number, y: number, dx: number, dy: number, len: number, b: number): string {
		const end = `L ${x + dx * len} ${y + dy * len}`;
		if (!b) return end;
		const nx = dy * b,
			ny = -dx * b;
		const d = len * 0.02,
			r = len * 0.12;
		const a1 = [x + dx * len * 0.42, y + dy * len * 0.42];
		const a2 = [x + dx * len * 0.58, y + dy * len * 0.58];
		return [
			`L ${a1[0]} ${a1[1]}`,
			`L ${a1[0] + nx * d} ${a1[1] + ny * d}`,
			`A ${r} ${r} 0 1 ${b > 0 ? 1 : 0} ${a2[0] + nx * d} ${a2[1] + ny * d}`,
			`L ${a2[0]} ${a2[1]}`,
			end
		].join(' ');
	}

	/** The outline of piece (r, c), in its own box (the cell plus room for tabs on each side). */
	function outline(r: number, c: number): string {
		const p = pad,
			w = cw;
		const top = r === 0 ? 0 : -hEdge[r - 1][c];
		const right = c === n - 1 ? 0 : vEdge[r][c];
		const bottom = r === n - 1 ? 0 : hEdge[r][c];
		const left = c === 0 ? 0 : -vEdge[r][c - 1];
		return [
			`M ${p} ${p}`,
			edge(p, p, 1, 0, w, top),
			edge(p + w, p, 0, 1, w, right),
			edge(p + w, p + w, -1, 0, w, bottom),
			edge(p, p + w, 0, -1, w, left),
			'Z'
		].join(' ');
	}

	/** Where a piece may go: inside the play area, given in the logo box's coordinates. */
	function bounds() {
		const a = area?.getBoundingClientRect();
		const b = box?.getBoundingClientRect();
		if (!a || !b) return { x0: -S, x1: S * 2, y0: 0, y1: S };
		return {
			x0: a.left - b.left + pad + 4,
			x1: a.right - b.left - cw - pad - 4,
			y0: a.top - b.top + pad + 4,
			y1: a.bottom - b.top - cw - pad - 4
		};
	}
	const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));

	/** Spreads the pieces: near their places after a break, across the whole space on Shuffle. */
	function scatter(wide: boolean) {
		const B = bounds();
		const snap = cw * 0.3;
		for (const p of pieces) {
			if (p.placed && !wide) continue;
			const hx = p.c * cw,
				hy = p.r * cw;
			let x = hx,
				y = hy;
			for (let k = 0; k < 12 && Math.hypot(x - hx, y - hy) < snap * 2.5; k++) {
				if (wide) {
					x = B.x0 + Math.random() * (B.x1 - B.x0);
					y = B.y0 + Math.random() * (B.y1 - B.y0);
				} else {
					const t = Math.random() * Math.PI * 2;
					const d = S * (0.22 + Math.random() * 0.45);
					x = clamp(hx + Math.cos(t) * d * 1.3, B.x0, B.x1);
					y = clamp(hy + Math.sin(t) * d * 0.8, B.y0, B.y1);
				}
			}
			p.x = x;
			p.y = y;
			p.placed = false;
			p.z = ++topZ;
		}
		homing = false;
	}

	/** Breaks the logo into the next grid of pieces and scatters them. */
	async function breakTo(next: number) {
		if (next >= GRIDS.length) {
			note = `${GRIDS[GRIDS.length - 1] ** 2} pieces is the finest cut.`;
			return;
		}
		const m = GRIDS[next];
		hEdge = Array.from({ length: m - 1 }, () => Array.from({ length: m }, () => (Math.random() < 0.5 ? 1 : -1)));
		vEdge = Array.from({ length: m }, () => Array.from({ length: m - 1 }, () => (Math.random() < 0.5 ? 1 : -1)));
		level = next;
		pieces = Array.from({ length: m * m }, (_, i) => ({ id: i, r: Math.floor(i / m), c: i % m, x: (i % m) * (S / m), y: Math.floor(i / m) * (S / m), z: 1, placed: false }));
		moves = 0;
		started = performance.now();
		solved = null;
		note = '';
		blockTapUntil = performance.now() + 350;
		// Let the play area open first, so the pieces have its room to land in.
		await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
		scatter(false);
	}

	/** Puts the pieces back in place, then shows the logo whole again. */
	function together(done = false) {
		homing = !calm;
		for (const p of pieces) {
			p.x = p.c * cw;
			p.y = p.r * cw;
			p.placed = true;
		}
		if (done) {
			const s = Math.round((performance.now() - started) / 1000);
			solved = { pieces: pieces.length, moves, time: `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` };
		}
		setTimeout(() => {
			level = -1;
			pieces = [];
			homing = false;
		}, calm ? 0 : done ? 900 : 650);
	}

	// ---- taps: one breaks smaller, two put it together
	let lastTap = 0;
	let blockTapUntil = 0;
	let pending: ReturnType<typeof setTimeout> | undefined;
	function tap() {
		const now = performance.now();
		if (now < blockTapUntil) return;
		if (now - lastTap < DOUBLE_MS) {
			clearTimeout(pending);
			lastTap = 0;
			together();
			return;
		}
		lastTap = now;
		pending = setTimeout(() => breakTo(level + 1), DOUBLE_MS);
	}

	// ---- dragging
	let drag: { id: number; ox: number; oy: number; sx: number; sy: number; moved: boolean } | null = null;
	function down(e: PointerEvent, p: Piece) {
		if (homing) return;
		e.preventDefault();
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		if (!p.placed) p.z = ++topZ;
		drag = { id: p.id, ox: e.clientX - p.x, oy: e.clientY - p.y, sx: e.clientX, sy: e.clientY, moved: false };
	}
	function move(e: PointerEvent) {
		if (!drag) return;
		const p = pieces[drag.id];
		if (!drag.moved && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) drag.moved = true;
		if (!drag.moved || p.placed) return;
		const B = bounds();
		p.x = clamp(e.clientX - drag.ox, B.x0, B.x1);
		p.y = clamp(e.clientY - drag.oy, B.y0, B.y1);
	}
	function up() {
		if (!drag) return;
		const p = pieces[drag.id];
		const wasDrag = drag.moved && !p.placed;
		drag = null;
		if (!wasDrag) return tap();
		moves += 1;
		const hx = p.c * cw,
			hy = p.r * cw;
		if (Math.hypot(p.x - hx, p.y - hy) < Math.max(10, cw * 0.22)) {
			p.x = hx;
			p.y = hy;
			p.placed = true;
			p.z = 0;
			if (pieces.every((q) => q.placed)) together(true);
		}
	}

	// Keeps the pieces where they were, relative to the logo, when the logo changes size.
	let lastS = 0;
	$effect(() => {
		const s = S;
		if (lastS && s && s !== lastS && pieces.length) {
			const k = s / lastS;
			for (const p of pieces) {
				p.x *= k;
				p.y *= k;
			}
		}
		lastS = s;
	});
</script>

<div class="lp" class:broken>
	<div class="lp-area" bind:this={area} style:height={broken ? `calc(${S}px * ${S < 260 ? 1.9 : 1.5})` : undefined}>
		<h1 class="lp-h1">
			<div class="lp-box" bind:this={box} bind:clientWidth={S} style:width={size}>
				{#if !broken}
					<div
						class="lp-whole"
						role="button"
						tabindex="0"
						aria-label="BSP MARGIE: click to break the logo into a puzzle"
						title="Click to break into a puzzle"
						onclick={() => breakTo(0)}
						onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), breakTo(0))}
					>
						<MargieLogo size="100%" />
					</div>
				{:else}
					<div class="lp-board" role="presentation" onpointerup={tap} aria-hidden="true"></div>
					{#each pieces as p (p.id)}
						<div
							class="lp-piece"
							class:placed={p.placed}
							class:homing
							role="presentation"
							style:width="{cw + pad * 2}px"
							style:height="{cw + pad * 2}px"
							style:transform="translate3d({p.x - pad}px, {p.y - pad}px, 0)"
							style:z-index={p.placed ? 1 : p.z + 1}
							onpointerdown={(e) => down(e, p)}
							onpointermove={move}
							onpointerup={up}
							onpointercancel={() => (drag = null)}
						>
							<div
								class="lp-face"
								style:clip-path="path('{outline(p.r, p.c)}')"
								style:background-size="{S}px {S}px, {S}px {S}px"
								style:background-position="{pad - p.c * cw}px {pad - p.r * cw}px, {pad - p.c * cw}px {pad - p.r * cw}px"
							></div>
						</div>
					{/each}
				{/if}
			</div>
		</h1>
	</div>

	{#if broken || solved}
		<div class="lp-help" role="status">
			{#if solved && !broken}
				<p><b>Solved.</b> {solved.pieces} pieces in {solved.moves} moves | {solved.time}</p>
				<div class="lp-acts">
					<button type="button" class="mg-btn small" onclick={() => breakTo(0)}><Puzzle size={14} /> Play again</button>
					<button type="button" class="mg-btn small" onclick={() => (solved = null)}>Close</button>
				</div>
			{:else}
				<p><b>Put MARGIE back together:</b> drag each piece into its place. {placed} of {pieces.length} in place.</p>
				<p class="lp-tip">Click a piece for smaller pieces | double-click to put it together</p>
				<div class="lp-acts">
					<button type="button" class="mg-btn small" onclick={() => scatter(true)}><Shuffle size={14} /> Shuffle</button>
					<button type="button" class="mg-btn small" onclick={() => breakTo(level + 1)} disabled={level >= GRIDS.length - 1}><Puzzle size={14} /> Smaller pieces</button>
					<button type="button" class="mg-btn small" onclick={() => together()}><Undo2 size={14} /> Put it together</button>
				</div>
				{#if note}<p class="lp-tip">{note}</p>{/if}
			{/if}
		</div>
	{/if}
</div>

<style>
	.lp {
		display: flex;
		flex-direction: column;
		align-items: center;
		align-self: stretch;
		gap: 10px;
	}
	.lp-area {
		position: relative;
		display: flex;
		justify-content: center;
		width: 100%;
		transition: height 380ms cubic-bezier(0.2, 0.7, 0.2, 1);
	}
	.lp-h1 {
		margin: 0;
		line-height: 0;
	}
	.lp-box {
		position: relative;
		aspect-ratio: 1;
	}
	.lp-whole {
		width: 100%;
		height: 100%;
		border-radius: 50%;
		cursor: pointer;
		outline: none;
	}
	.lp-whole:focus-visible {
		box-shadow: 0 0 0 2px var(--mg-accent);
	}
	/* Where the pieces go: the logo, faint, on the card's outline. */
	.lp-board {
		position: absolute;
		inset: 0;
		border: 1px dashed color-mix(in srgb, var(--mg-text) 22%, transparent);
		border-radius: 4px;
		background: url('/home/margie-logo.webp') center / 100% 100% no-repeat;
		opacity: 0.35;
		filter: grayscale(1);
		touch-action: none;
	}
	.lp-piece {
		position: absolute;
		top: 0;
		left: 0;
		filter: drop-shadow(0 2px 3px rgba(16, 24, 40, 0.28));
		cursor: grab;
		touch-action: none;
		user-select: none;
		will-change: transform;
	}
	.lp-piece:active {
		cursor: grabbing;
		filter: drop-shadow(0 6px 10px rgba(16, 24, 40, 0.32));
	}
	.lp-piece.placed {
		filter: none;
		cursor: default;
	}
	.lp-piece.homing {
		transition: transform 600ms cubic-bezier(0.2, 0.7, 0.2, 1);
	}
	.lp-face {
		width: 100%;
		height: 100%;
		background-image: url('/home/margie-logo.webp'), radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--mg-accent) 10%, #fff) 0%, #fff 70%);
		background-repeat: no-repeat;
	}
	:global([data-theme='dark']) .lp-face {
		background-image: url('/home/margie-logo.webp'), radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--mg-accent) 18%, #1d2230) 0%, #1d2230 70%);
	}
	.lp-help {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		max-width: 560px;
		padding: 10px 16px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
		line-height: 1.5;
		text-align: center;
	}
	.lp-help p {
		margin: 0;
	}
	.lp-tip {
		color: var(--mg-text-3);
	}
	.lp-acts {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 8px;
		margin-top: 2px;
	}
	@media (prefers-reduced-motion: reduce) {
		.lp-area,
		.lp-piece.homing {
			transition: none;
		}
	}
	:global([data-motion='off']) .lp-area,
	:global([data-motion='off']) .lp-piece.homing {
		transition: none;
	}
</style>
