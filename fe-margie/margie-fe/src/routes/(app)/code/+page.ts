import { redirect } from '@sveltejs/kit';
import { HOSTED } from '$lib/hosted';

/** The desktop app ships no code: its Methods page describes the steps. */
export function load() {
	if (!HOSTED) redirect(307, '/methods');
}
