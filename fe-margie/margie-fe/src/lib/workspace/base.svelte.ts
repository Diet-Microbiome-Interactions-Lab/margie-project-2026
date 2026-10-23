/**
 * Holds the base path of the interface's pages so shared parts link inside it. The pages
 * live at the site's root (/analyze, /jobs, ...), so it is empty; a shell may set another.
 */

let path = $state('');

export const uiBase = {
	get path() {
		return path;
	},
	set(to: string) {
		path = to;
	},
	/** `uiBase.to('/results')` -> `/results` (or under the base a shell set). */
	to(rest: string) {
		return path + rest;
	}
};
