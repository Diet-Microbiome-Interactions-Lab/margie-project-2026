/**
 * Theme presets (page, card, line and three text neutrals per light, all text
 * at 4.5:1 or better), the theme editor's tokens and its contrast checks. Hand
 * edits (UiPrefs.colours) layer over them in prefs.ts resolveColours.
 */

import type { UiPrefs } from './prefs';
import { SHADES } from './shades';
import { ALIKE, CLOSE, contrast, distance, TIER_NAMES, visionInfo, type Vision } from './vision';

export interface Neutrals {
	bg: string;
	surface: string;
	surface2: string;
	border: string;
	borderStrong: string;
	text: string;
	text2: string;
	text3: string;
}

export interface Preset {
	id: string;
	name: string;
	note: string;
	light: Neutrals;
	dark: Neutrals;
	/** Status colours of its own (ok, warn, danger), for a preset that needs them stronger. */
	status?: { light: string[]; dark: string[] };
	/** The accent (prefs ACCENTS) that goes with it: choosing the preset chooses it too. */
	accent?: string;
}

/** Converts HSL to #RRGGBB. */
function hsl(h: number, s: number, l: number): string {
	const a = (Math.max(0, Math.min(100, s)) / 100) * Math.min(l / 100, 1 - l / 100);
	const part = (n: number) => {
		const k = (n + h / 30) % 12;
		const v = l / 100 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
		return Math.round(255 * v)
			.toString(16)
			.padStart(2, '0');
	};
	return `#${part(0)}${part(8)}${part(4)}`.toUpperCase();
}

/** Builds a full set of neutrals from one hue, reusing the hand-made presets' lightness steps. */
function ramp(h: number, s: number): { light: Neutrals; dark: Neutrals } {
	const mid = s * 0.8;
	return {
		light: {
			bg: hsl(h, s * 0.9, 98),
			surface: hsl(h, s * 0.45, 100),
			surface2: hsl(h, s, 96),
			border: hsl(h, mid, 90),
			borderStrong: hsl(h, mid, 79),
			text: hsl(h, mid, 10),
			text2: hsl(h, mid * 0.8, 31),
			// 41 rather than 44: greens carry more luminance, so this keeps text3 at 4.5:1.
			text3: hsl(h, mid * 0.7, 41)
		},
		dark: {
			bg: hsl(h, s, 7),
			surface: hsl(h, s, 10),
			surface2: hsl(h, s, 14),
			border: hsl(h, mid, 21),
			borderStrong: hsl(h, mid, 31),
			text: hsl(h, mid * 0.4, 93),
			text2: hsl(h, mid * 0.5, 74),
			text3: hsl(h, mid * 0.5, 60)
		}
	};
}

/** id, name, note, hue, how much hue. */
const GENERATED: [string, string, string, number, number][] = [
	['ocean', 'Ocean', 'Deep blue, cool and quiet', 205, 24],
	['storm', 'Storm', 'Overcast blue-grey', 200, 12],
	['indigo', 'Indigo', 'Blue-violet, low and even', 250, 22],
	['teal', 'Teal', 'Blue-green, clean edges', 182, 22],
	['forest', 'Forest', 'Green, deep and steady', 150, 20],
	['moss', 'Moss', 'Soft green, easy on the eye', 110, 16],
	['olive', 'Olive', 'Dry green-gold', 80, 18],
	['sand', 'Sand', 'Warm neutral, like a field notebook', 40, 22],
	['copper', 'Copper', 'Warm metal, amber lines', 25, 26],
	['clay', 'Clay', 'Earth red, muted', 16, 22],
	['ember', 'Ember', 'Warm red, low light', 8, 24],
	['rose', 'Rose', 'Pink-red, gentle', 345, 18],
	['plum', 'Plum', 'Purple-red, rich at night', 300, 18],
	['lilac', 'Lilac', 'Pale violet', 275, 16],
	['ink', 'Ink', 'Almost neutral, a shade of blue', 230, 10],
	['graphite', 'Graphite', 'Grey, nearly colourless', 220, 5]
];

