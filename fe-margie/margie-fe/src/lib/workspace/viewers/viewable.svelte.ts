/**
 * Resolves a file URL an <img> or <iframe> can load: the URL itself here, or a
 * local copy fetched with sign-in where files need one (cluster).
 */

import { viewableUrl } from '$lib/api';

export function viewable(src: () => string) {
	let url = $state('');
	let error = $state('');
	$effect(() => {
		const from = src();
		let live = true;
		url = '';
		error = '';
		// The copy belongs to viewableUrl's cache, which releases it when it lets it go, so a
		// figure seen again shows at once.
		viewableUrl(from)
			.then((u) => {
				if (live) url = u;
			})
			.catch((e) => {
				if (live) error = e instanceof Error ? e.message : String(e);
			});
		return () => {
			live = false;
		};
	});
	return {
		get url() {
			return url;
		},
		get error() {
			return error;
		}
	};
}
