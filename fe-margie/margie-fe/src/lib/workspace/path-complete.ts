/**
 * Tab completion for path fields, as in a terminal: Tab fills in the folder (or file) the
 * typed start names; with several, it fills in what they share and lists them under the
 * field, where Tab or the arrow keys move, Enter or a click picks, and Escape closes.
 *
 *   <input use:pathComplete />                 folders and files
 *   <input use:pathComplete={{ dirs: true }} /> folders only
 *
 * The field's own input event fires on every change, so bind:value follows.
 */

import { api } from '$lib/api';

interface Entry {
	name: string;
	type: 'file' | 'directory';
}

/** The folder part and the name being typed: "/a/b/ge" -> ["/a/b/", "ge"]. */
export function splitPath(typed: string): [string, string] {
	const at = typed.lastIndexOf('/');
	return at < 0 ? ['', typed] : [typed.slice(0, at + 1), typed.slice(at + 1)];
}

/** The longest start every name shares. */
export function sharedStart(names: string[]): string {
	if (!names.length) return '';
	let out = names[0];
	for (const n of names.slice(1)) {
		let i = 0;
		while (i < out.length && i < n.length && out[i] === n[i]) i++;
		out = out.slice(0, i);
	}
	return out;
}

export function pathComplete(node: HTMLInputElement, opts: { dirs?: boolean } = {}) {
	let dirsOnly = !!opts.dirs;
	let list: HTMLDivElement | null = null;
	let options: string[] = [];
	let at = -1;
	let asking = 0;

	const set = (value: string) => {
		node.value = value;
		node.dispatchEvent(new Event('input', { bubbles: true }));
		node.setSelectionRange(value.length, value.length);
	};
	const close = () => {
		list?.remove();
		list = null;
		options = [];
		at = -1;
	};
	const highlight = (i: number) => {
		at = (i + options.length) % options.length;
		list?.querySelectorAll('button').forEach((b, k) => b.toggleAttribute('aria-selected', k === at));
		list?.querySelectorAll('button')[at]?.scrollIntoView({ block: 'nearest' });
	};
	const choose = (path: string) => {
		close();
		set(path);
		node.focus();
	};

	function show(paths: string[]) {
		close();
		options = paths;
		list = document.createElement('div');
		list.className = 'mg-complete';
		list.setAttribute('role', 'listbox');
		const r = node.getBoundingClientRect();
		Object.assign(list.style, { left: `${r.left}px`, top: `${r.bottom + 4}px`, minWidth: `${Math.min(r.width, 420)}px` });
		for (const p of paths) {
			const b = document.createElement('button');
			b.type = 'button';
			b.setAttribute('role', 'option');
			b.textContent = splitPath(p.endsWith('/') ? p.slice(0, -1) : p)[1] + (p.endsWith('/') ? '/' : '');
			b.title = p;
			// Picked before the field loses focus.
			b.addEventListener('mousedown', (e) => {
				e.preventDefault();
				choose(p);
			});
			list.append(b);
		}
		(node.closest('[data-mg-root]') ?? document.body).append(list);
	}

	async function complete() {
		const typed = node.value;
		const [dir, start] = splitPath(typed);
		if (!dir) return;
		const ask = ++asking;
		let entries: Entry[];
		try {
			entries = (await api<{ entries: Entry[] }>(`/files?path=${encodeURIComponent(dir)}`)).entries;
		} catch {
			return;
		}
		// Typed on meanwhile, or another Tab already answered.
		if (ask !== asking || node.value !== typed) return;
		const hits = entries
			.filter((e) => (!dirsOnly || e.type === 'directory') && e.name.startsWith(start) && (start.startsWith('.') || !e.name.startsWith('.')))
			.sort((a, b) => a.name.localeCompare(b.name));
		if (!hits.length) return;
		const full = (e: Entry) => dir + e.name + (e.type === 'directory' ? '/' : '');
		if (hits.length === 1) return set(full(hits[0]));
		const shared = sharedStart(hits.map((e) => e.name));
		if (shared.length > start.length) set(dir + shared);
		show(hits.slice(0, 200).map(full));
	}

	function onkeydown(e: KeyboardEvent) {
		if (list && options.length) {
			if (e.key === 'Tab' || e.key === 'ArrowDown') {
				e.preventDefault();
				return highlight(e.shiftKey && e.key === 'Tab' ? at - 1 : at + 1);
			}
			if (e.key === 'ArrowUp') {
				e.preventDefault();
				return highlight(at - 1);
			}
			if (e.key === 'Enter' && at >= 0) {
				e.preventDefault();
				e.stopPropagation();
				return choose(options[at]);
			}
			if (e.key === 'Escape') {
				e.preventDefault();
				e.stopPropagation();
				return close();
			}
		}
		if (e.key === 'Tab' && !e.shiftKey && !e.altKey && !e.metaKey && !e.ctrlKey && /^[/~]/.test(node.value)) {
			e.preventDefault();
			complete();
		}
	}
	const oninput = (e: Event) => {
		// Typing (not a completion) closes the list.
		if (e.isTrusted) close();
	};

	node.addEventListener('keydown', onkeydown);
	node.addEventListener('input', oninput);
	node.addEventListener('blur', close);
	return {
		update(next: { dirs?: boolean } = {}) {
			dirsOnly = !!next.dirs;
		},
		destroy() {
			close();
			node.removeEventListener('keydown', onkeydown);
			node.removeEventListener('input', oninput);
			node.removeEventListener('blur', close);
		}
	};
}
