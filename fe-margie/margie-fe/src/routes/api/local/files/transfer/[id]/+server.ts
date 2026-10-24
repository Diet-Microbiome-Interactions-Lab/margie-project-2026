import { error, json } from '@sveltejs/kit';
import { taskOf } from '$lib/server/file-ops';
import type { RequestHandler } from './$types';

/** A copy, move or delete started here: its state and each item's result. */
export const GET: RequestHandler = async ({ params }) => {
	const task = taskOf(params.id);
	if (!task) error(404, 'No such copy, move or delete (the app may have restarted since).');
	return json(task);
};
