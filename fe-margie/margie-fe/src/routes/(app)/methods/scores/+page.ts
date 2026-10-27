import { redirect } from '@sveltejs/kit';
import { HOSTED } from '$lib/hosted';

/** The locked pages come with the website alone, so the desktop app opens Methods. */
export function load() {
	if (!HOSTED) redirect(307, '/methods');
}
