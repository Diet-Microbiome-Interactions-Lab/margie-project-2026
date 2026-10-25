/**
 * Workspace state: saved preferences (theme, layout, mode) plus unsaved UI state
 * (arrange mode, Customize drawer, notices). Preferences are debounced into
 * localStorage and the local server's file (lib/server/ui.ts); on the website, into
 * the account (LOOK_API), so each browser signed in to it shows the same look.
 */

import { authHeaders, getToken } from '$lib/auth';
import { getApiUrl } from '$lib/config';
import { HOSTED } from '$lib/hosted';
import {
	LAYOUTS,
	motionScale,
	motionVars,
	sanitizePrefs,
	styleString,
	themeVars,
	DEFAULT_PREFS,
	LOOK_KEYS,
	lookOf,
	type LayoutName,
	type PanelId,
	type UiPrefs
} from './prefs';

/**
 * Browser storage. The website's copy of the account's look has names of its own, so a look
 * kept in one browser before the account kept it is left behind.
 */
const PREFS_KEY = HOSTED ? 'margie.ui.account-prefs' : 'margie.ui.prefs';
/** The default look, also kept here for when there is no local server. */
const DEFAULT_KEY = HOSTED ? 'margie.ui.account-default' : 'margie.ui.default';
/** Local server route that keeps both on disk (lib/server/ui.ts). */
const UI_API = '/api/local/ui';
/** Hosted: no server file, so browser storage is the only copy (see lib/hosted.ts). */
const NO_SERVER = HOSTED;
/** Set once the server's copy has been read in this window. */
let fromServer = false;
/** Website: the look kept with the account (routers/auth.py), read once per window. */
const LOOK_API = '/v1/auth/look';
let fromAccount = false;

/** Reads the account's look (no body) or saves parts of it; null while nobody is signed in to the website. */
function accountLook(body?: unknown): Promise<Response> | null {
	if (!HOSTED || !getToken()) return null;
	const url = `${getApiUrl()}${LOOK_API}`;
	return body === undefined ? fetch(url, { headers: authHeaders() }) : fetch(url, { method: 'PUT', headers: authHeaders(), body: JSON.stringify(body) });
}

/** Interface the app opens with until one is picked in Customize (prefs.ts holds the pipeline GUI's). */
const FIRST_INTERFACE: UiPrefs['interface'] = 'crisp';
/**
 * Set when an interface is picked in Customize. Every save writes an interface,
 * so only a picked one overrides FIRST_INTERFACE.
 */
const CHOSEN_KEY = 'margie.ui.interface-chosen';

/** Home route of each interface; Classic is the app's own pages. */
const INTERFACE_HOME: Record<UiPrefs['interface'], string> = {
	crisp: '/',
	classic: '/'
};

export interface Toast {
	id: number;
	text: string;
	tone: 'ok' | 'error' | 'info';
}

class Ui {
	prefs = $state<UiPrefs>(sanitizePrefs({ ...DEFAULT_PREFS, interface: FIRST_INTERFACE }));
	systemDark = $state(false);
	reducedMotion = $state(false);
	editLayout = $state(false);
	drawer = $state(false);
	toasts = $state<Toast[]>([]);
	/** Whether a look has been set as the default (null: not asked yet). */
	hasDefault = $state<boolean | null>(null);

	dark = $derived(this.prefs.theme === 'dark' || (this.prefs.theme === 'system' && this.systemDark));
	guided = $derived(this.prefs.mode === 'guided');
	/** Simple mode: explanations shown on request (the Details button), for this window. */
	details = $state(false);
	/** Whether explanatory text is shown: always in Guided, on request in Simple (see Explain.svelte). */
	explain = $derived(this.prefs.mode === 'guided' || this.details);
	motion = $derived(this.reducedMotion ? 'off' : this.prefs.motion);
	/** The motion variables as a style string, for any interface's root element. */
	motionStyle = $derived(styleString(motionVars(this.motion, this.prefs.speed)));
	vars = $derived(styleString(themeVars(this.prefs, this.dark)) + '; ' + this.motionStyle);

	#pending: Partial<UiPrefs> = {};
	#timer: ReturnType<typeof setTimeout> | null = null;
	#toastId = 0;

	init(p: UiPrefs) {
		this.prefs = sanitizePrefs(p);
	}

