<script lang="ts">
	/**
	 * A small game for the sign-in page: close a circular genome. The ring holds eight pieces of
	 * double-stranded DNA in the logo's colours, joined by two-base sticky ends; some pieces are
	 * taken out and shuffled into the tray. A piece fits a gap when the rungs at both of its ends
	 * pair (A with T, G with C), as in ligation. Pick a piece, then a gap (or drag it there); a
	 * placed piece goes back to the tray on a click. Any order whose ends all pair closes the ring.
	 */
	import { RotateCcw } from 'lucide-svelte';

	const N = 8;
	const SPAN = 360 / N;
	/** Two helix turns per piece, so each piece has the same shape and the ring turns with it. */
	const TWIST = SPAN / 2;
	/** Strands end where they cross, a quarter turn either side of a junction. */
	const NICK = TWIST / 4;
	const C = 150;
	const R = 114;
	const A = 13;
	const J0 = -90;
	/** A piece's rungs, in degrees from its left junction: its sticky end, then its core. */
	const END = [-2.5, 2.5];
	const CORE = [11.25, 20, 25, 33.75];

	const BASES = ['A', 'T', 'G', 'C'] as const;
	type Base = (typeof BASES)[number];
	const PAIR: Record<Base, Base> = { A: 'T', T: 'A', G: 'C', C: 'G' };
	/** A and T in the logo's green and cyan; G and C in yellow and pink. */
	const COLOUR: Record<Base, string> = { A: '#8CDC28', T: '#14C8F0', G: '#FFC83C', C: '#F2589B' };
	const LEVELS = [
		{ name: 'Easy', out: 3 },
		{ name: 'Medium', out: 5 },
		{ name: 'Hard', out: 8 }
	];

	const rad = (d: number) => (d * Math.PI) / 180;
	const wave = (d: number) => Math.cos((2 * Math.PI * (d - J0)) / TWIST);
	const radius = (strand: 1 | -1, d: number) => R + strand * A * wave(d);
	const at = (d: number, r: number) => [C + r * Math.cos(rad(d)), C + r * Math.sin(rad(d))];
	const xy = (d: number, r: number) => at(d, r).map((v) => v.toFixed(1)).join(' ');

	function strand(s: 1 | -1, from: number, to: number): string {
		const n = Math.round((to - from) / 0.75);
		return 'M' + Array.from({ length: n + 1 }, (_, i) => from + ((to - from) * i) / n).map((d) => xy(d, radius(s, d))).join(' L');
	}
	/** The strand that ends a quarter turn after each junction, and the one that ends a quarter turn before. */
	const TOP = strand(1, J0 + NICK, J0 + SPAN + NICK);
	const BOTTOM = strand(-1, J0 - NICK, J0 + SPAN - NICK);
	/** What a gap answers to: the middle of the ring along the piece. */
	const TARGET = `M${xy(J0, R)} A${R} ${R} 0 0 1 ${xy(J0 + SPAN, R)}`;

	type Rung = { x1: number; y1: number; x2: number; y2: number; colour: string };
	/** Half a rung: from a strand to the middle of the helix, in its base's colour. */
	function half(d: number, s: 1 | -1, base: Base): Rung {
		const [x1, y1] = at(d, radius(s, d));
		const [x2, y2] = at(d, R);
		return { x1, y1, x2, y2, colour: COLOUR[base] };
	}

	let level = $state(3);
	let ends = $state<Base[][]>([]);
	let cores = $state<Base[][]>([]);
	let slots = $state<(number | null)[]>([]);
	let fixed = $state<boolean[]>([]);
	let tray = $state<number[]>([]);
	let picked = $state<number | null>(null);
	let moves = $state(0);
	let took = $state(0);
	let began = 0;

	function shuffle<T>(xs: T[]): T[] {
		const a = [...xs];
		for (let i = a.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[a[i], a[j]] = [a[j], a[i]];
		}
		return a;
	}

	/** A new genome: eight sticky ends, each its own pair of bases, and random cores. */
	function start(out: number) {
		level = out;
		ends = shuffle(BASES.flatMap((x) => BASES.map((y): Base[] => [x, y]))).slice(0, N);
		cores = Array.from({ length: N }, () => CORE.map(() => BASES[Math.floor(Math.random() * 4)]));
		const gone = new Set(shuffle([...Array(N).keys()]).slice(0, out));
		slots = [...Array(N).keys()].map((s) => (gone.has(s) ? null : s));
		fixed = slots.map((p) => p !== null);
		tray = shuffle([...gone]);
		picked = null;
		moves = 0;
		took = 0;
		began = 0;
	}
	start(LEVELS[0].out);

	/** Piece p's rungs where it sits at the top: its left sticky end (bottom halves), its core, its right sticky end (top halves). */
	const shapes = $derived(
		ends.map((_, p): Rung[] => [
			...END.map((o, i) => half(J0 + o, -1, PAIR[ends[p][i]])),
			...CORE.flatMap((o, i) => [half(J0 + o, 1, cores[p][i]), half(J0 + o, -1, PAIR[cores[p][i]])]),
			...END.map((o, i) => half(J0 + SPAN + o, 1, ends[(p + 1) % N][i]))
		])
	);
	/** Each junction: null while a side is empty, else whether its sticky ends pair. */
	const joins = $derived(
		slots.map((b, j) => {
			const a = slots[(j + N - 1) % N];
			return a === null || b === null ? null : ends[(a + 1) % N].join('') === ends[b].join('');
		})
	);
	const placed = $derived(slots.filter((p) => p !== null).length);
	const wrong = $derived(joins.filter((j) => j === false).length);
	const done = $derived(placed === N && wrong === 0);

	function place(s: number) {
		if (picked === null || slots[s] !== null) return;
		const p = picked;
		slots[s] = p;
		tray = tray.filter((q) => q !== p);
		picked = null;
		moves += 1;
		if (!began) began = Date.now();
		if (done) took = Date.now() - began;
	}

	function takeBack(s: number) {
		const p = slots[s];
		if (p === null || fixed[s] || done) return;
		slots[s] = null;
		tray = [...tray, p];
		picked = p;
	}

	const onKey = (e: KeyboardEvent, act: () => void) => {
		if (e.key !== 'Enter' && e.key !== ' ') return;
		e.preventDefault();
		act();
	};
	const time = (ms: number) => {
		const s = Math.max(1, Math.round(ms / 1000));
		return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
	};
	const label = (p: number) => `Piece with ends ${ends[p].join('')} and ${ends[(p + 1) % N].join('')}`;