const HAND_MADE: Preset[] = [
	{
		id: 'crisp',
		accent: 'graphite',
		name: 'Modern',
		note: 'White boxes on cool grey',
		// Lines (hairlines between rows) a faint blue-white, so rows part without ruling the page.
		light: { bg: '#F5F6F8', surface: '#FFFFFF', surface2: '#F4F5F7', border: '#F5F8FF', borderStrong: '#C4C8CE', text: '#15181D', text2: '#454C57', text3: '#646B76' },
		// Charcoal at night, lifted off black so boxes, lines and the bars stay readable.
		dark: { bg: '#1C1F25', surface: '#23272E', surface2: '#2A2F37', border: '#373D47', borderStrong: '#4D5461', text: '#ECEEF1', text2: '#BEC4CD', text3: '#A1A8B2' }
	},
	{
		// Dane's pages as they were: the Skeleton theme's grey cards and colours (AppShell applies them).
		id: 'skeleton',
		name: 'Original',
		note: "The platform's Skeleton theme, grey cards",
		light: { bg: '#FCFCFC', surface: '#FFFFFF', surface2: '#E3E3E3', border: '#C9C9C9', borderStrong: '#B0B0B0', text: '#1F1F1F', text2: '#4D4D4D', text3: '#6E6E6E' },
		dark: { bg: '#101010', surface: '#1E1E1E', surface2: '#2A2A2A', border: '#3B3B3B', borderStrong: '#555555', text: '#FAFAFA', text2: '#C8C8C8', text3: '#9A9A9A' }
	},
	{
		id: 'paper',
		accent: 'amber',
		name: 'Paper',
		note: 'Warm, like paper and ink',
		light: { bg: '#F6F5F2', surface: '#FFFFFF', surface2: '#F2F1ED', border: '#E6E3DD', borderStrong: '#D3CFC7', text: '#1D1C1A', text2: '#524E47', text3: '#6E6961' },
		dark: { bg: '#121211', surface: '#1A1A18', surface2: '#232320', border: '#2D2C29', borderStrong: '#403E3A', text: '#ECEAE5', text2: '#B7B3AB', text3: '#8F8B83' }
	},
	{
		id: 'mint',
		accent: 'teal',
		name: 'Mint',
		note: 'Teal-tinted day and night',
		light: { bg: '#F4F9F7', surface: '#FFFFFF', surface2: '#EEF5F3', border: '#DCE8E4', borderStrong: '#B9CCC7', text: '#0D1F1C', text2: '#39504B', text3: '#526863' },
		dark: { bg: '#0A1816', surface: '#0F201E', surface2: '#152A27', border: '#213734', borderStrong: '#33504B', text: '#E6F2EF', text2: '#A9C0BB', text3: '#89A19C' }
	},
	{
		id: 'slate',
		accent: 'blue',
		name: 'Slate',
		note: 'Blue-grey, deep navy at night',
		light: { bg: '#F3F5F9', surface: '#FFFFFF', surface2: '#EEF1F6', border: '#DDE2EA', borderStrong: '#C2CAD6', text: '#111827', text2: '#3F4A5A', text3: '#5D6878' },
		dark: { bg: '#0B1020', surface: '#121829', surface2: '#19213A', border: '#243049', borderStrong: '#34425F', text: '#E6EAF2', text2: '#AEB8C8', text3: '#8C98AC' }
	},
	{
		id: 'contrast',
		accent: 'graphite',
		name: 'High contrast',
		note: 'Black on white, strong lines',
		light: { bg: '#FFFFFF', surface: '#FFFFFF', surface2: '#EDEDED', border: '#6E6E6E', borderStrong: '#1A1A1A', text: '#000000', text2: '#1A1A1A', text3: '#383838' },
		dark: { bg: '#000000', surface: '#000000', surface2: '#161616', border: '#9A9A9A', borderStrong: '#E6E6E6', text: '#FFFFFF', text2: '#F0F0F0', text3: '#D0D0D0' },
		status: { light: ['#1B5E20', '#7A4A00', '#A50E0E'], dark: ['#7CE0A0', '#FFD166', '#FF8A80'] }
	},
	// Three with a character of their own beyond colour (crisp/theme-effects.css, by data-palette).
	{
		id: 'glow',
		accent: 'cyan',
		name: 'Bioluminescence',
		note: 'The deep sea at night, glowing like Vibrio',
		light: { bg: '#EEF8F9', surface: '#FFFFFF', surface2: '#E4F3F5', border: '#CDE5E9', borderStrong: '#A5CDD4', text: '#04212A', text2: '#285560', text3: '#456B75' },
		dark: { bg: '#030F16', surface: '#081A23', surface2: '#0D232E', border: '#153340', borderStrong: '#23495A', text: '#E2F7FA', text2: '#A4CCD5', text3: '#80AAB5' }
	},
	{
		id: 'gram',
		accent: 'crystal',
		name: 'Gram stain',
		note: 'Crystal violet and safranin',
		light: { bg: '#FBF7FC', surface: '#FFFFFF', surface2: '#F4EDF7', border: '#E8DDEE', borderStrong: '#CBB9D5', text: '#1C1122', text2: '#4C3B57', text3: '#695873' },
		dark: { bg: '#110916', surface: '#190F1F', surface2: '#221629', border: '#33243D', borderStrong: '#4B3757', text: '#F4EAF8', text2: '#CAB6D4', text3: '#A592AF' }
	},
	{
		id: 'agar',
		accent: 'coral',
		name: 'Agar',
		note: 'A warm plate, colonies growing',
		light: { bg: '#FAF2E1', surface: '#FFFCF5', surface2: '#F5EAD3', border: '#EADBBC', borderStrong: '#D5C095', text: '#2A1D0B', text2: '#5A4426', text3: '#735E3D' },
		dark: { bg: '#14100A', surface: '#1C170F', surface2: '#252015', border: '#3A311F', borderStrong: '#54472D', text: '#F6EDDC', text2: '#D0C1A3', text3: '#AA9B7D' }
	}
];

