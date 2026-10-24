import { error, json } from '@sveltejs/kit';
import { lockBuild, openBuildFolder, passwordOpens, unlockBuild, vaultBundled } from '$lib/server/build-vault';
import { listRuns } from '$lib/server/runs';
import type { RequestHandler } from './$types';

/** The build files this app carries (lib/server/build-vault): { bundled, open, path }. */
const state = () => ({ bundled: vaultBundled(), open: !!openBuildFolder(), path: openBuildFolder() });

const building = () => listRuns().some((r) => r.kind === 'build' && r.status === 'running');

export const GET: RequestHandler = async () => json(state());

/** Body: { password, check? }. Unpacks the build files for this session; check only tests the password. */
export const POST: RequestHandler = async ({ request, url }) => {
	const origin = request.headers.get('origin');
	if (origin && origin !== url.origin) error(403, 'Not from this app.');
	const body = await request.json().catch(() => null);
	const password = typeof body?.password === 'string' ? body.password : '';
	if (!vaultBundled()) error(404, 'This app carries no build files.');
	if (body?.check === true) {
		if (!passwordOpens(password)) error(403, 'That is not the build password.');
		return json(state());
	}
	if (!unlockBuild(password)) error(403, 'That is not the build password.');
	return json(state());
};

/** Locks the build files again; they stay while a build runs from them. */
export const DELETE: RequestHandler = async ({ request, url }) => {
	const origin = request.headers.get('origin');
	if (origin && origin !== url.origin) error(403, 'Not from this app.');
	if (building()) return json({ ...state(), kept: 'A build is running from them.' });
	lockBuild();
	return json(state());
};
