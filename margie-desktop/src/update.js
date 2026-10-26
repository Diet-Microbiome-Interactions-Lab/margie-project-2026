/**
 * Looks for a newer build of the app on the repository's latest GitHub release, whatever its
 * version number: a release can carry new installers under the same version. The release's
 * build-info.json names its build (scripts/stage.mjs writes one into each build and beside the
 * installers); without one, an installer uploaded more than 12 hours after this copy was built
 * counts as newer. A newer build is offered: its installer for this system is downloaded to the
 * Downloads folder and opened, to install over this copy. Checked a little after start and once a
 * day while "Check for Updates Automatically" is on, and from the menu.
 */

import fs from 'node:fs';
import { once } from 'node:events';
import path from 'node:path';
import { app, dialog, shell } from './electron.js';
import electron from './electron.js';
import { prefs, setPref } from './app-prefs.js';
import { log } from './log.js';

const REPO = 'Diet-Microbiome-Interactions-Lab/margie-project-2026';
const LATEST = `https://api.github.com/repos/${REPO}/releases/latest`;
const PAGE = `https://github.com/${REPO}/releases/latest`;
const INFO = 'build-info.json';
const FIRST_LOOK = 15_000;
const DAY = 24 * 3600 * 1000;
// Installers go up within hours of their build; one uploaded later than this is a newer build.
const LEEWAY = 12 * 3600 * 1000;

/** This copy's build: {id, builtAt, commit}; empty fields in a development run. */
export function thisBuild() {
	try {
		const info = JSON.parse(fs.readFileSync(path.join(process.resourcesPath, INFO), 'utf8'));
		return { id: String(info.id ?? ''), builtAt: String(info.builtAt ?? ''), commit: String(info.commit ?? '') };
	} catch {
		return { id: '', builtAt: '', commit: '' };
	}
}

/**
 * The release asset that installs on this system: the macOS disk image, the Windows installer
 * (or its zip on ARM), and on Linux the AppImage when running from one, else the .deb.
 * @param {{name: string}[]} assets
 */
export function installerFor(assets, platform = process.platform, arch = process.arch, appImage = process.env.APPIMAGE) {
	const named = (test) => assets.find((a) => test(a.name.toLowerCase()));
	if (platform === 'darwin') return named((n) => n.endsWith(`-${arch}.dmg`)) ?? named((n) => n.endsWith('.dmg'));
	if (platform === 'win32')
		return arch === 'arm64'
			? (named((n) => n.endsWith('-arm64-win.zip')) ?? named((n) => n.endsWith('setup.exe')))
			: named((n) => n.endsWith('setup.exe'));
	if (platform === 'linux') {
		const linuxArch = arch === 'x64' ? (appImage ? 'x86_64' : 'amd64') : arch;
		return appImage
			? named((n) => n.endsWith(`-${linuxArch}.appimage`))
			: (named((n) => n.endsWith(`-${linuxArch}.deb`)) ?? named((n) => n.endsWith(`-${linuxArch}.appimage`)));
	}
	return undefined;
}

async function getJson(url) {
	const res = await electron.net.fetch(url, { headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'MARGIE-desktop' } });
	if (!res.ok) throw new Error(`GitHub answered ${res.status}`);
	return res.json();
}

/**
 * The latest release's build, when it is newer than this copy: {id, builtAt, asset}; null when
 * this copy is current or no installer fits this system.
 */
export async function newerBuild(mine = thisBuild(), fetchJson = getJson) {
	const release = await fetchJson(LATEST);
	const assets = release?.assets ?? [];
	const asset = installerFor(assets);
	if (!asset) return null;
	const info = assets.find((a) => a.name === INFO);
	if (info) {
		const theirs = await fetchJson(info.browser_download_url);
		const id = String(theirs?.id ?? '');
		const builtAt = String(theirs?.builtAt ?? '');
		return id && id !== mine.id && builtAt > mine.builtAt ? { id, builtAt, asset } : null;
	}
	const uploaded = Date.parse(asset.updated_at);
	const built = Date.parse(mine.builtAt);
	return Number.isFinite(built) && uploaded > built + LEEWAY ? { id: `${asset.name}@${asset.updated_at}`, builtAt: asset.updated_at, asset } : null;
}

const day = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'unknown');

