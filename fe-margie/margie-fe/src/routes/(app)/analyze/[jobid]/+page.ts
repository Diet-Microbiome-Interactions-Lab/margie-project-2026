import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** A job opened from the old Analyze page opens on Jobs. */
export function load({ params, url }) {
	redirect(308, currentPath(`jobs/${params.jobid}`, url.search));
}
