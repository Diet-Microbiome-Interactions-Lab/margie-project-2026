import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** The old genome map opens on Results. */
export function load({ url }) {
	redirect(308, currentPath('map', url.search));
}
