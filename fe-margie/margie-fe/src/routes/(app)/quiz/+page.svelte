<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { Lock, RotateCcw, Shuffle } from 'lucide-svelte';
	import { ui } from '$lib/workspace/ui.svelte';
	import { QUESTIONS, shuffled } from '$lib/quiz/bank';
	import { UNLOCK } from '$lib/quiz/unlock';
	import Sci from '$lib/quiz/Sci.svelte';
	import { KINDS, LEVELS, TOPICS, type Level, type Question, type Topic } from '$lib/quiz/types';

	/**
	 * Quizzes on bacterial and archaeal physiology, metabolism, energetics, applied bioinformatics and
	 * the gut microbiome. One unlock question opens them for the account; each answer shows why. Answers and
	 * filters are kept in this browser. A filter row with nothing picked leaves its questions in.
	 */

	const ANSWERS = 'margie.quiz.answers';
	// v2: rows start with nothing picked; earlier saves had each option picked.
	const FILTERS = 'margie.quiz.filters.v2';
	const GATE = 'margie.quiz.gate';

	function load<T>(key: string, fallback: T, store: 'local' | 'session' = 'local'): T {
		try {
			const raw = (store === 'local' ? localStorage : sessionStorage).getItem(key);
			return raw ? (JSON.parse(raw) as T) : fallback;
		} catch {
			return fallback;
		}
	}
	function save(key: string, value: unknown, store: 'local' | 'session' = 'local') {
		try {
			(store === 'local' ? localStorage : sessionStorage).setItem(key, JSON.stringify(value));
		} catch {
			// Storage blocked: the quiz still works, without remembering.
		}
	}

	// ------------------------------------------------ the unlock question
	/** This session's order of the unlock questions, and the one asked now. */
	const gate = $state(load<{ order: number[]; at: number }>(GATE, { order: shuffled(UNLOCK.map((_, k) => k)), at: 0 }, 'session'));
	$effect(() => save(GATE, $state.snapshot(gate), 'session'));
	const ask = $derived(UNLOCK[gate.order[gate.at % gate.order.length]]);
	let gatePick = $state<number | null>(null);

	function answerGate(k: number) {
		if (gatePick !== null) return;
		gatePick = k;
		if (k === ask.answer) {
			ui.update({ quizOpen: true });
			ui.notify('Quizzes are open. Enjoy!', 'ok');
		}
	}
	function anotherGate() {
		gatePick = null;
		gate.at = (gate.at + 1) % gate.order.length;
	}

	// ------------------------------------------------ which questions
	const saved = load<{ topics: Topic[]; levels: Level[]; kinds: Question['kind'][] }>(FILTERS, { topics: [], levels: [], kinds: [] });
	// The topics that have questions in the banks.
	const SHOWN = TOPICS.filter((t) => QUESTIONS.some((q) => q.topic === t.id));
	// ?topic=<id> (the FAQ links to ?topic=margie) starts on that topic alone.
	const asked = SHOWN.find((t) => t.id === page.url.searchParams.get('topic'))?.id;
	let topics = $state<Topic[]>(asked ? [asked] : saved.topics);
	let levels = $state<Level[]>(saved.levels);
	let kinds = $state<Question['kind'][]>(saved.kinds);
	$effect(() => save(FILTERS, { topics: $state.snapshot(topics), levels: $state.snapshot(levels), kinds: $state.snapshot(kinds) }));

	function flip<T>(list: T[], v: T): T[] {
		return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
	}
	/** A row with nothing picked lets each of its options through. */
	const lets = <T,>(picked: T[], v: T) => !picked.length || picked.includes(v);
	const picked = $derived(topics.length + levels.length + kinds.length > 0);
	function clearPicks() {
		topics = [];
		levels = [];
		kinds = [];
	}

	const pool = $derived(QUESTIONS.filter((q) => lets(topics, q.topic) && lets(levels, q.level) && lets(kinds, q.kind)));
	let answers = $state<Record<string, boolean>>(load(ANSWERS, {}));
	$effect(() => save(ANSWERS, $state.snapshot(answers)));
	const done = $derived(pool.filter((q) => q.id in answers));
	const right = $derived(done.filter((q) => answers[q.id]).length);

	// The pool in a shuffled order, unanswered first; a new order whenever the choices change.
	let order = $state<string[]>([]);
	let at = $state(0);
	$effect(() => {
		const ids = pool.map((q) => q.id);
		// Answering does not reorder the questions; only a change of choices does.
		const had = untrack(() => answers);
		order = [...shuffled(ids.filter((id) => !(id in had))), ...shuffled(ids.filter((id) => id in had))];
		at = 0;
		untrack(() => fresh(QUESTIONS.find((x) => x.id === order[0])));
	});
	const q = $derived(QUESTIONS.find((x) => x.id === order[at]));

	// ------------------------------------------------ answering one
	let pick = $state<number | boolean | null>(null);
	/** Match: which right-hand item (by index into `rights`) sits by each left one. */
	let placed = $state<(number | null)[]>([]);
	let holding = $state<number | null>(null);
	let checked = $state(false);
	/** Case study: the pick for each part. */
	let parts = $state<(number | null)[]>([]);
	let rights = $state<number[]>([]);
	/** Whether this attempt was right, once answered. */
	let gotIt = $state<boolean | null>(null);

	/** Clears the answer state for question `cur`, in the same step that shows it. */
	function fresh(cur: Question | undefined) {
		pick = null;
		checked = false;
		holding = null;
		placed = cur?.kind === 'match' ? cur.pairs.map(() => null) : [];
		rights = cur?.kind === 'match' ? shuffled(cur.pairs.map((_, k) => k)) : [];
		parts = cur?.kind === 'case' ? cur.parts.map(() => null) : [];
		gotIt = null;
	}
	/** Moves to question `k` of the order. */
	function goTo(k: number) {
		at = k;
		fresh(QUESTIONS.find((x) => x.id === order[k]));
	}

	/** Keeps the latest attempt at each question, for the score. */
	function record(ok: boolean) {
		if (!q) return;
		gotIt = ok;
		answers = { ...answers, [q.id]: ok };
	}
	function choose(k: number | boolean) {
		if (!q || pick !== null) return;
		pick = k;
		if (q.kind === 'choice') record(k === q.answer);
		if (q.kind === 'truefalse') record(k === q.answer);
	}
	function place(slot: number, item: number) {
		if (checked) return;
		const next = placed.map((p) => (p === item ? null : p));
		next[slot] = item;
		placed = next;
		holding = null;
	}
	function unplace(slot: number) {
		if (!checked) placed = placed.map((p, k) => (k === slot ? null : p));
	}
	function checkMatch() {
		if (q?.kind !== 'match') return;
		checked = true;
		record(placed.every((p, k) => p === k));
	}
	function choosePart(i: number, k: number) {
		if (q?.kind !== 'case' || parts[i] !== null) return;
		const next = [...parts];
		next[i] = k;
		parts = next;
		if (next.every((p) => p !== null)) record(q.parts.every((p, j) => next[j] === p.answer));
	}
	const answered = $derived(
		!q ? false : q.kind === 'match' ? checked : q.kind === 'case' ? parts.every((p) => p !== null) : pick !== null
	);

	function next() {
		goTo((at + 1) % Math.max(1, order.length));
	}
	function reshuffle() {
		order = shuffled(order);
		goTo(0);
	}
	function startOver() {
		if (!confirm('Clear your answers and score on this browser?')) return;
		answers = {};
		order = shuffled(order);
		goTo(0);
	}
	const levelWord: Record<Level, string> = { easy: 'Easy', intermediate: 'Intermediate', hard: 'Hard' };
	const topicWord = (t: Topic) => TOPICS.find((x) => x.id === t)?.label ?? t;
	const kindWord = (k: Question['kind']) => KINDS.find((x) => x.id === k)?.label ?? k;
