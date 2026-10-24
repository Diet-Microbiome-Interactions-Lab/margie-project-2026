/**
 * Copy, move, delete and make on this computer, for the Files views (FolderView), in the shape the
 * cluster's /v1/ssh/transfer_paths and delete_paths answer: { id, op, into, state, where, job, results }.
 * A copy, move or delete runs in the background and is followed by its id; nothing is overwritten.
 *
 * Changes stay inside the home folder and the folders MARGIE's settings point at. Refused: the home
 * folder or anything above it, the settings' folders themselves (databases, containers, results...),
 * MARGIE's pipeline code and its build files, and the SSH and MARGIE settings folders.
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { allowedRoots } from './files';
import { PIPELINE_ROOT } from './pipeline';

export interface Result {
	source: string;
	target: string;
	ok: boolean | null;
	message: string;
}

export interface Task {
	id: string | null;
	op: 'copy' | 'move' | 'delete';
	into: string;
	state: 'running' | 'done' | 'failed';
	where: 'local' | null;
	job: null;
	results: Result[];
}

const tasks = new Map<string, Task>();
/** Finished tasks kept for their last look. */
const KEPT = 50;

const above = (p: string, q: string) => q === p || q.startsWith(p.replace(/\/$/, '') + path.sep);

function resolve(p: string): string {
	let raw = String(p ?? '').trim();
	if (raw === '~' || raw.startsWith('~/')) raw = path.join(os.homedir(), raw.slice(1));
	return path.resolve(raw);
}

/** Where a path really is, its folder's links followed (the path itself may not exist yet). */
function real(p: string): string {
	try {
		return path.join(fs.realpathSync(path.dirname(p)), path.basename(p));
	} catch {
		return p;
	}
}

/** The folders MARGIE keeps for itself: its pipeline code (not its data folders), its build files, keys and settings. */
function kept(): string[] {
	const home = os.homedir();
	const data = new Set(['db', 'input', 'output', 'logs', 'user-input']);
	let code: string[] = [];
	try {
		code = fs.readdirSync(PIPELINE_ROOT).filter((n) => !data.has(n)).map((n) => path.join(PIPELINE_ROOT, n));
	} catch {
		code = [];
	}
	return [
		...code,
		...[process.env.MARGIE_BUILD_OPEN, process.env.MARGIE_STATE_DIR].filter((x): x is string => !!x),
		path.join(home, '.ssh'),
		path.join(home, '.config', 'margie')
	];
}

/** Why a path may not be changed from here, or '' when it may. */
export function refusal(p: string, removing: boolean): string {
	const home = os.homedir();
	const roots = allowedRoots().map((r) => path.resolve(r));
	for (const x of new Set([p, real(p)])) {
		if (x.split(path.sep).filter(Boolean).length < 2) return 'Too high up in the file system to change from here.';
		if (above(x, home)) return 'Your home folder, or a folder above it, is not changed from here.';
		if (!above(home, x) && !roots.some((r) => above(r, x))) return 'Outside your home folder and the folders MARGIE uses.';
		if (removing && roots.some((r) => above(x, r))) return "A folder MARGIE's settings point at (or one above it) is not removed from here.";
		if (kept().some((k) => above(k, x) || above(x, k))) return "MARGIE's own code, build files, keys or settings: they are not changed from here.";
	}
	return '';
}

function keep(task: Task) {
	tasks.set(task.id as string, task);
	while (tasks.size > KEPT) tasks.delete(tasks.keys().next().value as string);
}

/** Runs each item in turn, recording its result; the task ends failed when any item failed. */
function run(task: Task, items: Result[], step: (r: Result) => Promise<void>) {
	void (async () => {
		for (const r of items) {
			try {
				await step(r);
				Object.assign(r, { ok: true, message: '' });
			} catch (e) {
				Object.assign(r, { ok: false, message: e instanceof Error ? e.message : String(e) });
			}
		}
		task.state = task.results.some((r) => r.ok === false) ? 'failed' : 'done';
	})();
}

/** Copies or moves the sources into a folder, each under its own name; a name already there is left as it is. */
export function transfer(op: 'copy' | 'move', sources: string[], intoRaw: string): Task {
	const into = resolve(intoRaw);
	const why = refusal(into, false);
	if (why) throw new Error(why);
	if (!fs.existsSync(into) || !fs.statSync(into).isDirectory()) throw new Error(`No folder ${into} to paste into.`);
	const task: Task = { id: randomUUID().slice(0, 12), op, into, state: 'running', where: 'local', job: null, results: [] };
	const items: Result[] = [];
	for (const raw of sources) {
		const source = resolve(raw);
		const target = path.join(into, path.basename(source));
		let message = '';
		if (!fs.existsSync(source)) message = 'Not there any more.';
		else if (op === 'move') message = refusal(source, true);
		if (!message && above(source, into)) message = 'A folder cannot go inside itself.';
		if (!message && fs.existsSync(target)) message = `${path.basename(target)} is already in ${into}; it is left as it is.`;
		const r: Result = { source, target, ok: message ? false : null, message };
		task.results.push(r);
		if (!message) items.push(r);
	}
	keep(task);
	run(task, items, async (r) => {
		if (op === 'copy') {
			await fs.promises.cp(r.source, r.target, { recursive: true, errorOnExist: true, force: false, preserveTimestamps: true });
			return;
		}
		try {
			await fs.promises.rename(r.source, r.target);
		} catch (e) {
			// Another disk: copied over, then removed here.
			if ((e as NodeJS.ErrnoException).code !== 'EXDEV') throw e;
			await fs.promises.cp(r.source, r.target, { recursive: true, errorOnExist: true, force: false, preserveTimestamps: true });
			await fs.promises.rm(r.source, { recursive: true, force: true });
		}
	});
	return task;
}

/** Deletes files and folders (with everything in them). */
export function remove(paths: string[]): Task {
	const task: Task = { id: randomUUID().slice(0, 12), op: 'delete', into: '', state: 'running', where: 'local', job: null, results: [] };
	const items: Result[] = [];
	for (const raw of paths) {
		const source = resolve(raw);
		const message = !fs.existsSync(source) ? 'Not there any more.' : refusal(source, true);
		const r: Result = { source, target: '', ok: message ? false : null, message };
		task.results.push(r);
		if (!message) items.push(r);
	}
	keep(task);
	run(task, items, (r) => fs.promises.rm(r.source, { recursive: true, force: false }));
	return task;
}

export const taskOf = (id: string) => tasks.get(id) ?? null;

/** Makes a folder (and any above it) or an empty text file; `made` is false when it was there already. */
export function make(raw: string, kind: 'folder' | 'file'): { path: string; made: boolean } {
	const p = resolve(raw);
	const why = refusal(p, false);
	if (why) throw new Error(why);
	if (fs.existsSync(p)) return { path: p, made: false };
	if (kind === 'folder') fs.mkdirSync(p, { recursive: true });
	else {
		fs.mkdirSync(path.dirname(p), { recursive: true });
		fs.writeFileSync(p, '', { flag: 'wx' });
	}
	return { path: p, made: true };
}
