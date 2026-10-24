import { error, json } from '@sveltejs/kit';
import { transfer } from '$lib/server/file-ops';
import type { RequestHandler } from './$types';

/** Body: { op: 'copy' | 'move', sources: [paths], into }. Starts the copy or move; follow it at ./[id]. */
export const POST: RequestHandler = async ({ request, url }) => {
	const origin = request.headers.get('origin');
	if (origin && origin !== url.origin) error(403, 'Not from this app.');
	const body = await request.json().catch(() => null);
	const op = body?.op === 'copy' || body?.op === 'move' ? body.op : null;
	const sources = Array.isArray(body?.sources) ? body.sources.filter((s: unknown) => typeof s === 'string' && s.trim()) : [];
	if (!op || !sources.length || sources.length > 500 || typeof body?.into !== 'string') error(400, 'Expected { op: copy or move, sources: 1 to 500 paths, into }.');
	try {
		return json(transfer(op, sources, body.into));
	} catch (e) {
		error(400, e instanceof Error ? e.message : String(e));
	}
};
