/**
 * The `margie` and `margie-cli` terminal commands. At each start the app writes them to the user's
 * command folder (~/.local/bin; %LOCALAPPDATA%\MARGIE\bin on Windows, run by Git for Windows' bash)
 * and puts that folder on the user's PATH:
 *
 *   margie            the MARGIE command line on the HPC chosen in the app (dane_wf, dane and misc run there)
 *   margie <command>  one command there, for example: margie dane_wf margie sb -i genomes/ -o results/
 *   margie-cli        the MARGIE command line on this computer: dane_wf margie sb runs the app's local
 *                     pipeline (src/cli/margie-cli.sh), with setup and check
 *   margie app        opens this app (margie-cli app too)
 *   margie --help     says how to run MARGIE (margie-cli --help for this computer)
 *
 * The HPC, the MARGIE folder on it and the key come from ~/.config/margie/margie.env, as for the
 * app's own connection, whose open connection (hpc-connect.sh's socket) it signs in through.
 */

import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/** The line that marks a file as the app's, so a `margie` of the user's own stays as it is. */
export const MARK = 'Written by the MARGIE app';
const PATH_MARK = '# The margie command (added by the MARGIE app)';
const CLI_SOURCE = path.join(path.dirname(fileURLToPath(import.meta.url)), 'cli');

/**
 * margie-cli's defaults for a local run, as margie-fe's lib/server/pipeline.ts (LOCAL_DEFAULTS) gives
 * them to the pipeline: GTDB-Tk off, and each licence-gated tool not agreed until Settings says so.
 */
const LICENCE_TOOLS = ['kegg', 'tigrfam', 'dbcan', 'eggnog', 'merops', 'tcdb', 'uniprot', 'interpro', 'geneprop', 'psortb', 'deepsig'];
const LOCAL_DEFAULTS = ['export RUN_GTDBTK=0', "export LICENCE_INTENDED_USE=''", "export LICENCE_STATEMENT=''",
	...LICENCE_TOOLS.map((t) => `export LICENCE_AGREED_${t.toUpperCase()}=0`)].join('\n    ');

const sq = (s) => `'${String(s).replaceAll("'", `'\\''`)}'`;

/** C:\a\b -> /c/a/b, as Git Bash names Windows paths. */
const gitBashPath = (p) => p.replace(/^([A-Za-z]):[\\/]/, (_, d) => `/${d.toLowerCase()}/`).replaceAll('\\', '/');

const HELP = `MARGIE command line

  margie               opens the MARGIE command line on your HPC, where the commands below run
  margie <command>     runs one command there and returns, for example
                         margie dane_wf margie sb -i genomes/ -o results/
  margie app           opens the MARGIE app
  margie --help        shows this
  margie-cli           the same command line on this computer, running the app's local pipeline

Running MARGIE on a genome file or a folder of genomes (paths on the HPC):
  dane_wf margie sb --input <genome file or folder> --output <folder> [--working-directory <folder>] [--config <config file>]

  -i, --input              a genome file, or a folder of genome files
  -o, --output             the folder the results go in
  -w, --working-directory  the folder relative paths are read from; without --output,
                           the results go in its margie-output folder
  -c, --config             a config file, read over ~/.config/bioinformatics-tools/config.yaml on the HPC

  Other settings go after them as key: value, for example margie_sb.resume: true

At the prompt: dane, misc, cd <folder>, help, exit (or Ctrl-D); any other line runs in the HPC's shell.
The HPC is the one chosen on the app's start page.`;

/** The shell lines that open the app, for this platform and install. */
export function openAppLines({ platform, exe, packaged, appImage }) {
	if (platform === 'darwin') {
		// <MARGIE.app>/Contents/MacOS/MARGIE
		return packaged ? `open ${sq(path.resolve(exe, '..', '..', '..'))}` : 'open -a MARGIE';
	}
	const target = platform === 'win32' ? gitBashPath(exe) : appImage || exe;
	return `nohup ${sq(target)} >/dev/null 2>&1 &`;
}

