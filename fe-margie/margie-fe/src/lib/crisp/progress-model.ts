/**
 * A run's progress as one model, read by the Analyze grid (pies, and the popup on a pie)
 * and by the Jobs page (the table beside the log), so the two never disagree.
 *
 * Each cell is one step on one genome: its state, how far it is, and an estimate of the
 * time it still needs. Time left adds up the way the workflow schedules work: steps in the
 * same phase run side by side (the longest counts), phases one after another, and genomes
 * one after another (the cluster's Stage 2 takes one genome at a time).
 */

import type { Run } from '$lib/api';
import { COMPARE_TOOLS, RESULT_STAGES, logSteps } from '$lib/crisp/steps';
import { columnOf, sourceSay, type SourceRow } from '$lib/crisp/cache-report';
import { uiBase } from '$lib/workspace/base.svelte';
import { baseOf } from '$lib/crisp/genomes';
import type { Genome, OrganismResult, ToolClock, ToolJob } from '$lib/workspace/data.svelte';

export type State = 'done' | 'run' | 'wait' | 'failed' | 'partial' | 'none' | 'na';

export interface Cell {
	state: State;
	/** 0-100; null when it cannot be told. */
	pct: number | null;
	/** One line for the tooltip and the popup. */
	say: string;
	/** Seconds since the step started, and its usual seconds, when known. */
	so?: number;
	usual?: number;
	/** Seconds the step still needs; null when there is nothing to estimate from. */
	left: number | null;
}
/** src: where its results came from (the run's cache report), when the run has one. */
/** Where a step's results stand on disk: its main results file, and whether they are in the MARGIE database (a *_db.tkn beside them). */
export interface Store {
	file?: { name: string; size: number };
	loaded: boolean;
}

/** jobs: the SLURM jobs that ran the step for this genome (or for the whole run, a batch). */
export type GridCell = Cell & { t: string; href?: string; src?: SourceRow; store?: Store; jobs?: ToolJob[] };

export interface RowProgress {
	g: string;
	cells: GridCell[];
	/** 0-100 over the steps this genome runs. */
	pct: number;
	state: 'done' | 'running' | 'failed' | 'stopped' | 'queued';
	/** Steps running now. */
	running: string[];
	done: number;
	of: number;
	/** Seconds still needed for the steps with a usual time; `untimed` names the others (their first run here). */
	left: number;
	unknown: boolean;
	untimed: string[];
}

export interface ColumnProgress {
	t: string;
	pct: number | null;
	done: number;
	failed: number;
	of: number;
}

export interface Progress {
	phases: { label: string; cols: string[] }[];
	cols: string[];
	firsts: Set<string>;
	rows: RowProgress[];
	columns: ColumnProgress[];
	overall: number;
	counts: { done: number; all: number };
	/** The whole job: seconds still needed for the timed steps, and the steps on their first run here. */
	left: number;
	unknown: boolean;
	untimed: string[];
}

export interface ProgressInput {
	/** The run in view, going or ended; null for none. */
	run: Run | null;
	/** Whether it is still going. */
	going: boolean;
	/** Its tools (the grid's columns). */
	tools: string[];
	/** Every tool this setup offers. */
	offered: string[];
	/** The genomes, one row each. */
	genomes: string[];
	/** Its log, '' when not read. */
	log: string;
	/** Its tool clock, null when not read. */
	clock: ToolClock | null;
	/** Now on the server's clock, ms. */
	now: number;
	results: OrganismResult[];
	/** Domain and genetic code by genome. */
	meta: Map<string, Genome>;
	setting: (key: string) => string;
	outputRoot: string;
	/** The genome and tool the run's own log names as running now (this computer). */
	current?: { genome: string; tool: string } | null;
	/** The run's cache report (lib/crisp/cache-report.ts): restored, fresh or partly, per step. */
	sources?: SourceRow[] | null;
}

/* Every step a genome goes through, by phase. Steps this setup does not run are shown
   blank, so the whole pipeline stays in view. */
