/**
 * Answers the interface's local API routes (routes/api/local shapes) from
 * MARGIE's cluster API: jobs, SFTP browsing, config.yaml and licence status.
 * Routes with no cluster meaning return 501 with an explanation.
 */

import { ApiError, type Run } from '$lib/api';
import { NOT_YET } from '$lib/license';
import { isWorkflowPathParam } from '$lib/configParams';
import { backend } from '$lib/workspace/backend.svelte';
import type { CheckRow, Genome, GenomeSummary, OrganismResult, Overview, Setting, SetupRow, Tool, ToolClock, ToolJob } from '$lib/workspace/data.svelte';
import { FinalTally, type FinalCounts } from '$lib/workspace/final-summary';
import { TABLE_EXT, extOf, parseDelimited, queryFromParams, queryLoaded, type CellStyle, type Table } from '$lib/workspace/viewers/table-query';
import { sheetsOf } from '$lib/workspace/viewers/excel-sheets';
import { call, fetchRaw, get } from './http';
import { readWithProgress } from './transfers.svelte';
import { getApiUrl } from '$lib/config';
import { getToken } from '$lib/auth';
import type { ChatRemote } from '$lib/workspace/cluster-parts';

/** The workflow a Crisp run starts on the cluster. */
export const WORKFLOW = 'margie_sb';
const GENOME_EXT = /\.(fasta|fa|fna)(\.gz)?$/i;
/**
 * Stages a run includes, chosen or not. "rasttk" is phase 3's key whichever gene caller
 * the genome gets (RASTtk or Prodigal); the envelope stage is MARGIE's own, part of the standard annotation.
 */
const ALWAYS = ['rasttk', 'operon', 'envelope', 'consolidation', 'labeling', 'fingerprint', 'fingerprint_database', 'scoring_heuristic'];
/** Tools the envelope stage reads. */
const ENVELOPE_INPUTS = ['tigrfam', 'pgap', 'pfam', 'uniprot'];
const ENVELOPE_PHASE = 7;

/** Throws a 501 for features the cluster does not offer. */
const notHere = (what: string): never => {
	throw new ApiError(what, 501);
};
const baseName = (p: string) => p.split('/').filter(Boolean).at(-1) ?? p;
const q = encodeURIComponent;

// ---- API response shapes ----

interface Me {
	username: string;
	cluster_host: string;
	cluster_username: string;
	home_dir: string;
}
interface Param {
	param: string;
	default: unknown;
	description: string;
	type: string;
	required?: boolean;
}
interface WorkflowTool {
	key?: string;
	phase?: number;
	name: string;
	purpose: string;
	/** Runs in every run (workflow_registry.MARGIE_SB_REQUIRED_TOOLS). */
	required?: boolean;
}
interface Workflow {
	id: string;
	label: string;
	tools: WorkflowTool[];
	configurable_params: Param[];
	/** The container images a run checks for before it starts. */
	containers?: { name: string }[];
}
interface LicenceStatus {
	accepted: boolean;
	usage_type: string | null;
	licensed_tools: string[];
	disabled_tools: string[];
}
interface JobRow {
	job_id: string;
	status: string;
	phase?: string | null;
	genome_path?: string | null;
	workflow?: string | null;
	work_dir?: string | null;
	selected_tools?: string | string[] | null;
	start_time?: string | null;
	end_time?: string | null;
	logs?: string | null;
	progress?: number | null;
	steps_done?: number | null;
	steps_total?: number | null;
	status_note?: string | null;
	/** Each tool's SLURM job on each genome, as the API tracks them (job_runner.py). */
	slurm_jobs?: { job_id: string; rule?: string | null; status: string; time?: string; genome?: string | null; source?: string }[] | null;
}
interface Entry {
	name: string;
	type: 'file' | 'directory';
	size: number;
	mtime?: number | null;
}

type Config = Record<string, any>;

