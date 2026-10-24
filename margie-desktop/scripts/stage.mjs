/**
 * Builds fe-margie/margie-fe for the desktop (VITE_HOSTED=0: the node server with both modes) and
 * stages what the app ships: .stage/gui (adapter-node build, scripts, runtime-only node_modules) and
 * .stage/pipeline (margie-pipeline at a commit, via git archive, without its own GUI). electron-builder
 * copies both into the app's resources; `npm start` uses them directly.
 *
 * margie-pipeline comes from MARGIE_PIPELINE_REPO (a git checkout holding a margie-pipeline folder) at
 * MARGIE_PIPELINE_REF (default HEAD): by default this repository if it holds one, else the biolab-fe
 * checkout beside it.
 *
 * .stage/build.margie is margie-build (MARGIE_BUILD_REPO, default the checkout beside this repository)
 * as it is on disk, its git-ignored files left out, locked with MARGIE_BUILD_PASSWORD; when
 * MARGIE_BUILD_PASSWORD_SHA256 is set, the password must match it. Without a password the app
 * carries no build files.
 */

import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DESKTOP = path.resolve(HERE, '..');
const FE = path.resolve(DESKTOP, '..', 'fe-margie', 'margie-fe');
const STAGE = path.join(DESKTOP, '.stage');
const GUI = path.join(STAGE, 'gui');
const PIPELINE = path.join(STAGE, 'pipeline');
// The pipeline local mode runs: margie-pipeline in MARGIE_PIPELINE_REPO at MARGIE_PIPELINE_REF.
const PIPELINE_DIR = 'margie-pipeline';
const HERE_REPO = path.resolve(DESKTOP, '..');
const REPO = path.resolve(
	process.env.MARGIE_PIPELINE_REPO ||
		(fs.existsSync(path.join(HERE_REPO, PIPELINE_DIR)) ? HERE_REPO : path.join(HERE_REPO, '..', 'biolab-fe'))
);
const REF = process.env.MARGIE_PIPELINE_REF || 'HEAD';

const step = (s) => console.log(`\n\u001b[1m==> ${s}\u001b[0m`);
const run = (cmd, args, cwd, extraEnv = {}) =>
	execFileSync(cmd, args, {
		cwd,
		stdio: 'inherit',
		// On Windows npm is npm.cmd, which Node starts only through a shell.
		shell: process.platform === 'win32',
		env: { ...process.env, npm_config_update_notifier: 'false', ...extraEnv }
	});

if (!fs.existsSync(path.join(FE, 'package.json'))) {
	console.error(`margie-fe is not where it should be: ${FE}`);
	process.exit(1);
}

// ---------------------------------------------------------------------------
// 1. The pipeline (first: the front-end's build reads it)
// ---------------------------------------------------------------------------
step(`Staging ${PIPELINE_DIR} from ${REPO} (${REF})`);
fs.rmSync(STAGE, { recursive: true, force: true });
const git = (...args) => execFileSync('git', ['-C', REPO, ...args], { encoding: 'utf8' }).trim();
let commit;
try {
	commit = git('log', '-1', '--format=%H', REF, '--', PIPELINE_DIR);
} catch {
	console.error(`${REPO} is not a git checkout`);
	process.exit(1);
}
if (!commit) {
	console.error(`${PIPELINE_DIR} is not committed in ${REPO}`);
	process.exit(1);
}
fs.mkdirSync(PIPELINE, { recursive: true });
const tarball = path.join(STAGE, 'pipeline.tar');
// Only the pipeline folder, as committed, with its paths relative to it.
execFileSync('git', ['-C', REPO, 'archive', '--format=tar', '-o', tarball, `${REF}:${PIPELINE_DIR}`]);
// bsdtar (macOS, Windows 10+) keeps the scripts' exec bits.
execFileSync('tar', ['-xf', tarball, '-C', PIPELINE]);
fs.rmSync(tarball);
const describe = git('log', '-1', '--format=%h %cs %s', REF, '--', PIPELINE_DIR);
// The app's licence gate (lib/server/pipeline.ts LICENCE_TOOLS) in the pipeline it ships: annotate.sh
// skips a gated tool until its licence is accepted, and each gets its LICENCE_AGREED_<TOOL> default.
const gated = fs
	.readFileSync(path.join(FE, 'src', 'lib', 'server', 'pipeline.ts'), 'utf8')
	.match(/export const LICENCE_TOOLS = \[([^\]]*)\]/)?.[1]
	.match(/'([a-z0-9_-]+)'/g)
	?.map((t) => t.slice(1, -1));
