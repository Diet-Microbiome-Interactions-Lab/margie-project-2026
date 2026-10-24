import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** A job's own page is the Jobs page with that job picked: its progress, then its log. */
export function load({ params, url }) {
	redirect(308, currentPath(`jobs/${params.id}`, url.search));
}