/** The `margie` script (bash), opening the app with *openApp*. */
export function launcherScript(openApp) {
	return `#!/usr/bin/env bash
# margie -- the MARGIE command line. ${MARK}; the app writes it again at each start.
# margie opens it on the HPC chosen in the app; margie app opens the app; margie --help says how to run MARGIE.
set -u
CONFIG="\${XDG_CONFIG_HOME:-$HOME/.config}/margie/margie.env"
# shellcheck disable=SC1090
[ -f "$CONFIG" ] && . "$CONFIG"

open_app() {
    ${openApp}
}

case "\${1:-}" in
    app) open_app; exit $? ;;
    help|--help|-h) cat <<'MARGIE_HELP'
${HELP}
MARGIE_HELP
        exit 0 ;;
esac

if [ -z "\${HPC_HOST:-}" ] || [ -z "\${BACKEND_DIR:-}" ]; then
    echo "margie: no HPC chosen yet. Open the app (margie app), choose your HPC on its start page, then run margie again." >&2
    exit 1
fi

# The app's key and ssh options, and its open connection when there is one (no second sign-in).
read -r -a SSH_X <<< "\${MARGIE_SSH_OPTS:-}"
key="\${MARGIE_SSH_KEY:-}"
key="\${key/#\\~/$HOME}"
[ -n "$key" ] && [ -f "$key" ] && SSH_X+=(-i "$key")
socket="/tmp/margie-$HPC_HOST-\${USER:-$(id -un)}.sock"
[ -S "$socket" ] && SSH_X+=(-o "ControlPath=$socket")
[ -t 0 ] && SSH_X+=(-t)

# The MARGIE command line in the HPC's copy of MARGIE (~ there is the HPC home).
dir="\${BACKEND_DIR%/}"
case "$dir" in
    "~"|"~/"*) remote="\\$HOME$(printf '%q' "\${dir#\\~}")/.venv/bin/margie" ;;
    *) remote="$(printf '%q' "$dir")/.venv/bin/margie" ;;
esac
run="$remote"
for a in "$@"; do run+=" $(printf '%q' "$a")"; done
exec ssh \${SSH_X[@]+"\${SSH_X[@]}"} "$HPC_HOST" \\
    "if [ -x $remote ]; then exec $run; else echo 'margie: the MARGIE command line is not on the HPC yet. Start a run from the app once: it brings the HPC copy of MARGIE up to date.' >&2; exit 127; fi"
`;
}

/**
 * The `margie-cli` script (bash): the MARGIE command line on this computer, running the app's local
 * pipeline (*pipelineHome*, unless margie.env names another) with the app's settings, read by
 * *settingsEnv* run as Node with the app's binary *exe*.
 */
export function localScript({ openApp, exe, pipelineHome, settingsEnv, platform = process.platform }) {
	const shellPath = (p) => sq(platform === 'win32' ? gitBashPath(p) : p);
	return fs.readFileSync(path.join(CLI_SOURCE, 'margie-cli.sh'), 'utf8')
		.replace('__MARK__', () => MARK)
		.replace('__APP_EXE__', () => shellPath(exe))
		.replace('__APP_PIPELINE__', () => shellPath(pipelineHome))
		.replace('__SETTINGS_ENV__', () => shellPath(settingsEnv))
		.replace('__APP_DEFAULTS__', () => LOCAL_DEFAULTS)
		.replace('__OPEN_APP__', () => openApp);
}

/** Git for Windows' bash.exe, where the app looks for it to reach the HPC; '' when it is not there. */
function windowsBash(env) {
	const candidates = [
		path.join(env.ProgramFiles || 'C:\\Program Files', 'Git', 'bin', 'bash.exe'),
		path.join(env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'Git', 'bin', 'bash.exe'),
		env.LOCALAPPDATA && path.join(env.LOCALAPPDATA, 'Programs', 'Git', 'bin', 'bash.exe')
	];
	return candidates.find((p) => p && fs.existsSync(p)) || '';
}

/** Writes *file* with *text* unless a file there is not the app's; true when written or the same. */
function writeOurs(file, text, mode) {
	if (fs.existsSync(file)) {
		const now = fs.readFileSync(file, 'utf8');
		if (!now.includes(MARK)) return false;
		if (now === text) return true;
	}
	fs.mkdirSync(path.dirname(file), { recursive: true });
	fs.writeFileSync(file, text, { mode });
	fs.chmodSync(file, mode);
	return true;
}

