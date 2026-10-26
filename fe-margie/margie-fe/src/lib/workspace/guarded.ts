/**
 * Settings that ask before they change, such as the margie-build folder. The phrase is the
 * build password, which only the API checks (api/build_gate.py); nothing of it is in this
 * code, which is public.
 */
import { call } from '$lib/cluster/http';

/** Setting keys that need unlocking, and what to say when asking. */
export const GUARDED: Record<string, { title: string; why: string }> = {
	SETUP_REPO: {
		title: 'Unlock the build folder',
		why: 'This is where MARGIE looks for margie-build, which builds the container images and downloads the databases. Changing it redirects every build.'
	}
	// On a cluster, margie_sb.build_repo is a folder like the others: building itself asks for the build password (Install).
};

export const isGuarded = (key: string) => key in GUARDED;

/** Settings that unlock with a click after the page explains why and what is recommended. */
export const CONFIRMED: Record<string, { title: string; why: string }> = {
	'margie_sb.backup_root': {
		title: 'Change where backups go',
		why: 'Backups of your databases go beside the base copies on depot. On a shared cluster, for a laboratory’s in-house studies, keeping them there is recommended: everyone’s work stays in one place, and depot is kept.'
	}
};

export const isConfirmed = (key: string) => key in CONFIRMED;

/** Asks the API whether the trimmed phrase is the build password, which unlocks the guarded settings. */
export async function unlocks(phrase: string): Promise<boolean> {
	const text = phrase.trim();
	if (!text) return false;
	try {
		await call('POST', '/v1/ssh/assets/build-unlock', { password: text });
		return true;
	} catch {
		// Not the password, or the API could not be asked: the field stays locked.
		return false;
	}
}