</script>

{#snippet dna(p: number)}
	{#each shapes[p] as r, i (i)}
		<line x1={r.x1} y1={r.y1} x2={r.x2} y2={r.y2} stroke={r.colour} class="rung" />
	{/each}
	<path d={BOTTOM} class="strand blue" />
	<path d={TOP} class="strand orange" />
{/snippet}

<div class="puzzle">
	<div class="controls">
		<div class="levels" role="radiogroup" aria-label="Level">
			{#each LEVELS as l (l.name)}
				<button type="button" role="radio" aria-checked={level === l.out} onclick={() => start(l.out)}>{l.name}</button>
			{/each}
		</div>
		<button type="button" class="again" onclick={() => start(level)}><RotateCcw size={14} /> New genome</button>
	</div>

	<div class="stage" class:closed={done}>
		<svg class="dial" viewBox="0 0 300 300" role="group" aria-label="The circular genome">
			<g class="turn" class:spin={done}>
				{#each slots as p, s (s)}
					<g transform="rotate({s * SPAN} {C} {C})">
						{#if p === null}
							<path d={BOTTOM} class="ghost" />
							<path d={TOP} class="ghost" />
							<path
								d={TARGET}
								data-slot={s}
								class="target"
								class:ready={picked !== null}
								role="button"
								tabindex="0"
								aria-label="Gap {s + 1}"
								onclick={() => place(s)}
								onkeydown={(e) => onKey(e, () => place(s))}
								ondragover={(e) => e.preventDefault()}
								ondrop={(e) => {
									e.preventDefault();
									place(s);
								}}
							/>
						{:else if fixed[s] || done}
							<g>{@render dna(p)}</g>
						{:else}
							<g class="moved" data-slot={s} role="button" tabindex="0" aria-label="{label(p)}, placed: take it back" onclick={() => takeBack(s)} onkeydown={(e) => onKey(e, () => takeBack(s))}>
								<path d={TARGET} class="hit" />
								{@render dna(p)}
							</g>
						{/if}
					</g>
				{/each}
				{#each joins as ok, j (j)}
					{#if ok !== null}
						{@const [x, y] = at(J0 + j * SPAN, R + A + 11)}
						<circle cx={x} cy={y} r="4.5" class="join" class:ok class:bad={!ok} />
					{/if}
				{/each}
			</g>
			{#if done}
				<text x={C} y={C - 4} class="big">Closed!</text>
				<text x={C} y={C + 18} class="small">{N * (END.length + CORE.length)} bp circle</text>
			{:else}
				<text x={C} y={C - 4} class="big">{placed}/{N}</text>
				<text x={C} y={C + 18} class="small">pieces in place</text>
			{/if}
		</svg>
	</div>

	<p class="status" aria-live="polite">
		{#if done}
			Genome closed in {time(took)} with {moves} moves.
		{:else if wrong}
			Red dots mark ends that pair wrongly: click a piece you placed to take it back.
		{:else if picked !== null}
			Now click a gap in the ring for it.
		{:else}
			Pick a piece, then a gap whose ends it pairs with.
		{/if}
	</p>

	{#if tray.length}
		<div class="tray" aria-label="Pieces to fit">
			{#each tray as p (p)}
				<button
					type="button"
					class="piece"
					class:picked={picked === p}
					draggable="true"
					aria-label={label(p)}
					aria-pressed={picked === p}
					onclick={() => (picked = picked === p ? null : p)}
					ondragstart={(e) => {
						picked = p;
						e.dataTransfer?.setData('text/plain', String(p));
					}}
				>
					<svg viewBox="86 16 128 50" aria-hidden="true"><g transform="rotate({-SPAN / 2} {C} {C})">{@render dna(p)}</g></svg>
				</button>
			{/each}
		</div>
	{/if}

	<p class="legend">
		<span class="pair"><i style:background={COLOUR.A}></i><i style:background={COLOUR.T}></i>A–T</span>
		<span class="pair"><i style:background={COLOUR.G}></i><i style:background={COLOUR.C}></i>G–C</span>
		<span>Ends join where each rung pairs, as the rungs inside a piece do.</span>
	</p>
</div>

<style>
	.puzzle {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		width: 100%;
		max-width: 420px;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: 10px;
	}
	.levels {
		display: inline-flex;
		gap: 2px;
		padding: 3px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-text) 4%, var(--mg-surface));
	}
	.levels button,
	.again {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 12px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--cr-fs-meta);
		font-weight: 500;
		cursor: pointer;
	}
	.levels button[aria-checked='true'] {
		background: var(--mg-seg-sel);
		box-shadow:
			var(--mg-shadow-sm),
			0 0 0 1px var(--mg-border);
		color: var(--mg-accent-ink, var(--mg-text));
		font-weight: 600;
	}
	.again {
		border: 1px solid var(--mg-border);
		background: var(--mg-surface);
	}
	.again:hover {
		color: var(--mg-text);
	}
	.stage {
		position: relative;
		width: min(100%, 300px);
	}
	/* The logo's glow, once the ring closes. */
	.stage::before {
		content: '';
		position: absolute;
		inset: 18%;
		border-radius: 50%;
		background: radial-gradient(circle, color-mix(in srgb, #14c8f0 30%, transparent), transparent 70%);
		filter: blur(16px);
		opacity: 0;
		transition: opacity 600ms ease-out;
	}
	.stage.closed::before {
		opacity: 1;
	}
	.dial {
		position: relative;
		display: block;
		width: 100%;
		height: auto;
		overflow: visible;
	}
	.turn.spin {
		transform-origin: 150px 150px;
		animation: close 2.6s cubic-bezier(0.65, 0, 0.35, 1);
	}
	@keyframes close {
		to {
			transform: rotate(360deg);
		}
	}
	.rung {
		stroke-width: 3.6;
		stroke-linecap: butt;
	}
	.strand {
		fill: none;
		stroke-width: 5.5;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.blue {
		stroke: #1464f0;
	}
	.orange {
		stroke: #f07814;
	}
	.ghost {
		fill: none;
		stroke: var(--mg-border-strong);
		stroke-width: 2.5;
		stroke-dasharray: 3 5;
		stroke-linecap: round;
		pointer-events: none;
	}
	.target {
		fill: none;
		stroke: transparent;
		stroke-width: 44;
		pointer-events: stroke;
		cursor: pointer;
		outline: none;
	}
	.target.ready {
		stroke: color-mix(in srgb, var(--mg-accent) 12%, transparent);
	}
	.target.ready:hover,
	.target:focus-visible {
		stroke: color-mix(in srgb, var(--mg-accent) 24%, transparent);
	}
	.moved {
		cursor: pointer;
		outline: none;
	}
	/* A placed piece answers across its whole width, as a gap does. */
	.hit {
		fill: none;
		stroke: transparent;
		stroke-width: 44;
		pointer-events: stroke;
	}
	.moved:hover,
	.moved:focus-visible {
		filter: drop-shadow(0 0 4px color-mix(in srgb, var(--mg-accent) 70%, transparent));
	}
	.join.ok {
		fill: var(--mg-ok);
	}
	.join.bad {
		fill: var(--mg-danger);
	}
	.big {
		text-anchor: middle;
		fill: var(--mg-text);
		font-size: 26px;
		font-weight: 700;
	}
	.small {
		text-anchor: middle;
		fill: var(--mg-text-3);
		font-size: 12px;
	}
	.status {
		margin: 0;
		min-height: 1.4em;
		font-size: var(--cr-fs-meta);
		color: var(--mg-text-2);
		text-align: center;
	}
	.tray {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 8px;
	}
	.piece {
		display: grid;
		place-items: center;
		width: 104px;
		padding: 4px 6px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		cursor: grab;
		transition:
			transform 120ms ease-out,
			border-color 120ms ease-out;
	}
	.piece:hover {
		transform: translateY(-2px);
	}
	.piece.picked {
		border-color: var(--mg-accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--mg-accent) 30%, transparent);
	}
	.piece svg {
		display: block;
		width: 100%;
		height: auto;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 6px 14px;
		margin: 0;
		font-size: var(--cr-fs-micro);
		color: var(--mg-text-3);
	}
	.pair {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		font-weight: 600;
		color: var(--mg-text-2);
	}
	.pair i {
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}
	.pair i + i {
		margin-right: 3px;
	}
	@media (prefers-reduced-motion: reduce) {
		.turn.spin {
			animation: none;
		}
	}
	:global([data-motion='off']) .turn.spin {
		animation: none;
	}
</style>
