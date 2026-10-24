/**
 * "Email me about my runs" (the profile's notify_runs) and where the emails go, for the User
 * profile and Analyze alike: the account's Purdue address on a Purdue cluster, and the email on
 * the User profile (PUT /v1/auth/profile).
 */
import { authHeaders } from '$lib/auth.js';
import { getApiUrl } from '$lib/config';
import { ui } from './ui.svelte';

type Me = { notify_runs?: boolean; email?: string; cluster_username?: string; cluster_host?: string };

class RunEmails {
	on = $state(true);
	loaded = $state(false);
	purdue = $state('');
	email = $state('');
	/** Where the emails go ("a@purdue.edu and b@lab.org"); empty when there is no address. */
	to = $derived(
		[this.purdue, this.email.trim()].filter((a, i, all) => a && all.findIndex((b) => b.toLowerCase() === a.toLowerCase()) === i).join(' and ')
	);

	/** Takes the switch and the addresses from a profile (GET /v1/auth/me, or a save's answer). */
	take(d: Me) {
		if (typeof d.notify_runs === 'boolean') this.on = d.notify_runs;
		this.email = d.email ?? '';
		this.purdue = d.cluster_username && /(^|\.)purdue\.edu$/i.test(d.cluster_host ?? '') ? `${d.cluster_username}@purdue.edu` : '';
		this.loaded = true;
	}

	async load() {
		try {
			const res = await fetch(`${getApiUrl()}/v1/auth/me`, { headers: authHeaders() });
			if (res.ok) this.take(await res.json());
		} catch {
			// Left as not loaded: the switch waits.
		}
	}

	async set(on: boolean) {
		this.on = on;
		try {
			const res = await fetch(`${getApiUrl()}/v1/auth/profile`, {
				method: 'PUT',
				headers: { ...authHeaders(), 'Content-Type': 'application/json' },
				body: JSON.stringify({ notify_runs: on })
			});
			if (!res.ok) throw new Error('The email setting could not be saved.');
			ui.notify(on ? 'Emails about your runs are on.' : 'Emails about your runs are off.', 'ok');
		} catch (e) {
			this.on = !on;
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		}
	}
}

export const runEmails = new RunEmails();
