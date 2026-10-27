/**
 * Copies the bundled margie-pipeline to PIPELINE_HOME (it writes inside its own folder,
 * so it cannot run from the read-only bundle) on first start and whenever the bundle's
 * commit differs. Files are overwritten; the folders a former build left for a hidden tool
 * (pipeline.conf.sh HIDDEN_TOOLS) are removed from the code, and data and results stay.
 * A git clone or non-pipeline folder is left alone.
 */

import fs from 'node:fs';
import path from 'node:path';
import { PIPELINE_BUNDLE, PIPELINE_HOME } from './paths.js';
import { isPipeline } from './settings.js';

const STAMP = 'margie-bundle.json';
/** Data and results, which a refresh leaves as they are. */
const DATA = new Set(['db', 'input', 'logs', 'output', 'user-input', 'run-history']);

/** pipeline.conf.sh HIDDEN_TOOLS, lower-cased. */
const hiddenTools = (dir) => {
	try {
		const m = fs.readFileSync(path.join(dir, 'pipeline.conf.sh'), 'utf8').match(/^HIDDEN_TOOLS=\(([^)]*)\)$/m);
		return new Set((m?.[1] ?? '').split(/\s+/).filter(Boolean).map((t) => t.toLowerCase()));
	} catch {
		return new Set();
	}
};

/** Removes the folders under dir named after a hidden tool; returns how many. */
function dropHidden(dir, hidden) {
	let n = 0;
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		if (!e.isDirectory()) continue;
		const at = path.join(dir, e.name);
		if (hidden.has(e.name.toLowerCase())) {
			fs.rmSync(at, { recursive: true, force: true });
			n++;
		} else n += dropHidden(at, hidden);
	}
	return n;
}

const readStamp = (dir) => {
	try {
		return JSON.parse(fs.readFileSync(path.join(dir, STAMP), 'utf8'));
	} catch {
		return null;
	}
};

/** Installs or refreshes the bundled pipeline. Returns what happened, for the log. */
export function installBundledPipeline() {
	const bundled = readStamp(PIPELINE_BUNDLE);
	if (!bundled || !isPipeline(PIPELINE_BUNDLE)) return 'this build carries no pipeline';
	const exists = fs.existsSync(PIPELINE_HOME) && fs.readdirSync(PIPELINE_HOME).length > 0;
	if (exists && fs.existsSync(path.join(PIPELINE_HOME, '.git'))) return `a git clone is there; left as it is (${PIPELINE_HOME})`;
	if (exists && !isPipeline(PIPELINE_HOME)) return `${PIPELINE_HOME} is not a pipeline; left as it is`;
	const installed = readStamp(PIPELINE_HOME);
	if (installed?.commit === bundled.commit) return `up to date (${bundled.describe})`;
	fs.cpSync(PIPELINE_BUNDLE, PIPELINE_HOME, { recursive: true, force: true });
	// Its data folders are empty in git (placeholders only), so the bundle has none.
	for (const d of ['db', 'input', 'logs', 'output', 'user-input']) {
		fs.mkdirSync(path.join(PIPELINE_HOME, d), { recursive: true });
	}
	// A former build's folders for the hidden tools go; the code folders only.
	const hidden = hiddenTools(PIPELINE_BUNDLE);
	let dropped = 0;
	for (const e of hidden.size ? fs.readdirSync(PIPELINE_HOME, { withFileTypes: true }) : []) {
		if (e.isDirectory() && !DATA.has(e.name)) dropped += dropHidden(path.join(PIPELINE_HOME, e.name), hidden);
	}
	return `${installed ? 'updated' : 'installed'}: ${bundled.describe}${dropped ? ` (${dropped} hidden-tool folders removed)` : ''}`;
}