const FUNCTION = ['kegg', 'cog', 'pfam', 'pgap', 'tigrfam', 'dbcan', 'eggnog', 'merops', 'tcdb', 'uniprot', 'interpro', 'geneprop'];
const LOCATION = ['tmbed', 'phobius', 'envelope', 'psortb', 'deepsig', 'signalp4', 'signalp6'];
const CALLERS = ['rasttk', 'prodigal'];
/** Parts of the scoring and fingerprint stages, listed as tools: their stage's column stands for them. */
const PARTS = new Set(['scoring_heuristic', 'fingerprint_database']);
const KNOWN = new Set([...FUNCTION, ...LOCATION, ...CALLERS, 'operon', 'gtdbtk', 'quast', 'llm', ...RESULT_STAGES, ...COMPARE_TOOLS]);

/** "40 s", "12 min", "1 h 20 min". */
export function span(seconds: number): string {
	const s = Math.max(0, Math.round(seconds));
	if (s < 90) return `${s} s`;
	const m = Math.round(s / 60);
	if (m < 90) return `${m} min`;
	const h = Math.floor(m / 60);
	return `${h} h${m % 60 ? ` ${m % 60} min` : ''}`;
}
/**
 * "about 12 min left"; with steps on their first run here (no usual time yet), "about 12 min
 * left, plus gtdbtk (first run here)" or "time left: gtdbtk (first run here)"; '' when nothing
 * is left. Each step's usual time comes from earlier runs, so a step is timed once it has run.
 */
export function leftText(left: number, untimed: readonly string[] = []): string {
	const known = left > 0 ? `about ${span(left)} left` : '';
	if (!untimed.length) return known;
	const named = untimed.length > 3 ? `${untimed.slice(0, 3).join(', ')} and ${untimed.length - 3} more` : untimed.join(', ');
	return known ? `${known}, plus ${named} (first run here)` : `time left: ${named} (first run here)`;
}

export function phasesOf(tools: string[], offered: string[]) {
	const all = new Set([...offered, ...tools]);
	const pick = (list: readonly string[]) => list.filter((t) => all.has(t) || t === 'envelope');
	const other = [...all].filter((t) => !KNOWN.has(t) && !PARTS.has(t));
	return [
		{ label: 'Prepare', cols: ['quast', 'gtdbtk'] },
		{ label: 'Genes', cols: ['genes'] },
		{ label: 'Function', cols: [...pick(FUNCTION), ...other] },
		{ label: 'Operons', cols: ['operon'] },
		{ label: 'Location', cols: pick(LOCATION) },
		{ label: 'Results', cols: [...RESULT_STAGES] },
		{ label: 'Compare', cols: [...COMPARE_TOOLS] },
		{ label: 'LLM', cols: ['llm'] },
		{ label: 'Report', cols: ['report'] }
	].filter((g) => g.cols.length);
}

