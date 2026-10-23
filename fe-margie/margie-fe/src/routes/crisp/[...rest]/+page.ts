import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** Old Modern-interface links (/crisp/...) open the same page at its address today. */
export function load({ params, url }) {
	redirect(308, currentPath(params.rest, url.search));
}
