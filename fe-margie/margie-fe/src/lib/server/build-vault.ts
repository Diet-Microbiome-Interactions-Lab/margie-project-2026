/**
 * The build files (margie-build) the desktop app carries, locked with the build password
 * (margie-desktop/scripts/stage.mjs writes the same format). The password unpacks them into a
 * folder for this session, which the app removes on quit and at start; while it is there, local
 * mode uses it as the setup folder unless Settings names another.
 *
 * The file: "MARGIEB1", a 16-byte scrypt salt, a 12-byte IV, the 16-byte GCM tag, then the
 * AES-256-GCM ciphertext of gzip'd JSON { files: [[path, mode, base64]] }.
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const MAGIC = Buffer.from('MARGIEB1');
const SCRYPT = { N: 1 << 15, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };

/** The locked file (MARGIE_BUILD_VAULT) and the session folder it opens into (MARGIE_BUILD_OPEN). */
const VAULT = process.env.MARGIE_BUILD_VAULT || '';
const OPEN_DIR = process.env.MARGIE_BUILD_OPEN || '';

export const vaultBundled = () => !!VAULT && !!OPEN_DIR && fs.existsSync(VAULT);

/** The unlocked build files, or '' while they are locked. */
export function openBuildFolder(): string {
	return OPEN_DIR && fs.existsSync(path.join(OPEN_DIR, 'build.sh')) ? OPEN_DIR : '';
}

/** The archive inside, or null when the password does not open it. */
function decrypt(password: string): Buffer | null {
	const blob = fs.readFileSync(VAULT);
	if (blob.length < 52 || !blob.subarray(0, 8).equals(MAGIC)) throw new Error('The build files in this app are damaged.');
	const key = crypto.scryptSync(password, blob.subarray(8, 24), 32, SCRYPT);
	const d = crypto.createDecipheriv('aes-256-gcm', key, blob.subarray(24, 36));
	d.setAuthTag(blob.subarray(36, 52));
	try {
		return Buffer.concat([d.update(blob.subarray(52)), d.final()]);
	} catch {
		return null;
	}
}

/** Whether the password opens the build files. */
export function passwordOpens(password: string): boolean {
	return vaultBundled() && !!password.trim() && decrypt(password.trim()) !== null;
}

/** Unpacks the build files into the session folder. Returns false when the password is wrong. */
export function unlockBuild(password: string): boolean {
	if (!vaultBundled()) throw new Error('This app carries no build files.');
	const archive = password.trim() ? decrypt(password.trim()) : null;
	if (!archive) return false;
	const { files } = JSON.parse(zlib.gunzipSync(archive).toString('utf8')) as { files: [string, number, string][] };
	const tmp = `${OPEN_DIR}.part`;
	fs.rmSync(tmp, { recursive: true, force: true });
	for (const [rel, mode, data] of files) {
		const to = path.resolve(tmp, rel);
		if (!to.startsWith(tmp + path.sep)) throw new Error(`The build files hold a path outside their folder: ${rel}`);
		fs.mkdirSync(path.dirname(to), { recursive: true });
		fs.writeFileSync(to, Buffer.from(data, 'base64'), { mode: mode & 0o777 });
	}
	fs.rmSync(OPEN_DIR, { recursive: true, force: true });
	fs.renameSync(tmp, OPEN_DIR);
	return true;
}

/** Removes the unpacked build files. */
export function lockBuild() {
	if (!OPEN_DIR) return;
	fs.rmSync(OPEN_DIR, { recursive: true, force: true });
	fs.rmSync(`${OPEN_DIR}.part`, { recursive: true, force: true });
}
