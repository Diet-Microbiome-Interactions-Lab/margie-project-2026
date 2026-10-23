<script lang="ts">
	/**
	 * A small drawing of one page as the site shows it: the top bar, the sidebar with the
	 * page picked, the page's blue title, and its layout. Drawn in the theme's colours, so it
	 * follows the palette and dark mode.
	 */
	let { tab }: { tab: string } = $props();

	const PAGES = [
		['home', 'Home'],
		['analyze', 'Analyze'],
		['jobs', 'Jobs'],
		['results', 'Results'],
		['files', 'Files'],
		['terminal', 'Terminal'],
		['install', 'Install'],
		['settings', 'Settings']
	] as const;
	const TITLE: Record<string, string> = Object.fromEntries(PAGES);

	// Analyze: genomes down, tools across; 2 done, 1 under way, 0 not started.
	const GRID = [
		[2, 2, 2, 2, 2, 2, 1, 0],
		[2, 2, 2, 2, 1, 0, 0, 0],
		[2, 2, 1, 0, 0, 0, 0, 0],
		[1, 0, 0, 0, 0, 0, 0, 0]
	];
	// Results: the genome ring, in confidence tiers.
	const RING = [0, 0, 1, 0, 2, 1, 0, 0, 3, 1, 0, 1, 2, 0, 0, 4, 1, 0, 0, 1, 2, 0, 1, 5, 0, 0, 1, 3, 0, 1, 0, 2];
	const arc = (r: number, i: number, n: number) => {
		const c = 2 * Math.PI * r;
		return { dash: `${c / n - 1.4} ${c - c / n + 1.4}`, offset: -(c / n) * i };
	};
	const JOBS = [
		['running', '40%'],
		['failed', 'failed'],
		['done', 'finished'],
		['stopped', 'stopped'],
		['done', 'finished'],
		['failed', 'failed']
	];
</script>