</script>

<svelte:head><title>Quizzes | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-quiz">
	<div class="cr-head">
		<h1 class="cr-title">Quizzes</h1>
		<p class="cr-lede">
			Bacterial and archaeal physiology, metabolism, applied bioinformatics, the gut microbiome and how MARGIE works, at three levels.
			Each answer shows why.
		</p>
		{#if ui.prefs.quizOpen}<span class="cr-meta">{right} right of {done.length} answered | {pool.length} chosen</span>{/if}
	</div>

	{#if !ui.prefs.quizOpen}
		<!-- ------------------------------------------------ the unlock question -->
		<section class="qz-card qz-gate" aria-labelledby="qz-gate-h">
			<span class="qz-lock" aria-hidden="true"><Lock size={20} strokeWidth={1.75} /></span>
			<h2 id="qz-gate-h">Answer one to open the quizzes</h2>
			<p class="qz-q"><Sci text={ask.question} /></p>
			<ul class="qz-options">
				{#each ask.options as o, k (k)}
					<li>
						<button
							type="button"
							class="qz-opt"
							class:right={gatePick !== null && k === ask.answer}
							class:wrong={gatePick === k && k !== ask.answer}
							disabled={gatePick !== null}
							onclick={() => answerGate(k)}><Sci text={o} /></button
						>
					</li>
				{/each}
			</ul>
			{#if gatePick !== null}
				<p class="qz-why" class:ok={gatePick === ask.answer}>
					<b>{gatePick === ask.answer ? 'Right!' : 'Not quite.'}</b>
					<Sci text={ask.explain} />
				</p>
				{#if gatePick !== ask.answer}
					<button type="button" class="mg-btn" onclick={anotherGate}>Try another question</button>
				{/if}
			{:else}
				<button type="button" class="mg-link quiet" onclick={anotherGate}>Ask me a different one</button>
			{/if}
		</section>
	{:else}
		<!-- ------------------------------------------------ choosing -->
		<div class="qz-filters">
			<div class="qz-group" role="group" aria-label="Topics">
				{#each SHOWN as t (t.id)}
					<button type="button" class="qz-chip" aria-pressed={topics.includes(t.id)} onclick={() => (topics = flip(topics, t.id))}>{t.label}</button>
				{/each}
			</div>
			<div class="qz-group" role="group" aria-label="Levels">
				{#each LEVELS as l (l)}
					<button type="button" class="qz-chip" aria-pressed={levels.includes(l)} onclick={() => (levels = flip(levels, l))}>{levelWord[l]}</button>
				{/each}
			</div>
			<div class="qz-group" role="group" aria-label="Kinds">
				{#each KINDS as k (k.id)}
					<button type="button" class="qz-chip" aria-pressed={kinds.includes(k.id)} onclick={() => (kinds = flip(kinds, k.id))}>{k.label}</button>
				{/each}
			</div>
		</div>
		<p class="qz-hint">
			{#if picked}
				Questions from your picks; a row left unpicked keeps each of its options.
				<button type="button" class="mg-link quiet" onclick={clearPicks}>Clear picks</button>
			{:else}
				Questions from the whole bank. Pick topics, levels or kinds to narrow them.
			{/if}
		</p>

		{#if !q}
			<p class="mg-note">No questions match these choices yet.</p>
		{:else}
			<!-- ------------------------------------------------ one question -->
			<section class="qz-card" aria-live="polite">
				<header class="qz-head">
					<span class="qz-tag">{topicWord(q.topic)}</span>
					<span class="qz-tag lvl-{q.level}">{levelWord[q.level]}</span>
					<span class="qz-tag">{kindWord(q.kind)}</span>
					<span class="mg-grow"></span>
					<span class="qz-count">{at + 1} of {order.length}</span>
				</header>

				{#if q.kind === 'choice'}
					<p class="qz-q"><Sci text={q.question} /></p>
					<ul class="qz-options">
						{#each q.options as o, k (k)}
							<li>
								<button type="button" class="qz-opt" class:right={pick !== null && k === q.answer} class:wrong={pick === k && k !== q.answer} disabled={pick !== null} onclick={() => choose(k)}><Sci text={o} /></button>
							</li>
						{/each}
					</ul>
				{:else if q.kind === 'truefalse'}
					<p class="qz-q"><Sci text={q.statement} /></p>
					<ul class="qz-options two">
						{#each [true, false] as v (v)}
							<li>
								<button type="button" class="qz-opt" class:right={pick !== null && v === q.answer} class:wrong={pick === v && v !== q.answer} disabled={pick !== null} onclick={() => choose(v)}>{v ? 'True' : 'False'}</button>
							</li>
						{/each}
					</ul>
				{:else if q.kind === 'match'}
					<p class="qz-q"><Sci text={q.question} /></p>
					<p class="mg-note">Drag each item on the right to its match, or click an item and then its place.</p>
					<div class="qz-match">
						<ul class="qz-slots">
							{#each q.pairs as pair, k (k)}
								{@const item = placed[k]}
								<li class="qz-slot" class:right={checked && item === k} class:wrong={checked && item !== k}>
									<span class="qz-left"><Sci text={pair.left} /></span>
									<button
										type="button"
										class="qz-drop"
										class:filled={item !== null}
										aria-label="Place for {pair.left}"
										ondragover={(e) => e.preventDefault()}
										ondrop={(e) => {
											e.preventDefault();
											const n = Number(e.dataTransfer?.getData('text/plain'));
											if (Number.isInteger(n)) place(k, n);
										}}
										onclick={() => (holding !== null ? place(k, holding) : item !== null ? unplace(k) : null)}
									>
										{#if item !== null && q.pairs[item]}<Sci text={q.pairs[item].right} />{:else}<span class="mg-note">{holding !== null ? 'Place here' : 'Drop here'}</span>{/if}
									</button>
									{#if checked && item !== k}<span class="qz-fix"><Sci text={q.pairs[k].right} /></span>{/if}
								</li>
							{/each}
						</ul>
						<ul class="qz-tray" aria-label="Items to place">
							{#each rights as r (r)}
								{#if !placed.includes(r) && q.pairs[r]}
									<li>
										<button
											type="button"
											class="qz-item"
											class:held={holding === r}
											draggable="true"
											ondragstart={(e) => e.dataTransfer?.setData('text/plain', String(r))}
											onclick={() => (holding = holding === r ? null : r)}><Sci text={q.pairs[r].right} /></button
										>
									</li>
								{/if}
							{/each}
						</ul>
					</div>
					{#if !checked}
						<button type="button" class="mg-btn primary" disabled={placed.some((p) => p === null)} onclick={checkMatch}>Check</button>
					{/if}
				{:else if q.kind === 'case'}
					<p class="qz-scenario"><Sci text={q.scenario} /></p>
					{#each q.parts as part, i (i)}
						{#if i === 0 || parts[i - 1] !== null}
							<div class="qz-part">
								<p class="qz-q">{i + 1}. <Sci text={part.question} /></p>
								<ul class="qz-options">
									{#each part.options as o, k (k)}
										<li>
											<button type="button" class="qz-opt" class:right={parts[i] !== null && k === part.answer} class:wrong={parts[i] === k && k !== part.answer} disabled={parts[i] !== null} onclick={() => choosePart(i, k)}><Sci text={o} /></button>
										</li>
									{/each}
								</ul>
								{#if parts[i] !== null}<p class="qz-why" class:ok={parts[i] === part.answer}><Sci text={part.explain} /></p>{/if}
							</div>
						{/if}
					{/each}
				{/if}

				{#if answered}
					<p class="qz-why" class:ok={gotIt}>
						<b>{gotIt ? 'Right!' : 'Not this time.'}</b>
						<Sci text={q.explain} />
					</p>
					<div class="qz-actions">
						<button type="button" class="mg-btn primary" onclick={next}>Next question</button>
					</div>
				{:else}
					<div class="qz-actions">
						<button type="button" class="mg-link quiet" onclick={next}>Skip</button>
					</div>
				{/if}
			</section>

			<div class="qz-foot">
				<button type="button" class="mg-link quiet" onclick={reshuffle}><Shuffle size={13} /> Shuffle</button>
				<button type="button" class="mg-link quiet" onclick={startOver}><RotateCcw size={13} /> Start over</button>
			</div>
		{/if}
	{/if}
</div>

<style>
	.qz-card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: 760px;
		padding: var(--cr-box-pad, 16px 18px);
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		box-shadow: var(--cr-card-shadow);
	}
	.qz-gate h2 {
		margin: 0;
		font-size: var(--mg-fs-lg, 1.1rem);
	}
	.qz-lock {
		display: inline-grid;
		place-items: center;
		width: 40px;
		height: 40px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--mg-accent) 10%, transparent);
		color: var(--mg-accent);
	}
	.qz-q {
		margin: 0;
		font-size: var(--mg-fs-md, 1rem);
		font-weight: 500;
		line-height: 1.5;
	}
	.qz-scenario {
		margin: 0;
		padding: 10px 12px;
		border-left: 3px solid var(--mg-accent);
		background: color-mix(in srgb, var(--mg-accent) 5%, transparent);
		line-height: 1.55;
	}
	.qz-options {
		display: grid;
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.qz-options.two {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		max-width: 360px;
	}
	.qz-opt,
	.qz-item,
	.qz-drop {
		width: 100%;
		padding: 9px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm, 6px);
		background: var(--mg-surface);
		color: var(--mg-text);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.qz-opt:hover:not(:disabled),
	.qz-item:hover {
		border-color: var(--mg-accent);
	}
	.qz-opt:disabled {
		cursor: default;
		color: var(--mg-text);
		opacity: 1;
	}
	.qz-opt.right,
	.qz-slot.right .qz-drop {
		border-color: var(--mg-ok, #1a9641);
		background: color-mix(in srgb, var(--mg-ok, #1a9641) 12%, var(--mg-surface));
	}
	.qz-opt.wrong,
	.qz-slot.wrong .qz-drop {
		border-color: var(--mg-bad, #d7191c);
		background: color-mix(in srgb, var(--mg-bad, #d7191c) 10%, var(--mg-surface));
	}
	.qz-why {
		margin: 0;
		padding: 10px 12px;
		border-radius: var(--mg-r-sm, 6px);
		background: color-mix(in srgb, var(--mg-bad, #d7191c) 7%, transparent);
		line-height: 1.5;
	}
	.qz-why.ok {
		background: color-mix(in srgb, var(--mg-ok, #1a9641) 9%, transparent);
	}
	.qz-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}
	.qz-tag {
		padding: 2px 8px;
		border: 1px solid var(--mg-border);
		border-radius: 999px;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.qz-tag.lvl-hard {
		border-color: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
		color: var(--mg-accent);
	}
	.qz-count {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.qz-filters {
		display: flex;
		flex-wrap: wrap;
		gap: 10px 18px;
	}
	.qz-hint {
		margin: -4px 0 0;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-sm);
	}
	.qz-hint .mg-link {
		margin-left: 6px;
	}
	.qz-group {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.qz-chip {
		padding: 4px 11px;
		border: 1px solid var(--mg-border);
		border-radius: 999px;
		background: var(--mg-surface);
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--mg-fs-sm);
		cursor: pointer;
	}
	.qz-chip[aria-pressed='true'] {
		border-color: var(--mg-accent);
		background: color-mix(in srgb, var(--mg-accent) 10%, var(--mg-surface));
		color: var(--mg-text);
	}
	.qz-match {
		display: grid;
		grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
		gap: 14px;
		align-items: start;
	}
	.qz-slots,
	.qz-tray {
		display: grid;
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.qz-slot {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
		gap: 8px;
		align-items: center;
	}
	.qz-left {
		font-weight: 500;
	}
	.qz-drop {
		min-height: 40px;
		border-style: dashed;
	}
	.qz-drop.filled {
		border-style: solid;
	}
	.qz-fix {
		grid-column: 2;
		font-size: var(--mg-fs-xs);
		color: var(--mg-ok, #1a9641);
	}
	.qz-item {
		cursor: grab;
	}
	.qz-item.held {
		border-color: var(--mg-accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--mg-accent) 30%, transparent);
	}
	.qz-part {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.qz-actions,
	.qz-foot {
		display: flex;
		align-items: center;
		gap: 14px;
	}
	.qz-foot {
		max-width: 760px;
	}
	.qz-foot .mg-link {
		display: inline-flex;
		align-items: center;
		gap: 5px;
	}
	@media (max-width: 640px) {
		.qz-match,
		.qz-slot {
			grid-template-columns: 1fr;
		}
	}
</style>
