/**
 * Settings → Advanced: config.yaml and MARGIE's Snakemake workflow open to edit after Unlock, for
 * this browser session. Settings, the file viewer and the editor read the same lock, so the two
 * files are edited by hand only once they are unlocked.
 */

const KEY = 'margie.advanced.unlocked';

function stored(): boolean {
	try {
		return sessionStorage.getItem(KEY) === '1';
	} catch {
		return false;
	}
}

class AdvancedLock {
	open = $state(stored());

	set(on: boolean) {
		this.open = on;
		try {
			if (on) sessionStorage.setItem(KEY, '1');
			else sessionStorage.removeItem(KEY);
		} catch {
			// Kept for this page only.
		}
	}
}

export const advanced = new AdvancedLock();

/** config.yaml (~/.config/bioinformatics-tools/) and MARGIE's workflow (workflow_tools/margie_sb.smk). */
export const lockedFile = (path: string) =>
	/(^|\/)\.config\/bioinformatics-tools\/config\.ya?ml$/.test(path) || /(^|\/)workflow_tools\/margie_sb\.smk$/.test(path);
