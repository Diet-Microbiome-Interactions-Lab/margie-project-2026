import { redirect } from '@sveltejs/kit';
import { HOSTED } from '$lib/hosted';

/** The desktop app signs in to the HPC, or creates the account, on its start page. */
export function load() {
	if (!HOSTED) redirect(307, '/start');
}