	/** Changes preferences now and saves them a moment later (several changes, one save). */
	update(changes: Partial<UiPrefs>) {
		Object.assign(this.prefs, changes);
		Object.assign(this.#pending, changes);
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = setTimeout(() => this.flush(), 400);
	}

	async flush() {
		const prefs = this.#pending;
		this.#pending = {};
		this.#timer = null;
		if (!Object.keys(prefs).length) return;
		try {
			localStorage.setItem(PREFS_KEY, JSON.stringify(this.prefs));
		} catch {
			// Storage blocked: the server file still keeps them.
		}
		if (NO_SERVER) {
			await accountLook({ prefs: $state.snapshot(this.prefs) })?.catch(() => {
				// Unreachable: this browser's copy stands, and the next change tries again.
			});
			return;
		}
		try {
			await fetch(UI_API, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prefs: $state.snapshot(this.prefs) }) });
		} catch {
			// No local server: browser storage is all there is.
		}
	}

	/**
	 * Restores saved preferences under the default look: browser storage first,
	 * then, once per window, the copy on disk (on the website, the account's).
	 */
	restore() {
		try {
			const saved = localStorage.getItem(PREFS_KEY);
			const look = JSON.parse(localStorage.getItem(DEFAULT_KEY) ?? '{}');
			if (saved || Object.keys(look).length) {
				const prefs = saved ? JSON.parse(saved) : {};
				if (!localStorage.getItem(CHOSEN_KEY)) prefs.interface = FIRST_INTERFACE;
				this.init({ interface: FIRST_INTERFACE, ...prefs, ...lookOf(look) } as UiPrefs);
			}
		} catch {
			// Unreadable: the defaults stand.
		}
		if (NO_SERVER) return this.#fromAccount();
		if (fromServer) return;
		fromServer = true;
		fetch(UI_API)
			.then((r) => (r.ok ? r.json() : null))
			.then((d: { prefs: UiPrefs | null; default: Partial<UiPrefs> } | null) => {
				if (!d || (!d.prefs && !Object.keys(d.default ?? {}).length)) return;
				this.hasDefault = Object.keys(d.default ?? {}).length > 0;
				this.init({ ...(d.prefs ?? this.prefs), ...d.default } as UiPrefs);
				try {
					localStorage.setItem(PREFS_KEY, JSON.stringify(this.prefs));
				} catch {
					// Storage blocked: the server file has it.
				}
			})
			.catch(() => {
				// No local server: browser storage stands.
			});
	}

	/**
	 * Website, signed in: the look kept with the account, once per window. Before one is kept,
	 * this browser's look (MARGIE's own, unless changed since) becomes the account's.
	 */
	#fromAccount() {
		if (fromAccount) return;
		const asked = accountLook();
		if (!asked) return;
		fromAccount = true;
		asked
			.then((r) => (r.ok ? r.json() : null))
			.then((d: { prefs?: Partial<UiPrefs>; default?: Partial<UiPrefs> } | null) => {
				if (!d) return;
				if (!d.prefs) {
					accountLook({ prefs: $state.snapshot(this.prefs) })?.catch(() => {
						// Unreachable: the next change keeps it.
					});
					return;
				}
				const look = lookOf(d.default ?? {});
				this.hasDefault = Object.keys(look).length > 0;
				// The same look as this browser's copy changes nothing, so nothing repaints.
				const next = sanitizePrefs({ interface: FIRST_INTERFACE, ...d.prefs, ...look } as UiPrefs);
				if (JSON.stringify(next) !== JSON.stringify($state.snapshot(this.prefs))) this.prefs = next;
				try {
					localStorage.setItem(PREFS_KEY, JSON.stringify(this.prefs));
					localStorage.setItem(DEFAULT_KEY, JSON.stringify(look));
				} catch {
					// Storage blocked: the account keeps it.
				}
			})
			.catch(() => {
				// Unreachable: this browser's copy stands.
			});
	}

	/** Whether a default look is set, asked once. */
	async checkDefault() {
		if (this.hasDefault !== null) return;
		try {
			if (NO_SERVER) throw new Error('no server');
			const r = await fetch(UI_API);
			this.hasDefault = r.ok && Object.keys((await r.json()).default ?? {}).length > 0;
		} catch {
			try {
				this.hasDefault = Object.keys(JSON.parse(localStorage.getItem(DEFAULT_KEY) ?? '{}')).length > 0;
			} catch {
				this.hasDefault = false;
			}
		}
	}

	/** Keeps the current look as what MARGIE opens with. */
	async setDefault(): Promise<boolean> {
		await this.flush();
		const look = lookOf($state.snapshot(this.prefs));
		let kept = false;
		try {
			localStorage.setItem(DEFAULT_KEY, JSON.stringify(look));
			kept = true;
		} catch {
			// The file below keeps it instead.
		}
		const toAccount = accountLook({ default: look });
		if (toAccount) kept = (await toAccount.then((r) => r.ok).catch(() => false)) || kept;
		try {
			if (NO_SERVER) throw new Error('no server');
			const r = await fetch(`${UI_API}/default`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prefs: look }) });
			kept ||= r.ok;
		} catch {
			// No local server: browser storage keeps it.
		}
		this.hasDefault = kept;
		this.notify(kept ? 'Set as the default look. MARGIE opens with it from now on.' : 'Could not save the default look.', kept ? 'ok' : 'error');
		return kept;
	}

	/** Returns to the default look (the one set, or MARGIE's own when none is). */
	async resetToDefault() {
		let look: Partial<UiPrefs> = {};
		try {
			if (NO_SERVER) throw new Error('no server');
			const r = await fetch(UI_API);
			if (r.ok) look = (await r.json()).default ?? {};
		} catch {
			try {
				look = lookOf(JSON.parse(localStorage.getItem(DEFAULT_KEY) ?? '{}'));
			} catch {
				// Falls back to MARGIE's built-in defaults.
			}
		}
		this.update(Object.keys(look).length ? look : lookOf({ ...DEFAULT_PREFS, interface: FIRST_INTERFACE }));
	}

	/**
	 * Reset theme: back to MARGIE's recommended look (colours, type, sizes, layout and the reading
	 * aids as MARGIE ships them), asked first; light or dark and Simple or Guided stay as chosen. A
	 * default look kept before is cleared too, so MARGIE opens with her own.
	 */
	async resetLook() {
		if (!confirm("Reset the theme to MARGIE's recommended look? Your colours, type and layout, and any default look you kept, go back to MARGIE's own; light or dark stays as it is.")) return;
		const keep: string[] = ['interface', 'mode', 'theme'];
		this.update(Object.fromEntries(LOOK_KEYS.filter((k) => !keep.includes(k)).map((k) => [k, structuredClone(DEFAULT_PREFS[k])])) as Partial<UiPrefs>);
		this.hasDefault = false;
		try {
			localStorage.removeItem(DEFAULT_KEY);
		} catch {
			// Storage blocked: nothing kept there.
		}
		const saving = NO_SERVER
			? accountLook({ default: {} })
			: fetch(`${UI_API}/default`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prefs: {} }) });
		await saving?.catch(() => {
			// Unreachable: the next change saves the look.
		});
		this.notify("Back to MARGIE's recommended look.", 'ok');
	}

	/** The front page of the interface this browser opens with. */
	home(): string {
		return INTERFACE_HOME[this.prefs.interface] ?? INTERFACE_HOME[FIRST_INTERFACE];
	}

	/** Switches to another interface and goes to its own front page. */
	async switchInterface(value: UiPrefs['interface']) {
		try {
			localStorage.setItem(CHOSEN_KEY, '1');
		} catch {
			// Not remembered: the next visit opens the default interface.
		}
		if (value !== this.prefs.interface) {
			this.update({ interface: value, welcomed: true });
			await this.flush();
		}
		location.href = INTERFACE_HOME[value] ?? '/';
	}

	/** A duration for a Svelte transition, scaled by the motion and speed settings. */
	ms(full: number): number {
		return Math.round(full * motionScale(this.motion, this.prefs.speed));
	}

	/** Whether a collapsible section is collapsed; `closed` is how it starts. */
	isFolded(id: string, closed = false): boolean {
		if (this.prefs.folded.includes(id)) return true;
		if (this.prefs.unfolded.includes(id)) return false;
		return closed;
	}

	setFolded(id: string, folded: boolean) {
		this.update({
			folded: folded ? [...new Set([...this.prefs.folded, id])] : this.prefs.folded.filter((x) => x !== id),
			unfolded: folded ? this.prefs.unfolded.filter((x) => x !== id) : [...new Set([...this.prefs.unfolded, id])]
		});
	}

	toggleFold(id: string, closed = false) {
		this.setFolded(id, !this.isFolded(id, closed));
	}

	/** A resizable pane's saved width, or `fallback`. */
	size(id: string, fallback: number): number {
		return this.prefs.sizes[id] ?? fallback;
	}

	setSize(id: string, px: number | null) {
		const sizes = { ...this.prefs.sizes };
		if (px === null) delete sizes[id];
		else sizes[id] = Math.round(px);
		this.update({ sizes });
	}

	movePanel(id: PanelId, dir: -1 | 1, includeHidden = false) {
		const list = this.prefs.panels.map((p) => ({ ...p }));
		const i = list.findIndex((p) => p.id === id);
		let j = i + dir;
		if (!includeHidden) while (j >= 0 && j < list.length && !list[j].visible) j += dir;
		if (i < 0 || j < 0 || j >= list.length) return;
		[list[i], list[j]] = [list[j], list[i]];
		this.update({ panels: list });
	}

	toggleSpan(id: PanelId) {
		this.update({ panels: this.prefs.panels.map((p) => (p.id === id ? { ...p, span: p.span > 1 ? 1 : 2 } : { ...p })) });
	}

	togglePanel(id: PanelId) {
		this.update({ panels: this.prefs.panels.map((p) => (p.id === id ? { ...p, visible: !p.visible } : { ...p })) });
	}

	showPanel(id: PanelId) {
		if (!this.prefs.panels.find((p) => p.id === id)?.visible) this.togglePanel(id);
	}

	applyLayout(name: LayoutName) {
		this.update({ panels: LAYOUTS[name]() });
	}

	notify(text: string, tone: Toast['tone'] = 'info') {
		const id = ++this.#toastId;
		this.toasts.push({ id, text, tone });
		setTimeout(() => (this.toasts = this.toasts.filter((t) => t.id !== id)), tone === 'error' ? 7000 : 4000);
	}
}

export const ui = new Ui();