if (!gated?.length) {
	console.error('Could not read LICENCE_TOOLS from the front-end');
	process.exit(1);
}
const confPath = path.join(PIPELINE, 'pipeline.conf.sh');
let conf = fs.readFileSync(confPath, 'utf8');
const listLine = /^LICENCE_GATED_TOOLS=\(.*\)$/m;
if (!listLine.test(conf)) {
	console.error('pipeline.conf.sh has no LICENCE_GATED_TOOLS line to set');
	process.exit(1);
}
conf = conf.replace(listLine, `LICENCE_GATED_TOOLS=(${gated.join(' ')})`);
const defaults = gated
	.filter((t) => !conf.includes(`LICENCE_AGREED_${t.toUpperCase()}:=`))
	.map((t) => `: "\${LICENCE_AGREED_${t.toUpperCase()}:=0}"`);
if (defaults.length) conf = conf.replace(listLine, (m) => `${defaults.join('\n')}\n\n${m}`);
fs.writeFileSync(confPath, conf);
console.log(`  licence-gated: ${gated.join(' ')}`);
fs.writeFileSync(
	path.join(PIPELINE, 'margie-bundle.json'),
	JSON.stringify({ commit, describe, staged: new Date().toISOString() }, null, 2) + '\n'
);
console.log(`  ${describe}`);

