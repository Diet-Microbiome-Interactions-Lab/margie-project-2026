import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** Analysis history is the Jobs page now. */
export function load({ url }) {
	redirect(308, currentPath('jobs', url.search));
}
