import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** File Search is part of Files now. */
export function load({ url }) {
	redirect(308, currentPath('filesearch', url.search));
}