/** The accent nearest a generated preset's hue; the near-colourless ones take graphite. */
function accentFor(h: number, s: number): string {
	if (s <= 6) return 'graphite';
	if (h >= 160 && h < 195) return 'teal';
	if (h >= 195 && h < 245) return 'blue';
	if (h >= 245 && h < 320) return 'violet';
	if (h >= 320 || h < 20) return 'rose';
	if (h >= 20 && h < 60) return 'amber';
	return 'green';
}

/** Hand-made presets first, then the generated family in hue order. */
export const PRESETS: Preset[] = [
	...HAND_MADE,
	...GENERATED.map(([id, name, note, h, s]): Preset => ({ id, name, note, accent: accentFor(h, s), ...ramp(h, s) }))
];

/** The main palettes, first in the theme menu and in Customize; the rest are one hue each. */
export const FEATURED = ['crisp', 'glow', 'gram', 'agar', 'skeleton', 'paper', 'mint', 'slate', 'contrast'];

/** Returns the change that switches to preset `id`, dropping hand-edited page and text colours. */
export function presetChange(colours: UiPrefs['colours'], id: string): Pick<UiPrefs, 'palette' | 'colours'> & Partial<Pick<UiPrefs, 'accent'>> {
	const neutral = new Set(TOKENS.filter((t) => t.group === 'Surfaces' || t.group === 'Text').map((t) => t.key));
	const keep = (side: Record<string, string>) => Object.fromEntries(Object.entries(side).filter(([k]) => !neutral.has(k)));
	// Its own accent comes with it (highlights, links, titles); Customize can change it after.
	const accent = PRESETS.find((p) => p.id === (id || 'crisp'))?.accent;
	return { palette: id, colours: { light: keep(colours.light), dark: keep(colours.dark) }, ...(accent ? { accent } : {}) };
}

export const presetOf = (id: string, fallback: string) => PRESETS.find((p) => p.id === id) ?? PRESETS.find((p) => p.id === fallback) ?? PRESETS[0];

export interface Token {
	key: string;
	label: string;
	group: 'Surfaces' | 'Text' | 'Meaning' | 'Sections' | 'Confidence';
	/** What it colours, in a few words. */
	hint?: string;
	/** Read as text: the editor checks its contrast on the cards. */
	text?: boolean;
}