/** Downloads the installer to the Downloads folder, the window's progress bar following it. */
async function download(asset, getWindow) {
	const target = path.join(app.getPath('downloads'), asset.name);
	const res = await electron.net.fetch(asset.browser_download_url);
	if (!res.ok || !res.body) throw new Error(`the download answered ${res.status}`);
	const total = Number(res.headers.get('content-length')) || asset.size || 0;
	const out = fs.createWriteStream(`${target}.part`);
	let got = 0;
	try {
		for await (const chunk of res.body) {
			if (!out.write(chunk)) await once(out, 'drain');
			got += chunk.length;
			if (total) getWindow()?.setProgressBar(got / total);
		}
	} finally {
		await new Promise((resolve) => out.end(resolve));
		getWindow()?.setProgressBar(-1);
	}
	fs.renameSync(`${target}.part`, target);
	return target;
}

/** Opens the downloaded installer; an AppImage is made runnable and shown in its folder. */
async function openInstaller(file) {
	if (file.toLowerCase().endsWith('.appimage')) {
		fs.chmodSync(file, 0o755);
		shell.showItemInFolder(file);
		return '';
	}
	return shell.openPath(file);
}

let checking = false;

/**
 * Looks for a newer build and offers it. `manual`: from the menu, so "up to date" and network
 * problems are said too, and a build the user skipped is offered again.
 */
export async function checkForUpdates({ manual = false, getWindow = () => null } = {}) {
	if (checking) return;
	const mine = thisBuild();
	if (!mine.id) {
		if (manual) dialog.showMessageBox({ type: 'info', message: 'This copy of MARGIE is a development build.', detail: 'Installed copies look for updates on GitHub.', buttons: ['OK'] });
		return;
	}
	checking = true;
	try {
		const newer = await newerBuild(mine);
		if (!newer) {
			if (manual) dialog.showMessageBox({ type: 'info', message: 'MARGIE is up to date.', detail: `This copy was built ${day(mine.builtAt)}.`, buttons: ['OK'] });
			return;
		}
		if (!manual && prefs().skipBuild === newer.id) return;
		log.info(`a newer build is on GitHub: ${newer.id} (this copy: ${mine.id})`);
		const { response } = await dialog.showMessageBox(getWindow() ?? undefined, {
			type: 'info',
			message: 'A newer build of MARGIE is available.',
			detail:
				`It was built ${day(newer.builtAt)}; this copy was built ${day(mine.builtAt)}.\n\n` +
				`MARGIE downloads its installer (${newer.asset.name}) to your Downloads folder and opens it: install it over this copy. ` +
				'Your settings, genomes and runs stay as they are.',
			buttons: ['Download and Install', 'Later', 'Skip This Build'],
			defaultId: 0,
			cancelId: 1
		});
		if (response === 2) setPref('skipBuild', newer.id);
		if (response !== 0) return;
		const file = await download(newer.asset, getWindow);
		log.info(`downloaded the new build to ${file}`);
		const problem = await openInstaller(file);
		if (problem) throw new Error(problem);
		const quit = await dialog.showMessageBox(getWindow() ?? undefined, {
			type: 'info',
			message: 'The installer is open.',
			detail: `It is in ${path.dirname(file)}. Quit MARGIE so the installer can replace this copy, then open MARGIE again.`,
			buttons: ['Quit MARGIE', 'Later'],
			defaultId: 0,
			cancelId: 1
		});
		if (quit.response === 0) app.quit();
	} catch (err) {
		log.warn('the update check failed:', err);
		if (manual) {
			const { response } = await dialog.showMessageBox({
				type: 'warning',
				message: 'MARGIE could not finish the update.',
				detail: `${err?.message ?? err}\n\nThe newest installers are on the Releases page.`,
				buttons: ['Open Releases', 'OK'],
				defaultId: 0,
				cancelId: 1
			});
			if (response === 0) void shell.openExternal(PAGE);
		}
	} finally {
		checking = false;
	}
}

/** A first look shortly after start, then one a day, while automatic checks are on. */
export function scheduleUpdateChecks(getWindow) {
	const look = () => {
		if (prefs().updates) void checkForUpdates({ getWindow });
	};
	setTimeout(look, FIRST_LOOK).unref?.();
	setInterval(look, DAY).unref?.();
}