<svg viewBox="0 0 360 220" role="img" aria-hidden="true" class="pic">
	<!-- the window: bar, sidebar, page -->
	<rect class="frame" x="1" y="1" width="358" height="218" rx="10" />
	<path class="chrome" d="M1 11a10 10 0 0 1 10-10h338a10 10 0 0 1 10 10v12H1z" />
	<text class="brand" x="12" y="16">MARGIE</text>
	<rect class="beta" x="50" y="9" width="24" height="9" rx="4.5" />
	<circle class="dot" cx="318" cy="12.5" r="3.6" />
	<circle class="dot" cx="332" cy="12.5" r="3.6" />
	<circle class="avatar" cx="346" cy="12.5" r="4.6" />
	<path class="chrome" d="M1 23h62v186a10 10 0 0 1 -10 10h-42a10 10 0 0 1 -10 -10z" />
	{#each PAGES as [id, label], i (id)}
		<rect class={id === tab ? 'side-on' : 'side'} x="5" y={28 + i * 19} width="54" height="14" rx="3" />
		<circle class={id === tab ? 'side-ic-on' : 'side-ic'} cx="12" cy={35 + i * 19} r="2.4" />
		<text class={id === tab ? 'side-t-on' : 'side-t'} x="18" y={38 + i * 19}>{label}</text>
	{/each}
	<text class="ttl" x="72" y="43">{TITLE[tab] ?? ''}</text>

	{#if tab === 'analyze'}
		<text class="muted" x="72" y="55">95 genomes ready to annotate.</text>
		<rect class="card" x="72" y="62" width="134" height="36" rx="4" />
		<text class="tiny" x="80" y="73">TOOLS</text>
		<rect class="ghost" x="80" y="80" width="44" height="11" rx="2.5" />
		<rect class="ghost" x="128" y="80" width="50" height="11" rx="2.5" />
		<rect class="card" x="212" y="62" width="138" height="36" rx="4" />
		<rect class="accf" x="222" y="71" width="118" height="17" rx="3" />
		<text class="on" x="281" y="82.5" text-anchor="middle">Annotate 95 genomes</text>
		<rect class="card" x="72" y="103" width="278" height="58" rx="4" />
		<text class="sm b" x="80" y="114">Genomes</text>
		<rect class="accf" x="300" y="106" width="44" height="11" rx="2.5" />
		<text class="on" x="322" y="114" text-anchor="middle">Add FASTA</text>
		{#each ['Afipia_carboxidovorans', 'Bacteroides_theta', 'Escherichia_coli'] as g, i (g)}
			<rect class="box box-on {i < 2 ? 'drag' : ''}" style="--d: {i * 260}ms" x="80" y={121 + i * 12.5} width="8" height="8" rx="2" />
			<text class="tiny" x="94" y={128 + i * 12.5}>{g}.fna</text>
			<rect class={i === 1 ? 'pill-warn' : 'pill'} x="250" y={120.5 + i * 12.5} width="40" height="9.5" rx="4.75" />
			<rect class="pill" x="296" y={120.5 + i * 12.5} width="40" height="9.5" rx="4.75" />
		{/each}
		<rect class="card" x="72" y="166" width="278" height="46" rx="4" />
		<text class="tiny" x="80" y="177">PROGRESS</text>
		{#each GRID.slice(0, 2) as row, r (r)}
			{#each row as c, k (k)}
				<circle class={c === 2 ? 'pie-done' : c === 1 ? 'pie-run' : 'pie-none'} cx={142 + k * 25} cy={185 + r * 15} r="5" style="--d: {(r * 8 + k) * 90}ms" />
			{/each}
		{/each}
	{:else if tab === 'jobs'}
		<text class="muted" x="72" y="55">1 running | 12 finished | 22 failed</text>
		<rect class="card" x="72" y="62" width="88" height="88" rx="4" />
		{#each JOBS as [state, word], i (i)}
			<rect class={i === 0 ? 'accsoft' : 'none'} x="75" y={66 + i * 13.5} width="82" height="11" rx="2" />
			<circle class="st-{state}" cx="81" cy={71.5 + i * 13.5} r="2.4" />
			<text class="tiny" x="86" y={74.5 + i * 13.5}>Annotate</text>
			<text class="tiny st-t-{state}" x="155" y={74.5 + i * 13.5} text-anchor="end">{word}</text>
		{/each}
		<rect class="card" x="164" y="62" width="186" height="88" rx="4" />
		<text class="sm b" x="172" y="75">Annotate fna</text>
		<rect class="track" x="172" y="81" width="170" height="4" rx="2" />
		<rect class="accf grow" x="172" y="81" width="170" height="4" rx="2" />
		{#each [70, 45, 25, 10] as pct, i (i)}
			<text class="tiny" x="172" y={99 + i * 13}>genome {i + 1}</text>
			<rect class="track" x="222" y={95 + i * 13} width="80" height="4" rx="2" />
			<rect class="accf" x="222" y={95 + i * 13} width={(80 * pct) / 100} height="4" rx="2" />
			<text class="tiny" x="342" y={99 + i * 13} text-anchor="end">{pct}%</text>
		{/each}
		<rect class="term" x="72" y="155" width="278" height="57" rx="4" />
		<text class="termt mono" x="80" y="168">$ margie_sb --tools kegg,cog,pfam …</text>
		<text class="termt dim mono" x="80" y="180">rule run_pfam: genome 2 … done</text>
		<text class="termt dim mono" x="80" y="192">rule run_cog: genome 3 … started</text>
		<rect class="cursor" x="80" y="197" width="5" height="9" />
	{:else if tab === 'results'}
		<text class="muted" x="72" y="55">12 genomes annotated</text>
		<rect class="card" x="72" y="62" width="82" height="150" rx="4" />
		{#each ['E. coli', 'B. longum', 'C. fimi', 'A. macleodii', 'S. thiotaurini'] as g, i (g)}
			<rect class={i === 4 ? 'accsoft' : 'none'} x="76" y={67 + i * 16} width="74" height="13" rx="2" />
			<text class="tiny" x="81" y={76 + i * 16}>{g}</text>
		{/each}
		<rect class="card" x="160" y="62" width="190" height="150" rx="4" />
		{#each ['Map', 'Table', 'Figures'] as t, i (t)}
			<rect class={i === 0 ? 'accf' : 'ghost'} x={168 + i * 40} y="68" width="36" height="12" rx="2.5" />
			<text class={i === 0 ? 'on' : 'tiny'} x={186 + i * 40} y="77" text-anchor="middle">{t}</text>
		{/each}
		<g class="spin">
			{#each RING as tier, i (i)}
				{@const a = arc(42, i, RING.length)}
				<circle class="tier t{tier}" cx="255" cy="146" r="42" stroke-dasharray={a.dash} stroke-dashoffset={a.offset} />
			{/each}
		</g>
		<circle class="hole" cx="255" cy="146" r="30" />
		<text class="sm b" x="255" y="144" text-anchor="middle">3.9 Mb</text>
		<text class="tiny" x="255" y="155" text-anchor="middle">3,837 genes</text>
	{:else if tab === 'files'}
		<text class="muted" x="72" y="55">/scratch/cluster/you/margie-output</text>
		<rect class="card" x="72" y="62" width="110" height="150" rx="4" />
		{#each ['margie-output', 'genome-pool', 'sqlite', 'reports', 'logs', 'figures'] as f, i (f)}
			<path class="fold" d="M80 {70 + i * 18}h8l2 2h8v8h-18z" />
			<text class="tiny" x="102" y={78 + i * 18}>{f}</text>
		{/each}
		<rect class="card" x="188" y="62" width="162" height="150" rx="4" />
		<text class="sm b" x="196" y="76">summary.tsv</text>
		{#each Array(8) as _, i (i)}
			<rect class="line" x="196" y={86 + i * 14} width={140 - ((i * 37) % 60)} height="5" rx="2.5" />
		{/each}
	{:else if tab === 'terminal'}
		<text class="muted" x="72" y="55">A shell on your cluster account</text>
		<rect class="term" x="72" y="62" width="278" height="150" rx="4" />
		<circle class="okf" cx="82" cy="72" r="2.6" />
		<text class="termt" x="89" y="75">Connected as you@cluster</text>
		<text class="termt mono" x="80" y="94">$ squeue -u $USER</text>
		<text class="termt dim mono" x="80" y="107">JOBID  NAME       ST  TIME</text>
		<text class="termt dim mono" x="80" y="119">81234  run_pfam   R   12:04</text>
		<text class="termt dim mono" x="80" y="131">81235  run_cog    PD  0:00</text>
		<text class="termt mono" x="80" y="150">$ ls margie-output</text>
		<text class="termt dim mono" x="80" y="163">2026-10-22-1147  2026-10-21-0930</text>
		<text class="termt mono" x="80" y="182">$</text>
		<rect class="cursor" x="89" y="174" width="5" height="10" />
	{:else if tab === 'install'}
		<text class="muted" x="72" y="55">3 of 4 ready</text>
		<rect class="card" x="72" y="62" width="130" height="150" rx="4" />
		{#each [['Cluster', true], ['SLURM account', true], ['Output folder', true], ['Licence terms', false]] as [what, ok], i (what)}
			<circle class={ok ? 'okf' : 'warnf'} cx="84" cy={78 + i * 22} r="5" />
			{#if ok}<path class="tick sm" d="M81.5 {78 + i * 22} l2 2 l3.6 -3.8" />{/if}
			<text class="sm" x="94" y={81.5 + i * 22}>{what}</text>
		{/each}
		<rect class="card" x="208" y="62" width="142" height="150" rx="4" />
		<text class="tiny" x="216" y="74">WHAT A RUN CAN USE</text>
		{#each Array(6) as _, i (i)}
			<rect class="cell" x={216 + (i % 2) * 64} y={80 + Math.floor(i / 2) * 42} width="60" height="38" rx="3" />
			<text class="tiny" x={221 + (i % 2) * 64} y={91 + Math.floor(i / 2) * 42}>{i + 1}</text>
			<rect class="chip" x={221 + (i % 2) * 64} y={96 + Math.floor(i / 2) * 42} width="24" height="7" rx="2" />
			<rect class="chip" x={248 + (i % 2) * 64} y={96 + Math.floor(i / 2) * 42} width="22" height="7" rx="2" />
		{/each}
	{:else if tab === 'settings'}
		<text class="muted" x="72" y="55">Folders, cores and the steps a run takes</text>
		<rect class="card" x="72" y="62" width="278" height="68" rx="4" />
		<text class="tiny" x="80" y="74">DATABASES · NEEDED FOR EVERY RUN</text>
		{#each Array(3) as _, i (i)}
			<rect class="cell" x={80 + i * 88} y="80" width="84" height="40" rx="3" />
			<rect class="line" x={86 + i * 88} y="88" width="50" height="5" rx="2.5" />
			<rect class="field" x={86 + i * 88} y="100" width="72" height="12" rx="2.5" />
		{/each}
		<rect class="card" x="72" y="136" width="278" height="76" rx="4" />
		<text class="tiny" x="80" y="148">PER TOOL</text>
		{#each ['Tool', 'Threads', 'Memory', 'Time'] as h, i (h)}
			<text class="tiny b" x={80 + i * 66} y="160">{h}</text>
		{/each}
		<text class="acct tiny" x="80" y="172">PHASE 4</text>
		{#each ['COG', 'KEGG', 'Pfam'] as t, r (t)}
			<text class="tiny" x="80" y={184 + r * 11}>{t}</text>
			{#each Array(3) as _, c (c)}
				<rect class="field" x={146 + c * 66} y={177 + r * 11} width="50" height="8" rx="2" />
			{/each}
		{/each}
	{/if}
</svg>

<style>
	.pic {
		display: block;
		width: 100%;
		height: auto;
		font-family: var(--mg-font);
	}
	text {
		font-size: 8px;
		fill: var(--mg-text);
	}
	.sm {
		font-size: 8.5px;
	}
	.b {
		font-weight: 700;
	}
	.tiny {
		font-size: 7px;
		fill: var(--mg-text-3);
	}
	.muted {
		font-size: 8px;
		fill: var(--mg-text-2);
	}
	.ttl {
		font-size: 15px;
		font-weight: 800;
		fill: var(--mg-accent);
	}
	.brand {
		font-size: 8.5px;
		font-weight: 800;
	}
	.mono {
		font-family: var(--mg-mono);
		font-size: 7.5px;
	}
	.on {
		fill: var(--mg-on-accent, #fff);
		font-size: 7.5px;
		font-weight: 600;
	}
	.acct {
		fill: var(--mg-accent-ink, var(--mg-accent));
		font-weight: 600;
	}
	.frame {
		fill: var(--mg-bg);
		stroke: var(--mg-border);
	}
	.chrome {
		fill: var(--mg-surface-2);
	}
	.beta {
		fill: color-mix(in oklab, var(--color-warning-500, #e0a100) 35%, transparent);
	}
	.dot {
		fill: var(--mg-border-strong);
	}
	.avatar {
		fill: color-mix(in oklab, var(--mg-accent) 45%, var(--mg-border-strong));
	}
	.side,
	.none {
		fill: transparent;
	}
	.side-on {
		fill: var(--mg-accent);
	}
	.side-ic {
		fill: var(--mg-text-3);
	}
	.side-ic-on {
		fill: var(--mg-on-accent, #fff);
	}
	.side-t {
		font-size: 6.5px;
		fill: var(--mg-text-2);
	}
	.side-t-on {
		font-size: 6.5px;
		font-weight: 700;
		fill: var(--mg-on-accent, #fff);
	}
	.card {
		fill: var(--cr-card, var(--mg-surface));
		stroke: var(--cr-card-edge, var(--mg-border));
	}
	.cell {
		fill: var(--mg-surface);
		stroke: var(--mg-border);
	}
	.ghost {
		fill: none;
		stroke: color-mix(in srgb, var(--mg-accent) 45%, var(--mg-border));
	}
	.field {
		fill: var(--mg-surface);
		stroke: var(--mg-border-strong);
	}
	.chip,
	.line,
	.track {
		fill: var(--mg-surface-2);
	}
	.line {
		fill: color-mix(in srgb, var(--mg-text) 12%, transparent);
	}
	.pill {
		fill: var(--mg-surface-2);
		stroke: var(--mg-border);
	}
	.pill-warn {
		fill: color-mix(in srgb, var(--mg-warn) 14%, transparent);
		stroke: color-mix(in srgb, var(--mg-warn) 45%, transparent);
	}
	.accf {
		fill: var(--mg-accent);
	}
	.accsoft {
		fill: color-mix(in srgb, var(--mg-accent) 14%, transparent);
	}
	.okf {
		fill: var(--mg-ok);
	}
	.warnf {
		fill: var(--mg-warn);
	}
	.tick {
		fill: none;
		stroke: #fff;
		stroke-width: 1.6;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.rule.faint {
		stroke: var(--mg-border);
		stroke-width: 0.8;
	}
	.fold {
		fill: color-mix(in srgb, var(--mg-accent) 22%, transparent);
		stroke: color-mix(in srgb, var(--mg-accent) 60%, transparent);
		stroke-width: 0.8;
	}
	/* Analyze: the pies, done or filling. */
	.pie-done {
		fill: var(--mg-accent);
		animation: pop 600ms var(--d) both;
	}
	.pie-run {
		fill: color-mix(in srgb, var(--mg-accent) 30%, transparent);
		stroke: var(--mg-accent);
		stroke-width: 1.4;
		animation: breathe 1.8s ease-in-out infinite;
	}
	.pie-none {
		fill: none;
		stroke: var(--mg-border-strong);
		stroke-dasharray: 1.5 1.5;
	}
	/* Genomes: boxes ticked as a drag passes down them. */
	.box {
		stroke: var(--mg-accent);
	}
	.box-on {
		fill: var(--mg-accent);
	}
	.box.drag {
		animation: sweep 3.2s ease-in-out var(--d) infinite;
	}
	/* Jobs: the status dots and words. */
	.st-running {
		fill: var(--mg-accent);
	}
	.st-failed {
		fill: var(--mg-danger);
	}
	.st-done {
		fill: var(--mg-ok);
	}
	.st-stopped {
		fill: var(--mg-text-3);
	}
	.st-t-failed {
		fill: var(--mg-danger);
	}
	.st-t-running {
		fill: var(--mg-accent-ink, var(--mg-accent));
	}
	.grow {
		transform-box: fill-box;
		transform-origin: left;
		animation: fill 4s ease-in-out infinite alternate;
	}
	.term {
		fill: #14171b;
	}
	.termt {
		fill: #e4e8ec;
		font-size: 7.5px;
	}
	.termt.dim {
		fill: #9aa3ab;
	}
	.cursor {
		fill: #2e9d5b;
		animation: blink 1s steps(2) infinite;
	}
	/* Results: the ring in confidence tiers, turning slowly. */
	.tier {
		fill: none;
		stroke-width: 9;
	}
	.t0 {
		stroke: color-mix(in srgb, var(--mg-accent) 85%, transparent);
	}
	.t1 {
		stroke: color-mix(in srgb, var(--mg-accent) 55%, transparent);
	}
	.t2 {
		stroke: color-mix(in srgb, var(--mg-accent) 30%, transparent);
	}
	.t3 {
		stroke: var(--mg-warn);
	}
	.t4 {
		stroke: var(--mg-danger);
	}
	.t5 {
		stroke: var(--mg-border-strong);
	}
	.hole {
		fill: var(--mg-surface);
	}
	.spin {
		transform-origin: 255px 146px;
		animation: turn 40s linear infinite;
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: scale(0.4);
			transform-box: fill-box;
			transform-origin: center;
		}
	}
	@keyframes breathe {
		50% {
			fill: color-mix(in srgb, var(--mg-accent) 65%, transparent);
		}
	}
	@keyframes sweep {
		0%,
		12% {
			fill: transparent;
		}
		22%,
		100% {
			fill: var(--mg-accent);
		}
	}
	@keyframes fill {
		from {
			transform: scaleX(0.2);
		}
		to {
			transform: scaleX(0.75);
		}
	}
	@keyframes blink {
		50% {
			opacity: 0;
		}
	}
	@keyframes turn {
		to {
			transform: rotate(360deg);
		}
	}
	:global([data-motion='off']) .pic * {
		animation: none !important;
	}
</style>