/** Where each section hue is worn, for the editor's hints. */
const SHADE_USE: Record<string, string> = {
	blue: 'Install',
	cyan: 'Analyze, genomes',
	violet: 'Workflow, file view',
	amber: 'Jobs',
	green: 'Results',
	sky: 'Files, folders',
	rose: 'Licences',
	slate: 'Settings',
	plum: 'Spare'
};

export const TOKENS: Token[] = [
	{ key: 'bg', label: 'Page', group: 'Surfaces', hint: 'behind everything' },
	{ key: 'surface', label: 'Cards', group: 'Surfaces', hint: 'blocks, tables, menus' },
	{ key: 'surface2', label: 'Wells', group: 'Surfaces', hint: 'headers, inputs, hover' },
	{ key: 'border', label: 'Lines', group: 'Surfaces', hint: 'hairlines between rows' },
	{ key: 'borderStrong', label: 'Strong lines', group: 'Surfaces', hint: 'control edges' },
	{ key: 'text', label: 'Text', group: 'Text', text: true },
	{ key: 'text2', label: 'Secondary', group: 'Text', hint: 'descriptions', text: true },
	{ key: 'text3', label: 'Quiet', group: 'Text', hint: 'notes, dates', text: true },
	{ key: 'ok', label: 'Done', group: 'Meaning', hint: 'ready, finished', text: true },
	{ key: 'warn', label: 'Attention', group: 'Meaning', hint: 'missing, check', text: true },
	{ key: 'danger', label: 'Failed', group: 'Meaning', hint: 'errors', text: true },
	...Object.keys(SHADES).map((name) => ({
		key: `sh-${name}`,
		label: name[0].toUpperCase() + name.slice(1),
		group: 'Sections' as const,
		hint: SHADE_USE[name],
		text: true
	})),
	...TIER_NAMES.map((name, i) => ({ key: `tier-${i}`, label: name[0].toUpperCase() + name.slice(1), group: 'Confidence' as const })),
	{ key: 'tier-5', label: 'No tier', group: 'Confidence' }
];

export const TOKEN_KEYS = new Set(TOKENS.map((t) => t.key));

// ---------------------------------------------------------------- checks

export interface Check {
	/** bad: fails; close: works, but only just. */
	level: 'bad' | 'close';
	/** contrast: text too faint; apart: two colours that must differ look alike. */
	kind: 'contrast' | 'apart';
	text: string;
	/** The tokens involved, so the editor can point at them. */
	keys: string[];
}

const labelOf = (key: string) => TOKENS.find((t) => t.key === key)?.label ?? key;

/**
 * Flags text under 4.5:1 (large section headings under 3:1) and colours that
 * must differ (states, tiers) but look alike with vision `v`.
 */
export function checkColours(c: Record<string, string>, v: Vision, strength: number): Check[] {
	const out: Check[] = [];
	const seen = v === 'typical' ? '' : ` with ${visionInfo(v).plain.toLowerCase()}`;
	for (const t of TOKENS) {
		if (!t.text) continue;
		const need = t.group === 'Sections' ? 3 : 4.5;
		const r = Math.min(contrast(c[t.key], c.surface), t.group === 'Text' ? contrast(c[t.key], c.surface2) : Infinity);
		if (r < need) out.push({ level: 'bad', kind: 'contrast', text: `${labelOf(t.key)} text is ${r.toFixed(1)}:1 on the cards; it needs ${need}:1.`, keys: [t.key] });
	}
	const apart = (keys: string[], what: string) => {
		for (let i = 0; i < keys.length; i++)
			for (let j = i + 1; j < keys.length; j++) {
				const d = distance(c[keys[i]], c[keys[j]], v, strength);
				if (d < CLOSE)
					out.push({
						level: d < ALIKE ? 'bad' : 'close',
						kind: 'apart',
						text: `${what} ${labelOf(keys[i])} and ${labelOf(keys[j])} ${d < ALIKE ? 'look the same' : 'are close'}${seen}.`,
						keys: [keys[i], keys[j]]
					});
			}
	};
	apart(['ok', 'warn', 'danger'], 'States');
	apart([0, 1, 2, 3, 4, 5].map((i) => `tier-${i}`), 'Tiers');
	return out;
}
