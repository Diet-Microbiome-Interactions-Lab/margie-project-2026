/**
 * The interface's colour, type and shape variables (--mg-*, --cr-*), taken from the Skeleton
 * theme on <html data-theme> (see skin.svelte.ts): its surfaces, primary colour, status
 * colours, font and corners. Sizes and spacing still come from crisp/theme.ts.
 *
 * As on Dane's pages: a near-white page, flat grey cards with no outline, white fields,
 * bold page titles in the primary colour.
 */
export function skeletonVars(dark: boolean, keepStatus = false): Record<string, string> {
	const sf = (light: number, night: number) => `var(--color-surface-${dark ? night : light})`;
	const c = (name: string, light: number, night: number) => `var(--color-${name}-${dark ? night : light})`;
	const mix = (colour: string, pct: number, over = 'transparent') => `color-mix(in oklab, ${colour} ${pct}%, ${over})`;
	const primary = c('primary', 500, 400);
	// With a colour vision chosen, the states keep the colours picked for it (crisp/theme.ts).
	const status: Record<string, string> = keepStatus
		? {}
		: {
				'--mg-ok': c('success', 800, 400),
				'--mg-warn': c('warning', 900, 400),
				'--mg-warn-soft': mix('var(--color-warning-500)', 20),
				'--mg-danger': c('error', 600, 400),
				'--mg-danger-soft': mix('var(--color-error-500)', 14),
				'--cr-warm': c('warning', 900, 400)
			};
	return {
		...status,
		'--mg-font': 'var(--base-font-family)',
		'--cr-display': 'var(--heading-font-family, var(--base-font-family))',
		'--mg-bg': dark ? 'var(--body-background-color-dark)' : 'var(--body-background-color)',
		'--mg-surface': sf(50, 900),
		'--mg-surface-2': sf(100, 800),
		'--mg-seg-sel': sf(50, 700),
		'--mg-border': sf(200, 700),
		'--mg-border-strong': sf(300, 600),
		'--mg-text': sf(950, 50),
		'--mg-text-2': sf(700, 200),
		'--mg-text-3': sf(500, 400),
		'--mg-accent': primary,
		'--mg-accent-base': primary,
		'--mg-accent-ink': c('primary', 600, 300),
		'--mg-accent-soft': mix(primary, 14),
		'--mg-on-accent': 'var(--color-primary-contrast-500)',
		'--mg-r': 'var(--radius-container)',
		'--mg-r-sm': 'var(--radius-base)',
		'--mg-shadow-sm': 'none',
		// Cards: flat grey on the page, no outline; what is typed or picked inside sits on white.
		'--cr-card': sf(100, 900),
		'--cr-card-edge': 'transparent',
		'--cr-card-inner': sf(50, 800),
		'--cr-head-bg': sf(200, 800),
		'--cr-bar-bg': sf(100, 900),
		'--cr-rule': sf(200, 700),
		'--cr-zebra': mix(sf(950, 50), 3),
		'--cr-field-edge': sf(300, 600),
		// Titles: the page's in the primary colour, a block's in ink, labels lighter.
		'--cr-page': primary,
		'--cr-t2': sf(950, 50),
		'--cr-t3': sf(700, 200),
		'--cr-t4': sf(600, 300),
		'--cr-glow': '0%',
		// No per-page or per-block tints: one theme colour, as on the original pages.
		'--sh-head': '0%',
		'--sh-rail': '0%',
		'--sh-title': '0%',
		'--sh-field': '0%',
		'--sh-accent': '0%'
	};
}

/**
 * The other way round, for every palette but Original: Skeleton's tokens taken from the
 * interface's own colours, so Dane's parts (the bar, the sidebar, his pages' cards and
 * buttons) follow the accent, surfaces, type and corners chosen in Customize.
 */
export function skeletonFromPalette(dark: boolean): Record<string, string> {
	const a = 'var(--mg-accent-base)';
	const toward = (pct: number, to: string) => `color-mix(in oklab, ${a} ${pct}%, ${to})`;
	const ramp: Record<number, string> = {
		50: toward(10, 'white'),
		100: toward(20, 'white'),
		200: toward(36, 'white'),
		300: toward(56, 'white'),
		400: toward(78, 'white'),
		500: a,
		600: toward(86, 'black'),
		700: toward(72, 'black'),
		800: toward(58, 'black'),
		900: toward(44, 'black'),
		950: toward(32, 'black')
	};
	const out: Record<string, string> = {};
	for (const [k, v] of Object.entries(ramp)) {
		out[`--color-primary-${k}`] = v;
		out[`--color-primary-contrast-${k}`] = Number(k) >= 400 ? 'var(--mg-on-accent)' : 'var(--mg-text)';
	}
	// Skeleton's light/dark pairs are worked out where they are defined, so they are set again here.
	const pair = (light: number, night: number) => (dark ? ramp[night] : ramp[light]);
	Object.assign(out, {
		'--color-primary-50-950': pair(50, 950),
		'--color-primary-100-900': pair(100, 900),
		'--color-primary-950-50': pair(950, 50),
		'--color-primary-600-400': pair(600, 400),
		'--color-primary-400-600': pair(400, 600),
		// The bar and the sidebar, the page's fields and boxes, and their lines.
		'--color-surface-100-900': 'var(--mg-surface-2)',
		'--color-surface-50-950': 'var(--mg-surface)',
		'--color-surface-200-800': 'var(--mg-border)',
		'--color-surface-300-700': 'var(--mg-border-strong)',
		// Dane's pages' cards (bg-surface-100, dark:bg-surface-800) and their hover shade.
		[dark ? '--color-surface-800' : '--color-surface-100']: 'var(--mg-surface)',
		[dark ? '--color-surface-700' : '--color-surface-200']: 'var(--mg-surface-2)',
		'--base-font-family': 'var(--mg-font)',
		'--heading-font-family': 'var(--mg-font)',
		'--radius-base': 'var(--mg-r-sm)',
		'--radius-container': 'var(--mg-r)',
		'--cr-page': a
	});
	return out;
}

/**
 * With a colour vision chosen: Skeleton's success, warning and error ramps taken from the
 * states' colours picked for that vision, so Dane's parts (badges, alerts, buttons) change too.
 */
export function statusFromVision(dark: boolean): Record<string, string> {
	const out: Record<string, string> = {};
	const PAIRS: [number, number][] = [
		[50, 950],
		[100, 900],
		[200, 800],
		[300, 700],
		[400, 600],
		[500, 500],
		[600, 400],
		[700, 300],
		[800, 200],
		[900, 100],
		[950, 50]
	];
	for (const [name, from] of [
		['success', 'var(--mg-ok)'],
		['warning', 'var(--mg-warn)'],
		['error', 'var(--mg-danger)']
	]) {
		const toward = (pct: number, to: string) => `color-mix(in oklab, ${from} ${pct}%, ${to})`;
		const ramp: Record<number, string> = {
			50: toward(10, 'white'),
			100: toward(20, 'white'),
			200: toward(36, 'white'),
			300: toward(56, 'white'),
			400: toward(78, 'white'),
			500: from,
			600: toward(86, 'black'),
			700: toward(72, 'black'),
			800: toward(58, 'black'),
			900: toward(44, 'black'),
			950: toward(32, 'black')
		};
		for (const [k, v] of Object.entries(ramp)) out[`--color-${name}-${k}`] = v;
		// The light/dark pairs are worked out where Skeleton defines them, so they are set again here.
		for (const [light, night] of PAIRS) if (light !== night) out[`--color-${name}-${light}-${night}`] = dark ? ramp[night] : ramp[light];
	}
	return out;
}
