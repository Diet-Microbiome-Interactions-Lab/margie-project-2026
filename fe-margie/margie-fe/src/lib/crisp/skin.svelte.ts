/**
 * The Skeleton theme the site wears, from the ones Dane's pages load (routes/layout.css):
 * Cerberus, his default, and four more. It is set on <html data-theme>, so every page and
 * every Skeleton part follows it; the choice is kept in this browser.
 */

export const SKINS = [
	{ id: 'cerberus', name: 'Cerberus', note: 'the original' },
	{ id: 'rocket', name: 'Rocket' },
	{ id: 'modern', name: 'Modern' },
	{ id: 'vintage', name: 'Vintage' },
	{ id: 'seafoam', name: 'Seafoam' }
] as const;

export type SkinId = (typeof SKINS)[number]['id'];

const KEY = 'margie.skin';
const FIRST: SkinId = 'cerberus';

function stored(): SkinId {
	try {
		const v = localStorage.getItem(KEY);
		return SKINS.some((s) => s.id === v) ? (v as SkinId) : FIRST;
	} catch {
		return FIRST;
	}
}

let id = $state<SkinId>(typeof window === 'undefined' ? FIRST : stored());

export const skin = {
	get id() {
		return id;
	},
	set(next: SkinId) {
		id = next;
		try {
			localStorage.setItem(KEY, next);
		} catch {
			// Not kept: the next visit opens Cerberus.
		}
	},
	/** Puts the theme, and light or dark, on the page. */
	apply(dark?: boolean) {
		if (typeof document === 'undefined') return;
		const html = document.documentElement;
		html.dataset.theme = id;
		if (dark !== undefined) html.classList.toggle('dark', dark);
	}
};