export function buildProgress(i: ProgressInput): Progress {
	const run = i.going ? i.run : null;
	const planned = new Set(i.tools);
	const phases = phasesOf(i.tools, i.offered);
	const cols = phases.flatMap((g) => g.cols);
	const results = new Map(i.results.map((r) => [r.organism, r]));
	const cells = new Map<string, 'done' | 'partial'>();
	for (const r of i.results) for (const t of r.tools) cells.set(`${t.tool}\t${r.organism}`, t.processed ? 'done' : 'partial');
	const logged = i.log && i.run ? logSteps(i.log, i.run.status) : null;
	const started = new Map((i.clock?.started ?? []).map((e) => [`${e.tool}\t${e.genome}`, e]));
	const typical = i.clock?.typical ?? {};
	const usualOf = (col: string) => (col === 'genes' ? (typical.rasttk ?? typical.prodigal) : typical[col]);
	const now = i.current ?? null;
	const sourceOf = new Map((i.sources ?? []).map((r) => [`${columnOf(r.step)}\t${r.genome}`, r]));

	const mins = span;
	const NA = (say: string): Cell => ({ state: 'na', pct: null, say, left: 0 });
	const done = (say = 'done, 100%'): Cell => ({ state: 'done', pct: 100, say, left: 0 });
	const none = (col: string): Cell => {
		const u = usualOf(col);
		return { state: 'none', pct: 0, say: run ? 'not started yet' : 'not started, 0%', usual: u, left: run ? (u ?? null) : 0 };
	};

	/** A tool run's state from the clock: done, failed, under way (with an estimate when there is one), or cut short. */
	function fromClock(tool: string, genome: string): Cell | null {
		// A batch job on the cluster (GTDB-Tk, QUAST, the comparisons) has no genome and stands for all.
		const e = started.get(`${tool}\t${genome}`) ?? started.get(`${tool}\t`);
		if (!e) return null;
		if (e.ok) return done();
		if (e.failed) return { state: 'failed', pct: 0, say: 'failed (see the log)', left: 0 };
		if (!run) return { state: 'partial', pct: 0, say: 'stopped before it finished', left: 0 };
		const so = Math.max(0, (i.now - e.start) / 1000);
		const usual = typical[tool];
		if (usual) {
			const pct = Math.min(95, (so / usual) * 100);
			return { state: 'run', pct, say: `${Math.round(pct)}% (${mins(so)} of about ${mins(usual)})`, so, usual, left: Math.max(0, usual - so) };
		}
		return { state: 'wait', pct: null, say: `running, ${mins(so)} so far (no earlier run of ${tool} here to estimate from)`, so, left: null };
	}
	const fromLog = (step: string, genome: string): Cell | null => {
		const s = logged?.state.get(`${step}\t${genome}`);
		if (!s) return null;
		if (s === 'done') return done();
		if (s === 'failed') return { state: 'failed', pct: 0, say: 'failed (see the log)', left: 0 };
		if (s === 'partial') return { state: 'partial', pct: 0, say: 'stopped before it finished', left: 0 };
		if (s === 'na') return NA('switched off in Settings');
		return { state: 'wait', pct: null, say: 'running now', left: null };
	};

	/** Done when the cache report says the step's whole output was restored or kept: it is in place before the run goes on. */
	const inPlace = (col: string, genome: string): Cell | null => {
		const s = sourceOf.get(`${col}\t${genome}`)?.source;
		return s === 'restored' || s === 'kept' ? done() : null;
	};

	/** A cell: its state, how far it is (0-100; null when that cannot be told), and a line for its tooltip. */
	function cell(col: string, genome: string): Cell {
		const r = results.get(genome);
		const has = (t: string) => cells.get(`${t}\t${genome}`);
		switch (col) {
			case 'quast': {
				if (has('quast') === 'done') return done();
				if (!planned.has('quast')) return NA('not chosen for this run');
				return inPlace('quast', genome) ?? fromClock('quast', genome) ?? none(col);
			}
			case 'llm':
				return has(col) === 'done' ? done() : NA('not part of the pipeline yet');
			case 'gtdbtk': {
				if (has('gtdbtk') === 'done') return done();
				const kept = inPlace('gtdbtk', genome);
				if (kept) return kept;
				const c = fromClock('gtdbtk', genome);
				if (c) return c;
				if (i.setting('RUN_GTDBTK') !== '1') return NA('switched off in Settings');
				const g = i.meta.get(genome) ?? i.meta.get(baseOf(genome));
				return g?.domain && g?.genetic_code ? NA('not needed: its domain and genetic code are given') : none(col);
			}
			case 'genes': {
				for (const t of CALLERS) if (has(t) === 'done') return done(`done, 100% (${t === 'rasttk' ? 'RASTtk' : 'Prodigal'})`);
				const kept = inPlace('genes', genome);
				if (kept) return kept;
				for (const t of CALLERS) {
					const c = fromClock(t, genome);
					if (c) return { ...c, say: `${t === 'rasttk' ? 'RASTtk' : 'Prodigal'}: ${c.say}` };
				}
				if (now?.genome === genome && CALLERS.includes(now.tool)) return { state: 'wait', pct: null, say: 'running now', left: null };
				return none(col);
			}
			case 'report':
				if (r?.final?.table) return done('done, 100%: the table, map and figures are in');
				return fromLog('figures', genome)?.state === 'wait' ? { state: 'wait', pct: null, say: 'being written', left: null } : none(col);
		}
		// A comparison runs only when the run chose it; the result stages run in every run.
		if ((COMPARE_TOOLS as readonly string[]).includes(col) && !planned.has(col)) return NA('not chosen for this run');
		if ((RESULT_STAGES as readonly string[]).includes(col) || (COMPARE_TOOLS as readonly string[]).includes(col)) {
			const kept = inPlace(col, genome);
			if (kept) return kept;
			const l = fromLog(col, genome) ?? fromClock(col, genome);
			// Not in the log but the report is there: done before (a cache hands it back without running it).
			if (l && !(l.state === 'na' && r?.final?.table)) return l;
			if (has(col) === 'done' || r?.final?.table) return done();
			return none(col);
		}
		// An annotation tool, the operon finder or the envelope stage.
		if (has(col) === 'done') return done();
		const kept = inPlace(col, genome);
		if (kept) return kept;
		const c = fromClock(col, genome);
		if (c) return c;
		if (now?.genome === genome && now?.tool === col) return { state: 'wait', pct: null, say: 'running now', left: null };
		// The envelope stage runs in each run, as MARGIE's own part of the annotation.
		if (col !== 'envelope' && !planned.has(col)) return NA('not chosen for this run');
		// Its folder is there but nothing says it finished: under way while the job goes, cut short once it has ended.
		if (has(col) === 'partial')
			return run
				? { state: 'wait', pct: null, say: 'started, not finished yet', left: usualOf(col) ?? null }
				: { state: 'partial', pct: 0, say: 'started before, not finished', left: 0 };
		return none(col);
	}

	/** Where a cell's results are: its folder for the Files page, or the run's log for one that failed. */
	/** A step's folder in the genome's results: its main results file (<step>_results.tsv, rast.tsv for the genes, else the largest) and its database token. */
	function storeOf(col: string, genome: string): Store | undefined {
		const files = results.get(genome)?.files;
		const list = files?.[col === 'genes' ? (files.rasttk ? 'rasttk' : 'prodigal') : col];
		if (!list?.length) return undefined;
		const data = list.filter((f) => !f.name.endsWith('.tkn') && !/\.(log|err)$/.test(f.name));
		const file = data.find((f) => f.name === `${col}_results.tsv` || f.name === 'rast.tsv') ?? [...data].sort((a, b) => b.size - a.size)[0];
		return { file, loaded: list.some((f) => f.name.endsWith('_db.tkn')) };
	}

	function hrefOf(col: string, genome: string, c: Cell): string | undefined {
		if (c.state === 'na' || c.state === 'none') return undefined;
		const out = i.outputRoot;
		// This job's own folder first: Results may list the genome from another run, or not yet at all.
		const runDir = (i.run?.outputDir ?? '').replace(/\/$/, '');
		const listed = results.get(genome);
		const r = listed && (!runDir || listed.folder?.startsWith(`${runDir}/`)) ? listed : undefined;
		const gdir = r?.folder ?? (runDir ? `${runDir}/${genome}` : undefined);
		const toolPath = (t: string) => r?.tools.find((x) => x.tool === t)?.path ?? (gdir ? `${gdir}/${t}` : undefined);
		let dir: string | undefined;
		if (col === 'genes') dir = toolPath('rasttk') ?? toolPath('prodigal');
		else if (col === 'report') dir = r?.final?.dir ?? gdir;
		else if (col === 'figures') dir = r?.final?.diagrams ?? (gdir ? `${gdir}/scoring/figures` : undefined);
		else if (['consolidation', 'labeling', 'scoring'].includes(col)) dir = gdir ? `${gdir}/${col}` : undefined;
		else if ((RESULT_STAGES as readonly string[]).includes(col)) dir = gdir;
		else if ((COMPARE_TOOLS as readonly string[]).includes(col)) dir = runDir ? `${runDir}/${col}` : out ? `${out}/${col}` : undefined;
		else dir = toolPath(col) ?? (out ? `${out}/${col}/${genome}` : undefined);
		return dir ? uiBase.to(`/files?path=${encodeURIComponent(dir)}`) : undefined;
	}

	const avg = (cs: Cell[]) => {
		const on = cs.filter((c) => c.state !== 'na');
		return on.length ? on.reduce((a, c) => a + (c.pct ?? 0), 0) / on.length : null;
	};
	const phaseOf = new Map(phases.flatMap((g, k) => g.cols.map((t) => [t, k] as const)));

	/** A step's SLURM jobs for a genome: its own and the run's batch job; the genes column has both callers'. */
	const jobsOf = (t: string, g: string): ToolJob[] | undefined => {
		const by = i.clock?.jobs;
		if (!by) return undefined;
		const list = (t === 'genes' ? CALLERS : [t]).flatMap((k) => [...(by[`${k}\t${g}`] ?? []), ...(by[`${k}\t`] ?? [])]);
		return list.length ? list : undefined;
	};

	const rows: RowProgress[] = i.genomes.map((g) => {
		const cs: GridCell[] = cols.map((t) => {
			const store = storeOf(t, g);
			// Its results in the database (a *_db.tkn is written once they are loaded): the step is through.
			const shown = cell(t, g);
			const c = store?.loaded && ['run', 'wait', 'partial', 'none'].includes(shown.state) ? done() : shown;
			const src = sourceOf.get(`${t}\t${g}`);
			// The tooltip says where a step's results came from too, once the report has it.
			const say = src && src.source !== 'not run' && c.state !== 'na' ? `${c.say}; ${sourceSay(src)}` : c.say;
			return { t, ...c, say, href: hrefOf(t, g, c), src, store, jobs: jobsOf(t, g) };
		});
		const on = cs.filter((c) => c.state !== 'na');
		const pct = Math.round(avg(cs) ?? 0);
		// Phases one after another; within one, the longest step counts.
		let left = 0;
		const untimed: string[] = [];
		if (run) {
			const byPhase = new Map<number, number>();
			for (const c of on) {
				if (c.left === null && c.state !== 'done') untimed.push(c.t);
				const k = phaseOf.get(c.t) ?? 0;
				byPhase.set(k, Math.max(byPhase.get(k) ?? 0, c.left ?? 0));
			}
			left = [...byPhase.values()].reduce((a, b) => a + b, 0);
		}
		// A job that has ended runs nothing: a step it left under way stopped there.
		if (!run)
			for (const c of on)
				if (c.state === 'run' || c.state === 'wait') Object.assign(c, { state: 'partial', pct: 0, say: 'stopped before it finished', left: 0 });
		const running = on.filter((c) => c.state === 'run' || c.state === 'wait').map((c) => c.t);
		const doneN = on.filter((c) => c.state === 'done').length;
		const state: RowProgress['state'] =
			on.length && doneN === on.length
				? 'done'
				: on.some((c) => c.state === 'failed')
					? 'failed'
					: !run
						? doneN || on.some((c) => c.state === 'partial')
							? 'stopped'
							: 'queued'
						: running.length || doneN
							? 'running'
							: 'queued';
		return { g, cells: cs, pct, state, running, done: doneN, of: on.length, left, unknown: untimed.length > 0, untimed };
	});

	const columns = cols.map((t, j) => {
		const cs = rows.map((row) => row.cells[j]);
		const on = cs.filter((c) => c.state !== 'na');
		const pct = avg(cs);
		return {
			t,
			pct: pct === null ? null : Math.round(pct),
			done: on.filter((c) => c.state === 'done').length,
			failed: on.filter((c) => c.state === 'failed').length,
			of: on.length
		};
	});
	return {
		phases,
		cols,
		firsts: new Set(phases.map((g) => g.cols[0])),
		rows,
		columns,
		overall: Math.round(avg(rows.flatMap((r) => r.cells)) ?? 0),
		counts: { done: columns.reduce((a, c) => a + c.done, 0), all: columns.reduce((a, c) => a + c.of, 0) },
		// Genomes one after another (the cluster's Stage 2 takes one at a time).
		left: rows.reduce((a, r) => a + (r.state === 'done' ? 0 : r.left), 0),
		unknown: rows.some((r) => r.state !== 'done' && r.unknown),
		untimed: [...new Set(rows.flatMap((r) => (r.state === 'done' ? [] : r.untimed)))]
	};
}

/** A run's tools as the grid's columns: the operon finder always, then its own (all when it names none). */
export function toolsOfRun(r: Run | null, offered: string[]): string[] {
	const named = r?.args?.flatMap((a, k) => (r.args[k - 1] === '--tool' ? [a] : [])) ?? [];
	const list = named.length ? named : r?.tools?.length ? r.tools : offered;
	return ['operon', ...list.filter((t) => t !== 'operon')];
}