// ---------------------------------------------------------------------------
// 1b. The build files, locked (the format: fe-margie/margie-fe/src/lib/server/build-vault.ts)
// ---------------------------------------------------------------------------
const BUILD_REPO = path.resolve(process.env.MARGIE_BUILD_REPO || path.join(HERE_REPO, '..', 'margie-build'));
const password = process.env.MARGIE_BUILD_PASSWORD || '';
const VAULT = path.join(STAGE, 'build.margie');
if (!password) {
	step('No MARGIE_BUILD_PASSWORD: this build carries no build files');
} else {
	step(`Locking the build files from ${BUILD_REPO}`);
	const want = (process.env.MARGIE_BUILD_PASSWORD_SHA256 || '').trim().toLowerCase();
	if (want && crypto.createHash('sha256').update(password).digest('hex') !== want) {
		console.error('MARGIE_BUILD_PASSWORD does not match MARGIE_BUILD_PASSWORD_SHA256');
		process.exit(1);
	}
	if (!fs.existsSync(path.join(BUILD_REPO, 'build.sh'))) {
		console.error(`${BUILD_REPO} is not margie-build (no build.sh)`);
		process.exit(1);
	}
	// Tracked files as they are now and untracked ones, without what .gitignore keeps out
	// (images, site configs, licence logs, Phobius's vendor files, databases).
	const listed = execFileSync('git', ['-C', BUILD_REPO, 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], { encoding: 'utf8' })
		.split('\0')
		.filter((f) => f && !f.endsWith('.DS_Store') && fs.existsSync(path.join(BUILD_REPO, f)))
		.sort();
	const files = listed.map((f) => {
		const at = path.join(BUILD_REPO, f);
		return [f, fs.statSync(at).mode & 0o777, fs.readFileSync(at).toString('base64')];
	});
	const archive = zlib.gzipSync(JSON.stringify({ files }), { level: 9 });
	const salt = crypto.randomBytes(16);
	const iv = crypto.randomBytes(12);
	const key = crypto.scryptSync(password, salt, 32, { N: 1 << 15, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
	const c = crypto.createCipheriv('aes-256-gcm', key, iv);
	const body = Buffer.concat([c.update(archive), c.final()]);
	fs.writeFileSync(VAULT, Buffer.concat([Buffer.from('MARGIEB1'), salt, iv, c.getAuthTag(), body]));
	const head = execFileSync('git', ['-C', BUILD_REPO, 'log', '-1', '--format=%h %cs'], { encoding: 'utf8' }).trim();
	console.log(`  ${files.length} files from ${head} and the changes on disk, ${(fs.statSync(VAULT).size / 1024 / 1024).toFixed(1)} MB locked`);
}

// ---------------------------------------------------------------------------
// 2. Build the front-end
// ---------------------------------------------------------------------------
step('Installing the front-end’s build dependencies');
run('npm', ['install', '--no-audit', '--no-fund'], FE);

step('Building the front-end (vite build → build/)');
// The desktop build (VITE_HOSTED=0), its cluster API pinned to the local end of hpc-connect.sh's SSH
// tunnel; the build reads the staged pipeline (lib/server/pipeline finds it through MARGIE_PIPELINE_ROOT).
run('npm', ['run', 'build'], FE, { VITE_HOSTED: '0', VITE_PUBLIC_API_URL: 'http://localhost:8000', MARGIE_PIPELINE_ROOT: PIPELINE });

const built = path.join(FE, 'build', 'handler.js');
if (!fs.existsSync(built)) {
	console.error(`the build did not produce ${built}`);
	process.exit(1);
}

// ---------------------------------------------------------------------------
// 3. Lay out .stage/gui
// ---------------------------------------------------------------------------
step('Staging the front-end');
fs.rmSync(GUI, { recursive: true, force: true });
fs.mkdirSync(GUI, { recursive: true });

fs.cpSync(path.join(FE, 'build'), path.join(GUI, 'build'), { recursive: true });
fs.cpSync(path.join(FE, 'scripts'), path.join(GUI, 'scripts'), { recursive: true });
for (const f of ['package.json', 'package-lock.json']) {
	fs.copyFileSync(path.join(FE, f), path.join(GUI, f));
}

// The scripts are spawned by path and Resources is read-only, so they need their exec bit here.
step('Making the scripts executable');
for (const f of fs.readdirSync(path.join(GUI, 'scripts'))) {
	if (f.endsWith('.sh')) {
		fs.chmodSync(path.join(GUI, 'scripts', f), 0o755);
		console.log(`  chmod +x scripts/${f}`);
	}
}

// ---------------------------------------------------------------------------
// 4. Runtime dependencies only
// ---------------------------------------------------------------------------
step('Installing runtime dependencies (omit=dev)');
// --ignore-scripts: no runtime dependency needs an install hook.
run('npm', ['ci', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund'], GUI);

// The lockfile is only needed for the install.
fs.rmSync(path.join(GUI, 'package-lock.json'), { force: true });

// ---------------------------------------------------------------------------
// 5. Report
// ---------------------------------------------------------------------------
const bytes = (dir) => {
	let total = 0;
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		const p = path.join(dir, e.name);
		if (e.isDirectory()) total += bytes(p);
		else if (e.isFile()) total += fs.statSync(p).size;
	}
	return total;
};
const mb = (n) => `${(n / 1024 / 1024).toFixed(1)} MB`;

step('Staged');
console.log(`  build/        ${mb(bytes(path.join(GUI, 'build')))}`);
console.log(`  node_modules/ ${mb(bytes(path.join(GUI, 'node_modules')))}`);
console.log(`  scripts/      ${mb(bytes(path.join(GUI, 'scripts')))}`);
console.log(`  total         ${mb(bytes(GUI))}   →  ${GUI}`);
console.log(`  pipeline      ${mb(bytes(PIPELINE))}   →  ${PIPELINE}`);
console.log(`  build files   ${fs.existsSync(VAULT) ? `${mb(fs.statSync(VAULT).size)}, locked   →  ${VAULT}` : 'none'}`);