/** The startup file of the user's shell that interactive terminals read, for the PATH line. */
export function shellProfile({ home, shell, platform }) {
	const name = path.basename(shell || '');
	if (name === 'zsh') return path.join(home, '.zshrc');
	if (name === 'bash') return path.join(home, platform === 'darwin' ? '.bash_profile' : '.bashrc');
	if (name === 'fish') return '';
	return path.join(home, '.profile');
}

/** Adds the command folder to PATH in *profile*, once. */
function addToProfile(profile, dir, home) {
	const text = fs.existsSync(profile) ? fs.readFileSync(profile, 'utf8') : '';
	if (text.includes(PATH_MARK)) return false;
	const shown = dir.startsWith(home + path.sep) ? `$HOME/${path.relative(home, dir)}` : dir;
	fs.appendFileSync(profile, `${text && !text.endsWith('\n') ? '\n' : ''}\n${PATH_MARK}\nexport PATH="${shown}:$PATH"\n`);
	return true;
}

/** Puts *dir* on the Windows user's PATH (the registry's user Path), once. */
function addToWindowsPath(dir) {
	const ps = `$d=${sq(dir)}; $p=[Environment]::GetEnvironmentVariable('Path','User'); ` +
		`if (-not (($p -split ';') -contains $d)) { [Environment]::SetEnvironmentVariable('Path', $(if ($p) { "$p;$d" } else { $d }), 'User'); 'added' }`;
	return new Promise((resolve) =>
		execFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', ps], { windowsHide: true, timeout: 15000 },
			(err, stdout) => resolve(!err && String(stdout).includes('added')))
	);
}

/**
 * Writes the margie command and puts its folder on PATH. Returns what it did, for the log:
 * { file, written, onPath, profile, before } (before: another margie found first on PATH).
 */
export async function installCli({ platform = process.platform, home = os.homedir(), env = process.env,
	exe, packaged, loginPath = '', dataDir, pipelineHome }) {
	const openApp = openAppLines({ platform, exe, packaged, appImage: env.APPIMAGE });
	// margie-cli reads the app's saved settings with this helper, run as Node by the app's binary.
	const settingsEnv = path.join(dataDir, 'cli', 'settings-env.cjs');
	fs.mkdirSync(path.dirname(settingsEnv), { recursive: true });
	fs.writeFileSync(settingsEnv, fs.readFileSync(path.join(CLI_SOURCE, 'settings-env.cjs')));
	const scripts = {
		margie: launcherScript(openApp),
		'margie-cli': localScript({ openApp, exe, pipelineHome, settingsEnv, platform })
	};
	if (platform === 'win32') {
		const dir = path.join(env.LOCALAPPDATA || path.join(home, 'AppData', 'Local'), 'MARGIE', 'bin');
		const bash = windowsBash(env);
		if (!bash) return { file: '', written: false, why: 'Git for Windows (its bash) is not installed' };
		let written = true;
		for (const [name, text] of Object.entries(scripts)) {
			written = writeOurs(path.join(dir, name), text, 0o755) &&
				writeOurs(path.join(dir, `${name}.cmd`), `@echo off\r\nrem ${name}, the MARGIE command line. ${MARK}.\r\n"${bash}" "%~dp0${name}" %*\r\n`, 0o755) && written;
		}
		const onPath = (env.Path || env.PATH || '').split(';').includes(dir) || (await addToWindowsPath(dir));
		return { file: path.join(dir, 'margie'), written, onPath, profile: '' };
	}
	const dir = path.join(home, '.local', 'bin');
	const file = path.join(dir, 'margie');
	let written = true;
	for (const [name, text] of Object.entries(scripts)) written = writeOurs(path.join(dir, name), text, 0o755) && written;
	const parts = loginPath.split(':');
	let profile = '';
	let onPath = parts.includes(dir) || parts.includes('~/.local/bin');
	if (!onPath && loginPath) {
		// New terminals read it; this one keeps its PATH.
		const startup = shellProfile({ home, shell: env.SHELL, platform });
		if (startup && addToProfile(startup, dir, home)) profile = startup;
		onPath = !!startup;
	}
	// Another margie earlier on PATH (an older launcher) would answer first.
	const first = parts.slice(0, Math.max(0, parts.indexOf(dir))).find((p) => p && fs.existsSync(path.join(p, 'margie')));
	return { file, written, onPath, profile, before: first ? path.join(first, 'margie') : '' };
}