/** Caches an async answer for `ms` and shares one in-flight request. */
class Cache<T> {
	#value: T | undefined;
	#at = 0;
	#pending: Promise<T> | null = null;
	constructor(
		private readonly load: () => Promise<T>,
		private readonly ms: number
	) {}
	get(): Promise<T> {
		if (this.#value !== undefined && Date.now() - this.#at < this.ms) return Promise.resolve(this.#value);
		this.#pending ??= this.load()
			.then((v) => {
				this.#value = v;
				this.#at = Date.now();
				return v;
			})
			.finally(() => (this.#pending = null));
		return this.#pending;
	}
	set(v: T) {
		this.#value = v;
		this.#at = Date.now();
	}
	drop() {
		this.#value = undefined;
	}
	/** The cached answer, however old, without asking again. */
	peek(): T | undefined {
		return this.#value;
	}
}

const me = new Cache<Me>(async () => {
	const m = await get<Me>('/v1/auth/me');
	backend.host = m.cluster_host;
	backend.user = m.cluster_username;
	return m;
}, 10 * 60_000);
const workflows = new Cache(() => get<Workflow[]>('/v1/ssh/workflows'), 10 * 60_000);
const config = new Cache(() => get<Config>('/v1/ssh/config'), 20_000);
const licence = new Cache(() => get<LicenceStatus>('/v1/license/status'), 60_000);
const status = new Cache(
	() => get<{ connected: boolean; host: string; detail?: string }>('/v1/ssh/status').catch((e) => ({ connected: false, host: '', detail: String(e.message ?? e) })),
	60_000
);
const jobs = new Cache(async () => {
	const d = await get<{ jobs: JobRow[] }>('/v1/ssh/jobs?page=1&page_size=50');
	return d.jobs ?? [];
}, 6_000);

/** Drops cached answers after the licence or config changes elsewhere (e.g. the Install page). */
export function forget(what: 'licence' | 'config' | 'all') {
	if (what === 'licence' || what === 'all') licence.drop();
	if (what === 'config' || what === 'all') {
		config.drop();
		installed.drop();
	}
	if (what === 'all') {
		jobs.drop();
		status.drop();
		resultList.drop();
	}
}

/** Returns the margie_sb workflow description from the API. */
async function workflow(): Promise<Workflow> {
	const w = (await workflows.get()).find((x) => x.id === WORKFLOW);
	if (!w) throw new ApiError(`This API does not offer the ${WORKFLOW} workflow.`, 404);
	return w;
}

/** Reads a dotted key from the config. */
function dig(obj: Config, dotted: string): unknown {
	return dotted.split('.').reduce<any>((o, k) => (o == null ? undefined : o[k]), obj);
}
/** Sets a dotted key in the config, creating objects on the way. */
function place(obj: Config, dotted: string, value: unknown) {
	const keys = dotted.split('.');
	const last = keys.pop() as string;
	let o = obj;
	for (const k of keys) {
		if (typeof o[k] !== 'object' || o[k] === null) o[k] = {};
		o = o[k];
	}
	o[last] = value;
}
const str = (v: unknown) => (v === null || v === undefined ? '' : typeof v === 'boolean' ? (v ? '1' : '0') : String(v));

/**
 * Per-genome domain and genetic code in config.yaml's margie_sb.genome_info.
 * Genomes missing either go to Prodigal unless GTDB-Tk is on. Set as one object,
 * not through place(), because file names contain dots.
 */
type GenomeInfo = Record<string, { domain?: string; genetic_code?: string | number }>;
const genomeInfo = (cfg: Config): GenomeInfo => {
	const v = dig(cfg, `${WORKFLOW}.genome_info`);
	return v && typeof v === 'object' ? (v as GenomeInfo) : {};
};
const genomeStem = (n: string) => n.replace(/\.gz$/i, '').replace(/\.(fasta|fna|fa)$/i, '');
/** Switch for running GTDB-Tk first; on unless config.yaml turns it off. */
const USE_GTDBTK = `${WORKFLOW}.use_gtdbtk`;
const useGtdbtk = (cfg: Config) => !['0', 'false', 'no', 'off'].includes(str(dig(cfg, USE_GTDBTK)).toLowerCase());
/** Draws the operon map for every gene, not only examples; read by the API when it starts a run. */
const FULL_OPERON_MAP = `${WORKFLOW}.run_full_operon_map`;

/** Expands a leading ~ to the cluster home, which SFTP does not do. */
async function expand(p: string): Promise<string> {
	if (!p.startsWith('~')) return p;
	return (await me.get()).home_dir + p.slice(1);
}

// ---- jobs ----

const STATUS: Record<string, Run['status']> = {
	completed: 'completed',
	success: 'completed',
	failed: 'failed',
	error: 'failed',
	cancelled: 'cancelled',
	canceled: 'cancelled'
};

/** Returns the first error-looking line in the last 60 lines of a log. */
function reasonIn(log: string): string {
	const lines = log.split('\n').slice(-60);
	const bad = /(ERROR|Error\b|error:|FAIL|fail(ed|s)\b|Traceback|not found|No such file|missing|could not|cannot|unable|refus|denied|invalid)/i;
	return lines.find((l) => bad.test(l))?.trim().slice(0, 240) ?? '';
}

/** Normalises selected_tools (list or comma/space string) to an array. */
function toList(v: string | string[] | null | undefined): string[] {
	if (!v) return [];
	if (Array.isArray(v)) return v.filter(Boolean).map(String);
	return String(v).split(/[,\s]+/).filter(Boolean);
}

/** Converts an API job row to the interface's Run shape. */
function toRun(j: JobRow): Run {
	const tools = toList(j.selected_tools);
	const input = j.genome_path ?? '';
	const status = STATUS[String(j.status || '').toLowerCase()] ?? 'running';
	const steps = j.steps_total ? `${j.steps_done ?? 0} of ${j.steps_total} steps` : '';
	const progress = status === 'completed' ? 100 : typeof j.progress === 'number' ? Math.round(j.progress) : undefined;
	const log = j.logs ?? '';
	return {
		id: j.job_id,
		kind: 'annotate',
		label: `Annotate ${baseName(input) || 'genomes'}${tools.length ? ` with ${tools.length} tools` : ''}`,
		args: [],
		command: `${j.workflow ?? WORKFLOW}${tools.length ? ` --tools ${tools.join(',')}` : ' (every tool)'}${input ? `  ${input}` : ''}`,
		started: j.start_time ?? '',
		finished: j.end_time ?? undefined,
		status,
		exitCode: null,
		tools,
		files: input ? [baseName(input)] : [],
		outputDir: j.work_dir ?? undefined,
		progress,
		progressText: [j.phase, steps].filter(Boolean).join(' | ') || undefined,
		reason: status === 'failed' || status === 'cancelled' ? reasonIn(log) || j.phase || '' : ''
	};
}

async function listRuns() {
	return { runs: (await jobs.get()).map(toRun) };
}

/**
 * Returns a job and the new part of its log. The API slices the log
 * (log_tail / log_offset); an older API sends it whole and it is sliced here.
 */
/** A SLURM job's rule as the Analyze grid's column: run_<tool> is that tool; the step rules map to their step. */
const RULE_COL: Record<string, string> = {
	run_gtdbtk_batch: 'gtdbtk',
	run_quast_batch: 'quast',
	run_report_figures_one_genome: 'figures',
	run_genome_viewer_one_genome: 'viewer',
	build_gene_evidence_report: 'evidence',
	run_operon_fingerprint: 'fingerprint',
	run_ani_batch: 'ani',
	run_aai_batch: 'aai',
	run_closest_organisms_batch: 'closest'
};
/** A cache hit is recorded under the bare tool name (job_runner.py), a SLURM job under its rule. */
const colOf = (rule: string) => RULE_COL[rule] ?? (/^run_[a-z0-9]+$/.test(rule) ? rule.slice(4) : /^[a-z0-9]+$/.test(rule) ? rule : null);
/** SLURM's elapsed time ("12:34", "1:02:03", "2-01:02:03") in ms. */
function elapsedMs(t: string | undefined): number {
	if (!t) return 0;
	const [days, rest] = t.includes('-') ? t.split('-') : ['0', t];
	const parts = rest.split(':').map(Number);
	const secs = parts.reduce((a, b) => a * 60 + b, 0);
	return (Number(days) * 86400 + secs) * 1000;
}
/** SLURM states of a job that has not started yet: not drawn as running. */
const QUEUED = new Set(['PENDING', 'SUBMITTED', 'CONFIGURING', 'REQUEUED', 'SUSPENDED']);
const median = (xs: number[]) => {
	const v = [...xs].sort((a, b) => a - b);
	return v.length ? (v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2) : 0;
};
/** Seconds each finished tool took in a list of SLURM jobs, by tool (cache hits say nothing about time). */
function toolSeconds(jobs: NonNullable<JobRow['slurm_jobs']>): Map<string, number[]> {
	const out = new Map<string, number[]>();
	for (const sj of jobs) {
		const tool = colOf(sj.rule ?? '');
		const secs = elapsedMs(sj.time) / 1000;
		if (!tool || String(sj.status || '').toUpperCase() !== 'COMPLETED' || secs <= 0) continue;
		out.set(tool, [...(out.get(tool) ?? []), secs]);
	}
	return out;
}

/*
 * Each tool's usual time on this cluster, from the user's recent finished runs (their SLURM
 * jobs are kept in the job history). Worked out once in the background and kept for six
 * hours in this browser; until then, and for a tool never run before, the run's own
 * finished genomes are the estimate (clockOf).
 */
const TIMES_KEY = 'margie_tool_times';
const TIMES_FOR = 6 * 3600_000;
let usualTimes: Record<string, number> = {};
let timesAt = 0;
let timesLoading = false;
try {
	const kept = JSON.parse(localStorage.getItem(TIMES_KEY) ?? 'null');
	if (kept && typeof kept.at === 'number' && kept.times) [usualTimes, timesAt] = [kept.times, kept.at];
} catch {
	// Nothing kept, or storage blocked: worked out on the first run shown.
}
async function loadUsualTimes() {
	if (timesLoading || Date.now() - timesAt < TIMES_FOR) return;
	timesLoading = true;
	try {
		const finished = (await jobs.get()).filter((r) => String(r.status || '').toLowerCase() === 'completed').slice(0, 8);
		const all = new Map<string, number[]>();
		for (const r of finished) {
			try {
				const j = await get<JobRow>(`/v1/ssh/job_status/${q(r.job_id)}?log_tail=1`);
				for (const [t, xs] of toolSeconds(j.slurm_jobs ?? [])) all.set(t, [...(all.get(t) ?? []), ...xs]);
			} catch {
				// One unreadable run does not stop the rest.
			}
		}
		usualTimes = Object.fromEntries([...all].map(([t, xs]) => [t, median(xs)]));
		timesAt = Date.now();
		try {
			localStorage.setItem(TIMES_KEY, JSON.stringify({ at: timesAt, times: usualTimes }));
		} catch {
			// Kept for this page only.
		}
	} finally {
		timesLoading = false;
	}
}

/**
 * The run's tool clock from its SLURM jobs: one entry per tool and genome with whether it
 * finished, failed or is still going, plus each tool's usual time so a running tool's pie can
 * fill. A batch rule's entry has no genome and stands for all. Queued jobs are left out: a tool
 * is not drawn as running until SLURM starts it.
 */
function clockOf(j: JobRow): ToolClock | null {
	const jobs = j.slurm_jobs ?? [];
	if (!jobs.length) return null;
	void loadUsualTimes();
	const now = Date.now();
	const started = new Map<string, ToolClock['started'][number]>();
	for (const sj of jobs) {
		const tool = colOf(sj.rule ?? '');
		if (!tool) continue;
		const s = String(sj.status || '').toUpperCase();
		if (QUEUED.has(s)) continue;
		const ok = s === 'COMPLETED' || s === 'CACHED';
		const failed = ['FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'].includes(s);
		const key = `${tool}\t${sj.genome ?? ''}`;
		// The latest job of a tool on a genome counts (a retry replaces an earlier failure).
		const prev = started.get(key);
		if (prev && prev.ok) continue;
		started.set(key, { tool, genome: sj.genome ?? '', start: now - elapsedMs(sj.time), last: now, ok, failed });
	}
	// Each step's SLURM jobs, its database load (load_<tool>_to_db) with them, for the step's popup.
	const jobsBy: Record<string, ToolJob[]> = {};
	for (const sj of jobs) {
		const rule = sj.rule ?? '';
		const col = colOf(rule) ?? /^load_([a-z0-9]+?)(?:_perdb)?_to_db$/.exec(rule)?.[1];
		if (col && sj.job_id) (jobsBy[`${col}\t${sj.genome ?? ''}`] ??= []).push({ id: String(sj.job_id), rule, status: String(sj.status || '').toLowerCase() });
	}
	// This run's own finished genomes first (same cluster, same load), then the user's history.
	const here = Object.fromEntries([...toolSeconds(jobs)].map(([t, xs]) => [t, median(xs)]));
	return { typical: { ...usualTimes, ...here }, started: [...started.values()], now, jobs: jobsBy };
}

async function runDetail(id: string, params: URLSearchParams) {
	const tail = Number(params.get('tail')) || 0;
	const offset = Math.max(0, Number(params.get('offset')) || 0);
	const ask = tail ? `?log_tail=${tail}` : `?log_offset=${offset}`;
	const j = await get<JobRow & { logs_size?: number; logs_offset?: number }>(`/v1/ssh/job_status/${q(id)}${ask}`);
	const got = j.logs ?? '';
	const clock = clockOf(j);
	if (typeof j.logs_size === 'number') {
		return { run: toRun(j), step: j.phase ?? '', log: { text: got, offset: j.logs_size, size: j.logs_size }, clock };
	}
	const text = tail ? got.slice(-tail) : got.slice(Math.min(offset, got.length));
	return { run: toRun(j), step: j.phase ?? '', log: { text, offset: got.length, size: got.length }, clock };
}

/** Builds the tool selection from the request and config, then submits the workflow. */
async function startRun(body: { kind?: string; tools?: string[]; all?: boolean; genomes?: string[] }) {
	if (body.kind !== 'annotate') return notHere('Tools and databases on the cluster are installed by its administrators, not from here.');
	const w = await workflow();
	const cfg = await config.get();
	const lic = await licence.get();
	const known = new Map(w.tools.filter((t) => t.key).map((t) => [t.key as string, t]));
	const disabled = new Set(lic.disabled_tools);
	// The tools every run needs (labeling and scoring read them) come with any choice.
	const required = w.tools.filter((t) => t.required && t.key).map((t) => t.key as string);
	const chosen = new Set([...ALWAYS, ...required, ...(body.tools ?? [])]);
	// GTDB-Tk follows its switch only, never the tool list.
	chosen.delete('gtdbtk');
	if (useGtdbtk(cfg)) chosen.add('gtdbtk');
	// The envelope stage reads these.
	for (const k of ENVELOPE_INPUTS) chosen.add(k);
	// Always sent as a list: with none, the pipeline would run config.yaml's default_selected_tools
	// (or its own defaults) instead of the tools picked here.
	const selected = [...chosen].filter((k) => known.has(k) && !disabled.has(k) && !LATER.has(k));
	const input = str(dig(cfg, `${WORKFLOW}.input_path`));
	const output = str(dig(cfg, `${WORKFLOW}.output_path`));
	if (!input) throw new ApiError('Type the folder your genomes are in first (step 1).', 400);
	// A subset is staged by the API into its own folder; omitted, the whole input folder runs.
	const genomes = body.genomes?.length ? body.genomes : null;
	const r = await call<{ job_id: string; output_dir?: string }>('POST', '/v1/ssh/run_workflow', {
		workflow: WORKFLOW,
		genome_path: input,
		output_dir: output || null,
		selected_tools: selected,
		...(genomes ? { genomes } : {})
	});
	jobs.drop();
	return {
		run: toRun({
			job_id: r.job_id,
			status: 'running',
			phase: 'Submitting',
			genome_path: input,
			workflow: WORKFLOW,
			work_dir: r.output_dir ?? null,
			selected_tools: selected,
			start_time: new Date().toISOString()
		})
	};
}

/** Cancels a job. */
async function stopRun(id: string) {
	await call('POST', `/v1/ssh/cancel_job/${q(id)}`);
	jobs.drop();
	return { ok: true };
}

/** Resumes (after what finished) or restarts a failed or stopped job. */
async function relaunchRun(id: string, how: 'resume' | 'restart') {
	await call('POST', `/v1/ssh/${how}_job/${q(id)}`);
	jobs.drop();
	return { ok: true };
}

// ---- genomes and tools ----

/** Lists a folder on the cluster over SFTP. */
async function browse(path: string): Promise<{ path: string; entries: Entry[] }> {
	return get(`/v1/ssh/browse?path=${q(await expand(path))}`);
}

/** Lists genome files in the input folder (or the single input file) with their genome_info. */
async function listGenomes() {
	const cfg = await config.get();
	const folder = str(dig(cfg, `${WORKFLOW}.input_path`));
	const empty = { folder, genomes: [] as Genome[], nested: [], runGtdbtk: useGtdbtk(cfg), geneticCodes: ['11', '4', '25'] };
	if (!folder) return empty;
	const info = genomeInfo(cfg);
	const infoOf = (name: string) => info[name] ?? info[genomeStem(name)] ?? {};
	const asGenome = (e: Entry): Genome => {
		const i = infoOf(e.name);
		const d = str(i.domain).toLowerCase();
		return {
			name: e.name,
			size: e.size,
			domain: d.startsWith('b') ? 'Bacteria' : d.startsWith('a') ? 'Archaea' : '',
			genetic_code: /^\d+$/.test(str(i.genetic_code)) ? str(i.genetic_code) : ''
		};
	};
	try {
		const d = await browse(folder);
		return { ...empty, genomes: d.entries.filter((e) => e.type === 'file' && GENOME_EXT.test(e.name)).map(asGenome) };
	} catch (e) {
		// The input may be a single genome file.
		if (e instanceof ApiError && e.status === 400 && GENOME_EXT.test(folder)) {
			const parent = folder.slice(0, folder.lastIndexOf('/')) || '/';
			const d = await browse(parent).catch(() => null);
			const one = d?.entries.find((x) => x.name === baseName(folder));
			return { ...empty, genomes: one ? [asGenome(one)] : [] };
		}
		if (e instanceof ApiError && e.status === 404) return empty;
		throw e;
	}
}

/**
 * Saves the Genomes table's domain and genetic code into margie_sb.genome_info.
 * Other entries are kept; a row with both fields cleared is removed.
 */
async function saveGenomeInfo(body: { rows?: { name: string; domain: string; genetic_code: string }[] }) {
	const cfg = structuredClone(await get<Config>('/v1/ssh/config'));
	const info: GenomeInfo = { ...genomeInfo(cfg) };
	for (const r of body.rows ?? []) {
		delete info[genomeStem(r.name)];
		if (r.domain || r.genetic_code) info[r.name] = { domain: r.domain, genetic_code: r.genetic_code };
		else delete info[r.name];
	}
	const section = (cfg[WORKFLOW] ??= {}) as Config;
	section.genome_info = info;
	await call('PUT', '/v1/ssh/config', cfg);
	config.set(cfg);
	return { ok: true };
}

/** Returns a stores answer and drops cached config and assets, which it may have changed. */
async function storesAnswer<T>(p: Promise<T>): Promise<T> {
	const r = await p;
	config.drop();
	installed.drop();
	return r;
}

/** Uploadable genome file names: the workflow's extensions, excluding gzipped (not text). */
const UPLOADABLE = /^[A-Za-z0-9._-]+\.(fasta|fa|fna)$/i;

/**
 * Uploads FASTA files into the cluster input folder via /browse_save.
 * Existing files are never overwritten.
 */
async function addGenomes(form: FormData) {
	const folder = await expand(str(dig(await config.get(), `${WORKFLOW}.input_path`)));
	if (!folder) throw new ApiError('Type the folder on the cluster that genomes go in first (step 1 on Analyze).', 400);
	if (GENOME_EXT.test(folder)) throw new ApiError('The input path is one genome file; make it a folder to add more.', 400);
	const there = new Set((await browse(folder).catch(() => ({ entries: [] as Entry[] }))).entries.map((e) => e.name));
	const added: string[] = [];
	const skipped: string[] = [];
	for (const f of form.getAll('files')) {
		if (!(f instanceof File)) continue;
		if (!UPLOADABLE.test(f.name)) {
			skipped.push(`${f.name}: the cluster reads .fasta, .fa and .fna`);
			continue;
		}
		if (there.has(f.name)) {
			skipped.push(`${f.name}: already there`);
			continue;
		}
		const content = await f.text();
		if (!content.trimStart().startsWith('>')) {
			skipped.push(`${f.name}: not FASTA`);
			continue;
		}
		await call('POST', '/v1/ssh/browse_save', { path: `${folder}/${f.name}`, content });
		added.push(f.name);
	}
	if (!added.length) throw new ApiError(skipped.length ? `Nothing added. ${skipped.join('; ')}.` : 'No files to add.', 400);
	const { genomes } = await listGenomes();
	return { added, skipped, genomes };
}

/** Lists optional annotation tools with their licence state. */
/** Comparison and the LLM layer: not offered yet, so never in a run (lib/license NOT_YET). */
const LATER = NOT_YET;

async function listTools(): Promise<{ annotation: Tool[] }> {
	const [w, lic] = await Promise.all([workflow(), licence.get()]);
	const disabled = new Set(lic.disabled_tools);
	const annotation = w.tools
		// GTDB-Tk is a separate switch, not a tool.
		.filter((t) => t.key && !ALWAYS.includes(t.key) && t.key !== 'envelope' && t.key !== 'gtdbtk' && !LATER.has(t.key))
		.map((t) => ({
			name: t.key as string,
			gated: disabled.has(t.key as string),
			licensed: !disabled.has(t.key as string),
			gramDependent: (t.phase ?? 0) > ENVELOPE_PHASE && (t.phase ?? 0) < 9,
			phase: t.phase,
			label: t.name,
			required: !!t.required
		}));
	return { annotation };
}

// ---- installed assets ----

/** One row of GET /v1/ssh/assets (the backend's services/tool_assets.py). */
interface AssetRow {
	id: string;
	kind: 'image' | 'database';
	tool: string;
	label: string;
	path: string;
	status: 'ok' | 'missing' | 'unknown';
	/** GTDB-Tk and the LLM layer: run only when chosen. */
	optional: boolean;
}

/**
 * Checks each container image and database where the workflow looks for it,
 * using the backend's pre-run check. Unreadable folders are "unknown", not "missing".
 */
const installed = new Cache(async (): Promise<CheckRow[]> => {
	const d = await get<{ rows: AssetRow[] }>('/v1/ssh/assets');
	return d.rows.map((r) => {
		const status: CheckRow['status'] = r.status === 'missing' && r.optional ? 'optional' : r.status;
		return {
			status,
			name: r.tool,
			kind: r.kind,
			detail: status === 'unknown' ? `${r.path} (its folder cannot be read from your account)` : r.path,
			section: r.kind === 'image' ? 'Containers' : 'Databases',
			advice: false
		};
	});
}, 60_000);

// ---- readiness ----

/** Builds the setup overview rows: connection, SLURM, licence, history, assets, output. */
async function overview(): Promise<Overview> {
	// Failing parts show as not ready instead of failing the whole answer.
	const [m, s, cfg, lic] = await Promise.all([
		me.get(),
		status.get(),
		config.get().catch((): Config => ({})),
		licence.get().catch((): LicenceStatus => ({ accepted: false, usage_type: null, licensed_tools: [], disabled_tools: [] }))
	]);
	const account = str(dig(cfg, 'compute.cluster_default.account'));
	const partition = str(dig(cfg, 'compute.cluster_default.partition'));
	const db = str(cfg.main_database);
	const output = str(dig(cfg, `${WORKFLOW}.output_path`));
	const rows: SetupRow[] = [
		{
			id: 'cluster',
			label: 'Cluster',
			value: m.cluster_host,
			detail: s.connected ? `Signed in as ${m.cluster_username}` : (s.detail ?? 'Not reachable'),
			tone: s.connected ? 'ok' : 'danger',
			required: true,
			href: '/install'
		},
		// Account and partition are separate rows so neither reads as part of the other.
		{
			id: 'account',
			label: 'SLURM account',
			value: account || 'Not set',
			detail: account ? 'Every job is charged to this account' : 'Every job is charged to one; none is set yet',
			tone: account ? 'ok' : 'warn',
			required: true,
			href: '/settings#compute.cluster_default.account'
		},
		{
			id: 'partition',
			label: 'Main partition',
			value: partition || 'Cluster default',
			detail: partition ? 'The queue jobs are submitted to' : 'Jobs go to whichever queue the cluster uses by default',
			// Optional: the cluster's default partition is a normal choice.
			tone: 'ok',
			required: false,
			href: '/settings#compute.cluster_default.partition'
		},
		{
			id: 'terms',
			label: 'Licence terms',
			value: lic.accepted ? 'Accepted' : 'Not accepted',
			detail: lic.accepted ? `For ${lic.usage_type ?? 'your'} use` : 'Accepted once on Analyze, before the first run',
			tone: lic.accepted ? 'ok' : 'warn',
			required: true,
			href: '/analyze#licence'
		},
		{
			id: 'history',
			label: 'Job history',
			value: db ? baseName(db) : 'Not set',
			detail: db ? 'Where the cluster records your runs' : 'Runs are not recorded without it',
			tone: db ? 'ok' : 'warn',
			required: true,
			href: '/settings#main_database'
		},
		...(await installed
			.get()
			.then((rows): SetupRow[] => {
				const tally = (kind: string) => {
					const of = rows.filter((r) => r.kind === kind && r.status !== 'optional');
					const ok = of.filter((r) => r.status === 'ok').length;
					const unknown = of.filter((r) => r.status === 'unknown').length;
					return { ok, total: of.length, unknown };
				};
				const im = tally('image');
				const db = tally('database');
				const line = (t: { ok: number; total: number; unknown: number }, all: string) =>
					t.ok === t.total ? all : t.unknown === t.total ? 'Their folder cannot be read from your account' : `${t.total - t.ok - t.unknown} not where the config points`;
				// Informational: the run's own pre-flight check decides.
				return [
					{ id: 'cluster-tools', label: 'Tools', value: `${im.ok} / ${im.total}`, detail: line(im, 'All in the containers folder'), tone: im.ok === im.total ? 'ok' : 'warn', required: false, href: '/install#installed' },
					{ id: 'cluster-data', label: 'Reference data', value: `${db.ok} / ${db.total}`, detail: line(db, 'All in the databases folder'), tone: db.ok === db.total ? 'ok' : 'warn', required: false, href: '/install#installed' }
				];
			})
			.catch((): SetupRow[] => [])),
		{
			id: 'output',
			label: 'Results folder',
			value: output ? baseName(output) : 'Home folder',
			detail: output || m.home_dir,
			tone: 'neutral',
			required: false,
			href: '/settings#margie_sb.output_path'
		}
	];
	return {
		user: m.cluster_username,
		runtime: { setting: 'apptainer', active: 'apptainer', label: 'Apptainer on the cluster', ready: s.connected },
		runtimes: [],
		recommended: null,
		repo: { ok: true, path: '', reason: '', containers: [], databases: [] },
		python: { ready: true, version: '', path: '', base: null },
		licences: { tools: lic.disabled_tools, accepted: lic.licensed_tools, intendedUse: lic.usage_type ?? '' },
		gtdbtk: false,
		machine: { os: 'linux', arch: '', chip: m.cluster_host, cores: 0, memory: 0, diskFree: null, dbRoot: str(dig(cfg, `${WORKFLOW}.db_root`)) },
		rows
	};
}

// ---- settings ----

const PATHS: Record<string, string> = {
	// The folder the genomes, results and databases folders go in when left empty.
	working_folder: 'Working folder',
	input_path: 'Genomes folder',
	output_path: 'Results folder',
	sif_path: 'Containers folder',
	db_root: 'Databases folder',
	backup_root: 'Backup location',
	// Where margie-build is, which builds containers and databases (Install).
	build_repo: 'Build recipes (margie-build)'
};
// The databases a run reads (set to the working copies by the API, services/user_stores.py; editable
// for files that were moved) and where a first run copies each one from.
// Labelled "Part: name", so Settings shows them under parts: what every run needs, what runs read
// and grow, where results are kept, and the backups (a part of their own, folded).
export const DB_NEEDED = 'Needed for every run';
export const DB_READ = 'Read and added to by runs';
export const DB_KEPT = 'Where results are kept';
export const DB_BACKUPS = 'Backups';
const EXTENDED: Record<string, string> = {
	shared_root: `${DB_NEEDED}: Group folder (your group's shared MARGIE folder)`,
	stores_root: `${DB_NEEDED}: Databases folder (your own copies of MARGIE's databases)`,
	'operon_database.occ_reference_pkl': `${DB_READ}: Operon reference (occ_reference.pkl)`,
	'fingerprint_database.path': `${DB_READ}: Fingerprint database (fingerprint-database.tsv)`,
	'report_figures.operon_db': `${DB_READ}: Operon fingerprint database, label-ordered`,
	'genome_pool.path': `${DB_READ}: Genome pool folder`,
	'scoring_results_historical.path': `${DB_KEPT}: Scoring archive folder`,
	'final_tables_depot.path': `${DB_KEPT}: Final tables folder`,
	'sqlite_pipeline_snapshot.path': `${DB_BACKUPS}: Database snapshots folder`,
	'stores.base.job_db': `${DB_BACKUPS}: First run copies the job database from`,
	'stores.base.occ': `${DB_BACKUPS}: First run copies the operon reference from`,
	'stores.base.fingerprint': `${DB_BACKUPS}: First run copies the fingerprint databases from`,
	'stores.base.genome_pool': `${DB_BACKUPS}: First run copies the genome pool from`
};
/** The order of the parts in Settings → Databases. */
export const DB_PARTS = [DB_NEEDED, DB_READ, DB_KEPT, DB_BACKUPS];
const COMPUTE: Record<string, string> = {
	account: 'SLURM account',
	partition: 'Main partition',
	default_runtime: 'Time per job (min)',
	default_mem_mb: 'Memory per job (MB)',
	max_jobs: 'Jobs at once',
	driver_walltime: 'Time limit for a run'
};
/** Notes Settings shows (in Guided mode, or under a section's ?) in place of the workflow's own. */
const NOTE: Record<string, string> = {
	'compute.cluster_default.partition':
		'The partition every job goes to unless its phase or tool names another. Give a phase or a tool its own (highmem for large memory, a GPU partition for GPU tools) under Phases or Per tool.'
};
const FIELD: Record<string, string> = {
	threads: 'threads',
	mem_mb: 'memory (MB)',
	runtime: 'time (min)',
	partition: 'partition',
	db: 'database',
	sif: 'container',
	at_once: 'genomes at once'
};
const DEFAULTS: Record<string, string> = {
	default_threads: 'Threads per tool',
	default_mem_mb: 'Memory per tool (MB)',
	default_runtime: 'Time per tool (min)'
};
/** Local setting names mapped to cluster config keys, so the same controls work on both. */
const ALIASES: Record<string, string> = {
	USER_INPUT_DIR: `${WORKFLOW}.input_path`,
	OUTPUT_ROOT: `${WORKFLOW}.output_path`,
	LOCAL_PARALLEL_TOOLS: `${WORKFLOW}.phase4.max_parallel_tools`
};

const humanize = (s: string) => s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

/** Returns a setting's label and Settings group from its config key. */
function describeParam(p: Param, toolLabel: Map<string, string>): { label: string; group: string } {
	const key = p.param;
	if (key === 'main_database') return { label: `${DB_NEEDED}: MARGIE database (SQLite)`, group: 'Databases' };
	if (key.startsWith('compute.cluster_default.')) {
		const k = key.slice('compute.cluster_default.'.length);
		return { label: COMPUTE[k] ?? humanize(k), group: 'Cluster' };
	}
	// A per-tool database folder override.
	if (key.startsWith('db.')) {
		const t = key.slice(3);
		return { label: `${toolLabel.get(t) ?? humanize(t)} database`, group: 'Other folders' };
	}
	const rest = key.slice(WORKFLOW.length + 1);
	// Where backups go belongs with the backups.
	if (rest === 'backup_root') return { label: `${DB_BACKUPS}: Backup location (on depot)`, group: 'Databases' };
	if (PATHS[rest]) return { label: PATHS[rest], group: 'Folders' };
	if (EXTENDED[rest]) return { label: EXTENDED[rest], group: 'Databases' };
	if (isWorkflowPathParam(key)) return { label: humanize(rest), group: 'Other folders' };
	const [head, field] = rest.split('.');
	if (!field) return { label: DEFAULTS[head] ?? humanize(head), group: 'Phases' };
	const phase = head.match(/^phase(\d+)$/);
	if (phase) {
		// "Phase 6: Partition", so Settings lays the phases out as a table, as it does the tools.
		const what = field === 'partition' ? 'Partition' : field === 'max_parallel_genomes' ? 'Genomes at once' : field === 'max_parallel_tools' ? 'Tools at once' : humanize(field);
		return { label: `Phase ${phase[1]}: ${what}`, group: 'Phases' };
	}
	// "Tool: field", so Settings lays the tools out as a table: a row each, a column per field.
	return { label: `${toolLabel.get(head) ?? humanize(head)}: ${FIELD[field] ?? humanize(field)}`, group: 'Per tool' };
}

const TYPES: Record<string, Setting['type']> = { int: 'int', integer: 'int', path: 'path', bool: 'flag', boolean: 'flag' };

/** Lists workflow settings with values from config.yaml, plus alias and switch entries. */
async function settingsList(): Promise<{ settings: Setting[]; configMissing: boolean }> {
	const [w, cfg] = await Promise.all([workflow(), config.get()]);
	const toolLabel = new Map(w.tools.filter((t) => t.key).map((t) => [t.key as string, t.name]));
	const params: Param[] = [
		{ param: 'main_database', default: '', description: 'The main MARGIE database on the cluster: every run’s results, cached tool outputs and the job history.', type: 'path' },
		...w.configurable_params
	];
	const settings: Setting[] = params.map((p) => {
		const { label, group } = describeParam(p, toolLabel);
		const description = NOTE[p.param] ?? p.description;
		const value = str(dig(cfg, p.param));
		const def = str(p.default);
		return {
			key: p.param,
			label,
			group,
			type: TYPES[p.type] ?? 'text',
			description,
			value,
			default: def,
			// The history database has no default to go back to: the API picks one per account.
			overridden: p.param !== 'main_database' && value !== '' && value !== def
		};
	});
	// Aliases have no group, so Settings lists each setting once.
	for (const [alias, real] of Object.entries(ALIASES)) {
		const s = settings.find((x) => x.key === real);
		settings.push({ key: alias, label: s?.label ?? alias, group: '', type: s?.type ?? 'text', description: '', value: s?.value ?? '', default: s?.default ?? '', overridden: false });
	}
	// Automatic: RASTtk where domain and code are known, Prodigal otherwise.
	settings.push({ key: 'GENE_CALLER', label: 'Gene caller', group: '', type: 'text', description: '', value: 'auto', default: 'auto', overridden: false });
	const gtdbtk = useGtdbtk(cfg) ? '1' : '0';
	settings.push({ key: 'RUN_GTDBTK', label: 'Classify with GTDB-Tk', group: '', type: 'flag', description: '', value: gtdbtk, default: '1', overridden: gtdbtk === '0' });
	const operons = ['1', 'true'].includes(str(dig(cfg, FULL_OPERON_MAP)).toLowerCase()) ? '1' : '0';
	settings.push({
		key: 'FULL_OPERON_MAP',
		label: 'Full-genome operon map',
		group: 'Phases',
		type: 'flag',
		description: 'Operon diagrams for every gene of each genome, not only representative examples. About 3 to 4 minutes more per genome, after scoring; every run applies it while on.',
		value: operons,
		default: '0',
		overridden: operons === '1'
	});
	// No config.yaml on the cluster yet: Settings offers to write the default one.
	return { settings, configMissing: !Object.keys(cfg ?? {}).length };
}

/** Writes the default config.yaml (the API fills in the account's own SLURM defaults). */
async function createDefaultConfig() {
	await call('POST', '/v1/ssh/config/create-default');
	config.drop();
	installed.drop();
	return settingsList();
}

/** Puts back the default config.yaml or workflow; the file it replaces is kept beside it. */
async function restoreDefault(body: { which?: string }) {
	const d = await call<{ path: string; backup: string | null }>('POST', '/v1/ssh/restore_default', body);
	if (body.which === 'config') {
		config.drop();
		installed.drop();
	}
	return d;
}

/** Writes changed settings into config.yaml, converting by parameter type. */
async function saveSettings(body: { values?: Record<string, string> }) {
	const values = body.values ?? {};
	const w = await workflow();
	const types = new Map(w.configurable_params.map((p) => [p.param, p.type]));
	const cfg = structuredClone(await get<Config>('/v1/ssh/config'));
	// A new working folder takes its margie-databases, margie-input and margie-output along: settings
	// pointing at those in the old one point at the new one (a path chosen apart from it stays; files stay put).
	const wf = `${WORKFLOW}.working_folder`;
	const given = new Set(Object.keys(values).map((k) => ALIASES[k] ?? k));
	const before = str(dig(cfg, wf)).replace(/\/+$/, '');
	const after = String(values[wf] ?? '').trim().replace(/\/+$/, '');
	if (before && after && after !== before) {
		for (const [key, sub] of [['stores_root', 'margie-databases'], ['input_path', 'margie-input'], ['output_path', 'margie-output']]) {
			const at = `${WORKFLOW}.${key}`;
			if (!given.has(at) && str(dig(cfg, at)).replace(/\/+$/, '') === `${before}/${sub}`) place(cfg, at, `${after}/${sub}`);
		}
	}
	for (const [key0, raw] of Object.entries(values)) {
		if (key0 === 'GENE_CALLER') continue;
		if (key0 === 'RUN_GTDBTK') {
			place(cfg, USE_GTDBTK, String(raw) === '1');
			continue;
		}
		if (key0 === 'FULL_OPERON_MAP') {
			place(cfg, FULL_OPERON_MAP, String(raw) === '1');
			continue;
		}
		const key = ALIASES[key0] ?? key0;
		const type = TYPES[types.get(key) ?? ''] ?? 'text';
		const text = String(raw).trim();
		const value = type === 'int' ? (text === '' ? null : Number.isFinite(Number(text)) ? Number(text) : text) : type === 'flag' ? text === '1' : text;
		place(cfg, key, value);
	}
	await call('PUT', '/v1/ssh/config', cfg);
	config.set(cfg);
	// Folders may have moved, so assets are checked again.
	installed.drop();
	return settingsList();
}

// ---- files ----

/** The group's shared MARGIE folder, which Files offers as Depot until another is opened:
 *  margie_sb.shared_root, else the folder the API's prebuilt databases are in. */
async function groupFolder(cfg: Config): Promise<string> {
	const set = str(dig(cfg, `${WORKFLOW}.shared_root`));
	if (set) return set;
	try {
		const s = await get<{ stores?: { base?: string }[] }>('/v1/ssh/stores');
		const base = s.stores?.find((x) => x.base)?.base ?? '';
		const at = base.indexOf('/databases/margie-generated-databases');
		return at > 0 ? base.slice(0, at) : '';
	} catch {
		return '';
	}
}
const depotKey = (m: Me) => `margie.depot.${m.cluster_username}@${m.cluster_host}`;

/** Remembers the last depot folder opened in Files, for this account, as its Depot shortcut. */
export function rememberDepot(path: string) {
	const m = me.peek();
	if (!m || !/^\/depot\/[^/]+/.test(path)) return;
	try {
		localStorage.setItem(depotKey(m), path);
	} catch {
		// not remembered: the default stays
	}
}

/** Returns the file browser's shortcut folders, deduplicated. */
async function places() {
	const [m, cfg] = await Promise.all([me.get(), config.get()]);
	const at = (k: string) => str(dig(cfg, `${WORKFLOW}.${k}`));
	let depot = '';
	try {
		depot = localStorage.getItem(depotKey(m)) || '';
	} catch {
		// not remembered
	}
	depot ||= await groupFolder(cfg);
	const cluster = m.cluster_host.split('.')[0];
	const list = [
		{ label: 'Home', path: m.home_dir },
		// Your scratch on this cluster, and the depot folder last opened here (the group's by default).
		{ label: 'Scratch', path: cluster && m.cluster_username ? `/scratch/${cluster}/${m.cluster_username}` : at('stores_root') },
		{ label: 'Depot', path: depot },
		{ label: 'Genomes in', path: at('input_path') },
		{ label: 'Results', path: at('output_path') },
		// MARGIE's own databases (the working folder) and the tools' reference databases.
		{ label: 'MARGIE databases', path: at('stores_root') },
		{ label: 'Reference databases', path: at('db_root') },
		{ label: 'Containers', path: at('sif_path') },
		{ label: 'The cluster', path: '/' }
	];
	const seen = new Set<string>();
	const out = [];
	for (const p of list) {
		const path = p.path ? await expand(p.path) : '';
		if (!path || seen.has(path)) continue;
		seen.add(path);
		out.push({ label: p.label, path });
	}
	return { places: out };
}

/** Lists a folder in the file browser's shape. */
async function listFolder(path: string) {
	const d = await browse(path);
	return {
		path: d.path,
		entries: d.entries.map((e) => ({
			name: e.name,
			type: e.type,
			size: e.size,
			mtime: e.mtime ? new Date(e.mtime * 1000).toISOString() : ''
		}))
	};
}

/**
 * Finds the job whose folder holds a path. Job files stream whole; elsewhere
 * the API returns only the first megabyte of a text file.
 */
async function jobFor(path: string): Promise<{ id: string; rel: string } | null> {
	const rows = await jobs.get().catch(() => [] as JobRow[]);
	for (const j of rows) {
		const dir = j.work_dir?.replace(/\/$/, '');
		if (dir && path.startsWith(dir + '/')) return { id: j.job_id, rel: path.slice(dir.length + 1) };
	}
	return null;
}

/**
 * Returns a file as a Blob: a job's file in full; elsewhere the head of a text file, or with
 * `whole` (an image, a map, a PDF to show) the whole file by its path.
 */
export async function fileBlob(path: string, whole = false): Promise<Blob> {
	const abs = await expand(path);
	const job = await jobFor(abs);
	if (job) return readWithProgress(await fetchRaw(`/v1/ssh/download_file/${q(job.id)}?path=${q(job.rel)}`), abs);
	if (whole) return readWithProgress(await fetchRaw(`/v1/ssh/download_path?path=${q(abs)}`), abs);
	const d = await get<{ content: string; binary: boolean; truncated: boolean }>(`/v1/ssh/browse_view?path=${q(abs)}`);
	if (d.binary) throw new ApiError('Outside a job’s folder only text files can be opened from the cluster.', 415);
	return new Blob([d.content], { type: 'text/plain' });
}

/** A cluster path's kind, size in bytes (a folder's total) and file count. */
export async function pathSize(path: string): Promise<{ path: string; kind: 'file' | 'directory'; bytes: number | null; files: number | null }> {
	return get(`/v1/ssh/path_size?path=${q(await expand(path))}`);
}

/** Downloads any file the account can read, whole, or a folder zipped on the cluster; with the name it is saved under. */
export async function downloadBlob(path: string): Promise<{ blob: Blob; name: string }> {
	const res = await fetchRaw(`/v1/ssh/download_path?path=${q(await expand(path))}`);
	const name = res.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1] ?? path.split('/').filter(Boolean).at(-1) ?? 'download';
	return { blob: await res.blob(), name };
}

/** Returns a text file's content from the cluster. */
async function readText(path: string) {
	const abs = await expand(path);
	const d = await get<{ content: string; binary: boolean; truncated: boolean }>(`/v1/ssh/browse_view?path=${q(abs)}`);
	return { path: abs, content: d.content, binary: d.binary, truncated: d.truncated, size: d.content.length };
}

/** Keeps the last four files read as text, so a FINAL table crosses the network once. */
const texts = new Map<string, Promise<string>>();
function fileText(path: string): Promise<string> {
	let text = texts.get(path);
	if (!text) {
		text = fileBlob(path).then((b) => b.text());
		text.catch(() => texts.delete(path));
		texts.set(path, text);
		while (texts.size > 4) texts.delete(texts.keys().next().value as string);
	}
	return text;
}

/** Parsed tables, the last four kept. */
const tables = new Map<string, Table>();

/** Loads a table (TSV/CSV/GFF or xlsx) and returns the requested page of it. */
async function tablePage(params: URLSearchParams) {
	const path = await expand(params.get('path') ?? '');
	const kind = TABLE_EXT[extOf(path)];
	if (!kind) throw new ApiError('Not a table file.', 400);
	let table = tables.get(path);
	if (!table && kind === 'xlsx') {
		// ExcelJS is large, so it is loaded only when a workbook opens.
		const ExcelJS = (await import('exceljs')).default;
		const wb = new ExcelJS.Workbook();
		await wb.xlsx.load(await (await fileBlob(path)).arrayBuffer());
		const palette: CellStyle[] = [];
		table = { kind, sheets: sheetsOf(wb, palette), palette };
	} else if (!table) {
		table = { kind, sheets: [parseDelimited(await fileText(path), kind as 'tsv' | 'csv' | 'gff', baseName(path))], palette: [] };
	}
	if (!tables.has(path)) {
		tables.set(path, table);
		while (tables.size > 4) tables.delete(tables.keys().next().value as string);
	}
	return queryLoaded(table, queryFromParams(params), { path, name: baseName(path) });
}

// ---- results ----

/**
 * Run output layout: <run>/<genome>/ beside run-level folders. The FINAL table
 * sits in scoring/, or at the genome's top once outputs are reorganised.
 */
const TABLE_NAME = 'FINAL_ANNOTATION_WITH_CONFIDENCE.tsv';
const EXCEL_NAME = 'FINAL_ANNOTATION_WITH_CONFIDENCE.xlsx';
const VIEWER_NAME = 'FINAL_GENOME_VIEWER.html';
const PER_TOOL = 'per-tool-phased-output';
/** Run-level folders (reorganize_outputs.py's list, and synteny). */
const RUN_LEVEL = new Set(['scoring', 'sqlite', 'ani', 'aai', 'closest', 'mauve', 'original_container_outputs', 'logs', 'genome_pool', 'synteny']);
/** Folders in a genome's results that are steps, not tools. */
const NOT_TOOLS = new Set(['consolidation', 'labeling', 'scoring', 'fingerprint', 'evidence', 'figures', 'diagrams', PER_TOOL]);
/** How many of the latest runs Results looks through. */
const RUNS_LOOKED_AT = 12;

/** Names of entries of one type. */
const names = (entries: Entry[], type: Entry['type']) => new Set(entries.filter((e) => e.type === type).map((e) => e.name));

/** A genome folder's results (table, Excel, viewer, diagrams, tools) from its entries, the paths inside it. */
/** A folder tree entry: type, path under the genome folder, and size in bytes (sent by newer APIs). */
type Kid = [string, string, number?];

function genomeFrom(dir: string, kids: Kid[]): OrganismResult & { jobDir: string } {
	const organism = baseName(dir);
	/** Names directly inside `under` ('' for the genome folder) of one type. */
	const inside = (under: string, type: 'd' | 'f') =>
		new Set(kids.filter(([k, r]) => k === type && r.startsWith(under) && r.length > under.length && !r.slice(under.length).includes('/')).map(([, r]) => r.slice(under.length)));
	const files = inside('', 'f');
	const dirs = inside('', 'd');
	const final: NonNullable<OrganismResult['final']> = { dir };
	if (files.has(VIEWER_NAME)) final.viewer = `${dir}/${VIEWER_NAME}`;
	if (files.has(TABLE_NAME)) {
		final.table = `${dir}/${TABLE_NAME}`;
		if (files.has(EXCEL_NAME)) final.excel = `${dir}/${EXCEL_NAME}`;
		if (dirs.has('diagrams')) final.diagrams = `${dir}/diagrams`;
	} else if (dirs.has('scoring')) {
		const scoring = inside('scoring/', 'f');
		if (scoring.has(TABLE_NAME)) final.table = `${dir}/scoring/${TABLE_NAME}`;
		if (scoring.has(EXCEL_NAME)) final.excel = `${dir}/scoring/${EXCEL_NAME}`;
		if (inside('scoring/', 'd').has('figures')) final.diagrams = `${dir}/scoring/figures`;
	}
	const toolDir = dirs.has(PER_TOOL) ? `${dir}/${PER_TOOL}` : dir;
	const toolNames = dirs.has(PER_TOOL) ? inside(`${PER_TOOL}/`, 'd') : dirs;
	const tools = [...toolNames]
		.filter((n) => !NOT_TOOLS.has(n) && !n.startsWith('.'))
		.map((tool) => ({ tool, path: `${toolDir}/${tool}`, processed: !!final.table }));
	// Each folder's files with their sizes: a step's popup names its results file and whether it is in the database.
	const byFolder: Record<string, { name: string; size: number }[]> = {};
	for (const [k, r, size] of kids) {
		const [folder, name, more] = r.split('/');
		if (k === 'f' && folder && name && more === undefined) (byFolder[folder] ??= []).push({ name, size: Number(size) || 0 });
	}
	return { organism, tools, folder: dir, final: final.table ? final : undefined, files: byFolder, jobDir: dir.slice(0, dir.lastIndexOf('/')) };
}

/** Genome result folders across the latest runs, cached for 20 s. */
const resultList = new Cache(async () => {
	const [rows, cfg] = await Promise.all([jobs.get().catch(() => [] as JobRow[]), config.get()]);
	// The run folders in the results folder (named by their start, newest first), then any other
	// run in the job history, so a cleared history leaves Results as it was.
	const output = str(dig(cfg, `${WORKFLOW}.output_path`));
	const root = output ? (await expand(output)).replace(/\/$/, '') : '';
	const listed = root ? ((await browse(root).catch(() => null))?.entries ?? []) : [];
	const fromFolder = listed
		.filter((e) => e.type === 'directory' && !e.name.startsWith('.'))
		.map((e) => e.name)
		.sort()
		.reverse()
		.map((name) => `${root}/${name}`);
	const fromJobs = rows.filter((j) => j.work_dir).map((j) => (j.work_dir as string).replace(/\/$/, ''));
	const runs = [...new Set([...fromFolder, ...fromJobs])].slice(0, RUNS_LOOKED_AT);
	if (!runs.length) return [];
	// The runs' genome folders, three levels deep, in one trip to the cluster (/v1/ssh/tree).
	const { trees } = await call<{ trees: Record<string, Kid[]> }>('POST', '/v1/ssh/tree', { paths: runs, depth: 3, prune: [...RUN_LEVEL] });
	// Newest run first: a genome annotated more than once shows its latest finished result, so a run still
	// working on it (or one that stopped before it) leaves the earlier map and figures in view.
	const picked = new Map<string, OrganismResult & { jobDir: string }>();
	for (const run of runs) {
		const entries = trees[run] ?? [];
		for (const [kind, name] of entries) {
			if (kind !== 'd' || name.includes('/') || name.startsWith('.') || RUN_LEVEL.has(name) || picked.get(name)?.final) continue;
			const kids = entries.filter(([, r]) => r.startsWith(`${name}/`)).map(([k, r, size]) => [k, r.slice(name.length + 1), size] as Kid);
			const found = genomeFrom(`${run}/${name}`, kids);
			if (!picked.has(name) || found.final) picked.set(name, found);
		}
	}
	return [...picked.values()].sort((a, b) => a.organism.localeCompare(b.organism));
}, 20_000);

/** Returns the Results page listing. */
async function results() {
	const [m, cfg] = await Promise.all([me.get(), config.get()]);
	const output = await expand(str(dig(cfg, `${WORKFLOW}.output_path`)) || m.home_dir);
	const organisms = await resultList.get().catch(() => [] as OrganismResult[]);
	return { outputRoot: output, genomesDir: '', organisms: organisms.map(({ organism, tools, folder, final, files }) => ({ organism, tools, folder, final, files })) };
}

/** Returns the API URL and token, for chat keys kept in the HPC home (lib/server/genome-chat). */
export function chatLink(): { api: string; token: string } | null {
	const token = getToken();
	return token ? { api: getApiUrl(), token } : null;
}

/**
 * Returns what genome chat needs to read a genome's results on the cluster:
 * API, token, folder, report table and owning jobs.
 */
export async function chatRemote(genome: string): Promise<ChatRemote | null> {
	const token = getToken();
	if (!token) return null;
	const organisms = await resultList.get().catch(() => [] as (OrganismResult & { jobDir: string })[]);
	const r = organisms.find((o) => o.organism === genome);
	if (!r?.folder) return null;
	const rows = await jobs.get().catch(() => [] as JobRow[]);
	const owning = rows
		.filter((j) => j.work_dir && r.folder!.startsWith((j.work_dir as string).replace(/\/$/, '') + '/'))
		.map((j) => ({ id: j.job_id, dir: (j.work_dir as string).replace(/\/$/, '') }));
	return { api: getApiUrl(), token, roots: [r.folder], table: r.final?.table ?? null, jobs: owning };
}

/**
 * Returns a FINAL table's report numbers, counted on the cluster via
 * /v1/ssh/final_summary; older APIs fall back to downloading and counting here.
 */
async function finalCounts(table: string): Promise<FinalCounts> {
	try {
		return await get<FinalCounts>(`/v1/ssh/final_summary?path=${q(table)}`);
	} catch (e) {
		if (!(e instanceof ApiError) || (e.status !== 404 && e.status !== 405)) throw e;
		// A 404 naming the table is a real miss; a bare 404 means an older API.
		if (e.status === 404 && /not found on cluster/i.test(e.message)) throw e;
	}
	const tally = new FinalTally();
	for (const line of (await fileText(table)).split(/\r?\n/)) tally.add(line);
	return tally.result();
}

/** A JSON file on the cluster, or null when it is not there or not JSON. */
async function jsonAt<T>(path: string): Promise<T | null> {
	try {
		return JSON.parse((await readText(path)).content) as T;
	} catch {
		return null;
	}
}

/**
 * What the genome was scored against: scoring/scored-against.json, where the run left it or tidied it to.
 * A run from before that file reads its reference-update token instead: the reference's size just after
 * this genome went in, less the genome itself, which scoring leaves out (estimated: true).
 */
async function scoredAgainst(folder: string): Promise<GenomeSummary['scoredAgainst']> {
	const recorded = (await jsonAt<NonNullable<GenomeSummary['scoredAgainst']>>(`${folder}/${PER_TOOL}/scoring/scored-against.json`)) ??
		(await jsonAt<NonNullable<GenomeSummary['scoredAgainst']>>(`${folder}/scoring/scored-against.json`));
	if (recorded) return recorded;
	for (const dir of [`${folder}/${PER_TOOL}/scoring`, `${folder}/scoring`]) {
		const token = await readText(`${dir}/occ_reference_updated.tkn`).then((d) => d.content).catch(() => '');
		const n = Number(/organisms_in_reference=(\d+)/.exec(token)?.[1]);
		if (!n) continue;
		const inside = /status=(added|already_present)/.test(token);
		return { genomes: inside ? n - 1 : n, reference: /(?:^|; )reference=(\S+)/.exec(token)?.[1] ?? '', left_out_self: inside, scored_at: '', estimated: true };
	}
	return null;
}

/**
 * How many genomes the operon reference holds now: the working reference's summary, else the one it was
 * scored with; a reference from before summaries is counted from its genome_stats.tsv (one row a genome).
 */
async function referenceNow(scoredWith: string | undefined): Promise<number | null> {
	const current = str(dig(await config.get(), 'margie_sb.operon_database.occ_reference_pkl'));
	for (const ref of [current, scoredWith ?? ''].filter(Boolean)) {
		const n = (await jsonAt<{ genomes?: number }>(`${ref}.summary.json`))?.genomes;
		if (typeof n === 'number') return n;
		const stats = await readText(`${ref}.genome_stats.tsv`).then((d) => d.content).catch(() => '');
		const rows = stats.split('\n').slice(1).filter((l) => l.trim()).length;
		if (rows) return rows;
	}
	return null;
}

/** The deployed map script's version, read once (the server answers for its own copy). */
let viewerVersion: Promise<string | null> | null = null;
/** Whether a map was drawn by the deployed map script: its first lines name the version that drew it. */
async function mapCurrent(viewer: string | undefined): Promise<boolean | undefined> {
	if (!viewer) return undefined;
	viewerVersion ??= get<{ version: string }>('/v1/ssh/genome-viewer/version')
		.then((d) => d.version)
		.catch(() => null);
	const [now, head] = await Promise.all([
		viewerVersion,
		get<{ content: string }>(`/v1/ssh/browse_view?path=${q(viewer)}&limit=400`).catch(() => null)
	]);
	if (!now || !head) return undefined;
	return (/<!-- margie-viewer (\w+) -->/.exec(head.content)?.[1] ?? '') === now;
}

/** Builds a genome's report summary: counts, figures and tools run. */
async function summary(genome: string): Promise<GenomeSummary> {
	const r = (await resultList.get()).find((x) => x.organism === genome);
	if (!r?.final?.table) throw new ApiError(`No finished results for ${genome} on the cluster.`, 404);
	const final = r.final;
	const scored = await scoredAgainst(r.folder as string);
	const [counts, figures, tools, refNow, current] = await Promise.all([
		finalCounts(final.table as string),
		final.diagrams
			? browse(final.diagrams)
					.then((d) => d.entries.filter((e) => e.type === 'file' && /\.png$/i.test(e.name)).map((e) => `${final.diagrams}/${e.name}`).sort())
					.catch(() => [] as string[])
			: Promise.resolve([] as string[]),
		browse(`${r.folder}/${PER_TOOL}`)
			.catch(() => browse(r.folder as string))
			.then((d) => [...names(d.entries, 'directory')].filter((n) => !NOT_TOOLS.has(n) && !n.startsWith('.')).sort())
			.catch(() => [] as string[]),
		scored ? referenceNow(scored.reference) : Promise.resolve(null),
		mapCurrent(final.viewer)
	]);
	return {
		...counts,
		genome,
		final: final as GenomeSummary['final'],
		// The cluster works these out itself (GTDB-Tk, then RASTtk); the table does not repeat them.
		domain: '',
		geneticCode: '',
		geneCaller: 'rasttk',
		tools,
		figures,
		scoredAgainst: scored,
		referenceNow: refNow,
		mapCurrent: current
	};
}

// ---- router ----

/**
 * Answers `path` (with its query) as routes/api/local would. `init` carries
 * the method and a JSON body, as lib/api sends them.
 */
export async function clusterApi<T = any>(path: string, init: RequestInit = {}): Promise<T> {
	const url = new URL(path, 'http://x');
	const route = url.pathname.replace(/\/$/, '');
	const params = url.searchParams;
	const method = (init.method ?? 'GET').toUpperCase();
	const body = typeof init.body === 'string' ? JSON.parse(init.body || '{}') : init.body ? {} : undefined;
	const form = init.body instanceof FormData ? init.body : null;
	const answer = (async (): Promise<unknown> => {
		const run = route.match(/^\/runs\/([^/]+)(?:\/(stop|resume|restart|command|sources))?$/);
		if (run) {
			const id = decodeURIComponent(run[1]);
			if (run[2] === 'stop') return stopRun(id);
			// The command it ran, as a script to run again from a shell on the cluster.
			if (run[2] === 'command') return get(`/v1/ssh/job_command/${q(id)}`);
			// Where each step's results came from: the run's cache report, or its job log for an older run.
			if (run[2] === 'sources') return get(`/v1/ssh/job_sources/${q(id)}`);
			if (run[2] === 'resume' || run[2] === 'restart') return relaunchRun(id, run[2]);
			// One finished job leaves the list, after a backup of it (job-history-backups).
			if (method === 'DELETE') {
				const cleared = await call('POST', '/v1/ssh/job_history/clear', { job_ids: [id] });
				jobs.drop();
				return cleared;
			}
			return runDetail(id, params);
		}
		// A copy or move under way (Files): its state and each item's outcome.
		const transfer = route.match(/^\/files\/transfer\/([0-9a-f]{12})$/);
		if (transfer && method === 'GET') return get(`/v1/ssh/transfer_paths/${transfer[1]}`);
		const report = route.match(/^\/results\/([^/]+)$/);
		if (report && method === 'GET') return summary(decodeURIComponent(report[1]));
		switch (`${method} ${route}`) {
			// The Code page: the scripts behind MARGIE's own steps, as the server has them (routers/code.py).
			case 'GET /code':
				return get('/v1/code');
			case 'GET /code/file':
				return get(`/v1/code/file?path=${q(params.get('path') ?? '')}`);
			case 'GET /code/snippet':
				return get(`/v1/code/snippet?path=${q(params.get('path') ?? '')}&symbol=${q(params.get('symbol') ?? '')}`);
			case 'GET /runs':
				return listRuns();
			case 'POST /runs':
				return startRun(body ?? {});
			// Backs up the finished jobs to the working folder, then clears them from the list.
			case 'DELETE /runs': {
				const cleared = await call('POST', '/v1/ssh/job_history/clear');
				// The list is read again at once, not from the copy kept for a few seconds.
				jobs.drop();
				return cleared;
			}
			case 'GET /genomes':
				return listGenomes();
			// Your databases on scratch, their backups on depot, and the copy under way.
			case 'GET /stores':
				return storesAnswer(get('/v1/ssh/stores'));
			case 'GET /stores/progress':
				return get('/v1/ssh/stores/progress');
			case 'POST /results/refresh-map':
				// Regenerates the genome map with the backend's current viewer.
				return call('POST', '/v1/ssh/genome-viewer/refresh', { folder: String((body as { folder?: string })?.folder ?? '') });
			case 'POST /stores/run-here':
				return call('POST', '/v1/ssh/stores/run-here');
			case 'POST /stores/stop':
				return storesAnswer(call('POST', '/v1/ssh/stores/stop'));
			case 'POST /stores/setup':
				// {fresh, build_password}: every database starts empty (a new lab's own).
				return storesAnswer(call('POST', '/v1/ssh/stores/setup', body ?? {}));
			case 'GET /stores/check':
				return get(`/v1/ssh/stores/${q(params.get('id') ?? '')}/backup-check`);
			case 'POST /stores/backup':
				return storesAnswer(call('POST', `/v1/ssh/stores/${q(String((body as { id?: string })?.id ?? ''))}/backup`));
			case 'PUT /genomes':
				return saveGenomeInfo(body ?? {});
			case 'POST /genomes':
				if (form) return addGenomes(form);
				return notHere('Genomes in folders inside the input folder are gathered on the cluster itself, not from here.');
			case 'DELETE /genomes':
				return notHere('Genomes on the cluster are removed in their folder there, not from here.');
			case 'GET /tools':
				return listTools();
			case 'GET /overview':
				return overview();
			// SLURM as the user sees it: accounts and limits, jobs, partitions (Cluster: Resources).
			case 'GET /cluster/resources':
				return get('/v1/ssh/cluster_resources');
			// One of the user's SLURM jobs, cancelled (a MARGIE run's driver as its run).
			case 'POST /cluster/cancel':
				return call('POST', `/v1/ssh/cancel_slurm_job/${encodeURIComponent(String(body?.id ?? ''))}`);
			case 'GET /check':
				return { rows: await installed.get() };
			case 'GET /settings':
				return settingsList();
			case 'PUT /settings':
				return saveSettings(body ?? {});
			case 'POST /settings/create-default':
				return createDefaultConfig();
			// Settings → Advanced: whether the workflow has edits by hand, and putting a default back.
			case 'GET /settings/advanced':
				return get('/v1/ssh/advanced_files');
			case 'POST /settings/restore-default':
				return restoreDefault(body ?? {});
			// A new folder (and any above it) or an empty text file; refused where the account may not write.
			case 'POST /files/make':
				return call('POST', '/v1/ssh/make_path', body ?? {});
			// A text file edited by hand (config.yaml, the workflow): checked, the old version kept.
			case 'POST /files/edit':
				return call('POST', '/v1/ssh/edit_file', body ?? {});
			// Copy or move on the cluster, into a folder; nothing is overwritten.
			case 'POST /files/transfer':
				return call('POST', '/v1/ssh/transfer_paths', body ?? {});
			// Deletes files and folders as a job on the login node, followed like a transfer; some paths are refused.
			case 'POST /files/delete':
				return call('POST', '/v1/ssh/delete_paths', body ?? {});
			case 'GET /results':
				return results();
			case 'GET /files':
				return params.get('places') ? places() : listFolder(params.get('path') ?? '~');
			case 'GET /files/text':
				return readText(params.get('path') ?? '');
			case 'GET /files/table':
				return tablePage(params);
			case 'GET /preview':
				return { output: 'The cluster runs MARGIE (SB) through SLURM; the job page shows each step as it is submitted.' };
			case 'POST /licences':
				return notHere('On the cluster the licence terms are accepted on the Install page.');
			case 'POST /runtime/start':
				return notHere('The cluster’s container runtime is not started from here.');
		}
		throw new ApiError(`Not available on the cluster: ${route}`, 404);
	})();
	return answer as Promise<T>;
}
