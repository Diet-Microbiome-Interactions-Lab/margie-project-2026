import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** Links to the retired Atlas interface open the same page today. */
export function load({ params, url }) {
	redirect(308, currentPath(params.rest, url.search));
}
