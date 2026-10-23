import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** Run SSH is the Terminal now. */
export function load({ url }) {
	redirect(308, currentPath('run_ssh', url.search));
}
