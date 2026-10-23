import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** The old file view opens the job on Jobs. */
export function load({ params, url }) {
	redirect(308, currentPath(`jobs/${params.id}`, url.search));
}
