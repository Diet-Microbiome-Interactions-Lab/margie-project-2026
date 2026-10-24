import { error, json } from '@sveltejs/kit';
import { make } from '$lib/server/file-ops';
import type { RequestHandler } from './$types';

/** Body: { path, kind: 'folder' | 'file' }. Makes a folder (and any above it) or an empty text file. */
export const POST: RequestHandler = async ({ request, url }) => {
	const origin = request.headers.get('origin');
	if (origin && origin !== url.origin) error(403, 'Not from this app.');
	const body = await request.json().catch(() => null);
	const kind = body?.kind === 'folder' || body?.kind === 'file' ? body.kind : null;
	if (!kind || typeof body?.path !== 'string' || !body.path.trim()) error(400, 'Expected { path, kind: folder or file }.');
	try {
		return json(make(body.path, kind));
	} catch (e) {
		error(400, e instanceof Error ? e.message : String(e));
	}
};
