/**
 * Pages that open with a password (the scores page draws on a thesis under embargo). The website
 * build adds each page as /locked/<name>.bin, encrypted (AES-256-GCM, key from PBKDF2-SHA256 of the
 * password); its source and the encrypting script are kept privately. An opened page stays open
 * for this tab's visit, or until relock() locks it again.
 */

import DOMPurify from 'dompurify';

export interface LockedPage {
	/** Sanitized HTML, its figures as object URLs. */
	html: string;
	/** A page in parts (the FAQ's thesis panels, by question id), sanitized the same way. */
	sections: Record<string, string>;
}

const MAGIC = 'MARGIEL1';
const opened = new Map<string, LockedPage>();
/** Each opened page's figure URLs, released when the page is locked again. */
const figureUrls = new Map<string, string[]>();

export class LockedError extends Error {
	constructor(
		message: string,
		readonly kind: 'missing' | 'password'
	) {
		super(message);
	}
}

/** The page if it was opened earlier in this visit. */
export const alreadyOpen = (name: string): LockedPage | null => opened.get(name) ?? null;

/** Locks a page again: it asks for the password at its next opening, and its figures are released. */
export function relock(name: string) {
	opened.delete(name);
	for (const url of figureUrls.get(name) ?? []) URL.revokeObjectURL(url);
	figureUrls.delete(name);
}

/** Fetches, decrypts and returns a locked page; throws LockedError for a missing page or a wrong password. */
export async function openLocked(name: string, password: string): Promise<LockedPage> {
	const kept = opened.get(name);
	if (kept) return kept;
	const res = await fetch(`/locked/${name}.bin`, { cache: 'no-cache' });
	if (!res.ok) throw new LockedError('This copy of MARGIE does not carry this page.', 'missing');
	const buf = new Uint8Array(await res.arrayBuffer());
	if (new TextDecoder().decode(buf.slice(0, 8)) !== MAGIC) throw new LockedError('This copy of MARGIE does not carry this page.', 'missing');
	const rounds = new DataView(buf.buffer, buf.byteOffset + 8, 4).getUint32(0);
	const salt = buf.slice(12, 28);
	const iv = buf.slice(28, 40);
	const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
	const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: rounds, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
	let plain: ArrayBuffer;
	try {
		plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, buf.slice(40));
	} catch {
		throw new LockedError('That password does not open this page.', 'password');
	}
	const data = JSON.parse(new TextDecoder().decode(plain)) as { html?: string; sections?: Record<string, string>; figs: Record<string, string> };
	const urls = Object.entries(data.figs).map(([fig, b64]) => {
		const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
		return [fig, URL.createObjectURL(new Blob([bytes], { type: fig.endsWith('.webp') ? 'image/webp' : 'image/png' }))] as const;
	});
	// Sanitized with the figures still as __fig/<name> placeholders, then pointed at their object URLs.
	const clean = (html: string) => urls.reduce((out, [fig, url]) => out.replaceAll(`__fig/${fig}`, url), DOMPurify.sanitize(html, { ADD_ATTR: ['target'] }));
	const page = {
		html: clean(data.html ?? ''),
		sections: Object.fromEntries(Object.entries(data.sections ?? {}).map(([k, v]) => [k, clean(v)]))
	};
	opened.set(name, page);
	figureUrls.set(name, urls.map(([, url]) => url));
	return page;
}
