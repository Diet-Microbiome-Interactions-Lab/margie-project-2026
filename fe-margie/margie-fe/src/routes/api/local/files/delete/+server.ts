import { error, json } from '@sveltejs/kit';
import { remove } from '$lib/server/file-ops';
import type { RequestHandler } from './$types';

/** Body: { paths }. Deletes them (folders with everything in them); follow it at ../transfer/[id]. */
export const POST: RequestHandler = async ({ request, url }) => {
	const origin = request.headers.get('origin');
	if (origin && origin !== url.origin) error(403, 'Not from this app.');
	const body = await request.json().catch(() => null);
	const paths = Array.isArray(body?.paths) ? body.paths.filter((s: unknown) => typeof s === 'string' && s.trim()) : [];
	if (!paths.length || paths.length > 500) error(400, 'Expected { paths: 1 to 500 paths }.');
	return json(remove(paths));
};
