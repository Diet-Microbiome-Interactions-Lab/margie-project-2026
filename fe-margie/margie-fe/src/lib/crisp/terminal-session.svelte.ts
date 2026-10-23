/**
 * The shell on the cluster, kept for the whole visit: xterm.js and its WebSocket to MARGIE's API
 * (/v1/ssh/terminal, api/routers/terminal.py) live here rather than in the Terminal page, so
 * leaving the page and coming back finds the same shell, scrollback and all. It ends with
 * Disconnect, or when the browser closes the site (the socket closes with the page). A ping
 * every 30 s keeps the server and the proxy in front of it from closing an idle shell.
 * The sign-in token goes in the first message, never in the URL.
 */
import { getToken } from '$lib/auth';
import { getApiUrl } from '$lib/config';

type XTerm = import('@xterm/xterm').Terminal;
type Fit = import('@xterm/addon-fit').FitAddon;

const PING_MS = 30_000;

class TerminalSession {
	status = $state<'idle' | 'connecting' | 'open' | 'closed'>('idle');
	note = $state('');
	#term: XTerm | null = null;
	#fit: Fit | null = null;
	#sock: WebSocket | null = null;
	#ping: ReturnType<typeof setInterval> | null = null;
	#starting: Promise<XTerm> | null = null;

	/** Shows the terminal in `box`, made the first time and moved there after; opens a shell if none is open. */
	async attach(box: HTMLElement): Promise<void> {
		const term = await this.#make();
		if (term.element) box.appendChild(term.element);
		else term.open(box);
		this.refit();
		if (this.status === 'idle') this.connect();
		term.focus();
	}

	/** Fits the terminal to its box (after a resize, or when it is shown again). */
	refit(): void {
		try {
			this.#fit?.fit();
		} catch {
			// Hidden or zero-sized for a moment: the next resize fits it.
		}
	}

	connect(): void {
		const term = this.#term;
		if (!term) return;
		this.#close();
		this.note = '';
		this.status = 'connecting';
		term.reset();
		term.write('\x1b[2mSigning in to the cluster…\x1b[0m\r\n');
		const s = new WebSocket(socketUrl());
		s.binaryType = 'arraybuffer';
		this.#sock = s;
		let opened = false;
		s.onopen = () => {
			opened = true;
			s.send(JSON.stringify({ token: getToken() ?? '', cols: term.cols, rows: term.rows }));
			this.#ping = setInterval(() => s.readyState === WebSocket.OPEN && s.send('{"type":"ping"}'), PING_MS);
		};
		s.onmessage = (e) => {
			if (typeof e.data === 'string') {
				try {
					const m = JSON.parse(e.data) as { type: string; message?: string };
					if (m.type === 'error' && m.message) {
						this.note = m.message;
						term.write(`\r\n\x1b[31m${m.message}\x1b[0m\r\n`);
					}
				} catch {
					// Not a control message: nothing to show.
				}
				return;
			}
			if (this.status !== 'open') this.status = 'open';
			term.write(new Uint8Array(e.data as ArrayBuffer));
		};
		s.onclose = async () => {
			if (this.#sock !== s) return;
			this.#stopPing();
			this.status = 'closed';
			if (!opened) {
				const why = await whyNoSocket();
				if (this.#sock !== s) return;
				this.note = why;
				term.write(`\r\n\x1b[31m${why}\x1b[0m\r\n`);
				return;
			}
			term.write('\r\n\x1b[2m[the shell has closed: Reconnect opens a new one]\x1b[0m\r\n');
		};
	}

	disconnect(): void {
		this.#sock?.close();
	}

	async #make(): Promise<XTerm> {
		if (this.#term) return this.#term;
		this.#starting ??= (async () => {
			const [{ Terminal }, { FitAddon }] = await Promise.all([import('@xterm/xterm'), import('@xterm/addon-fit')]);
			const t = new Terminal({
				cursorBlink: true,
				fontFamily: 'Menlo, ui-monospace, SFMono-Regular, Consolas, monospace',
				fontSize: 13,
				lineHeight: 1.15,
				scrollback: 10000,
				macOptionIsMeta: true,
				theme: { background: '#14171b', foreground: '#e4e8ec', cursor: '#e4e8ec', selectionBackground: '#3a4655' }
			});
			const f = new FitAddon();
			t.loadAddon(f);
			t.onData((data) => {
				if (this.#sock?.readyState === WebSocket.OPEN) this.#sock.send(JSON.stringify({ type: 'input', data }));
			});
			t.onResize(({ cols, rows }) => {
				if (this.#sock?.readyState === WebSocket.OPEN) this.#sock.send(JSON.stringify({ type: 'resize', cols, rows }));
			});
			this.#term = t;
			this.#fit = f;
			return t;
		})();
		return this.#starting;
	}

	#close(): void {
		this.#stopPing();
		const s = this.#sock;
		this.#sock = null;
		s?.close();
	}

	#stopPing(): void {
		if (this.#ping) clearInterval(this.#ping);
		this.#ping = null;
	}
}

/** The API's WebSocket address: same origin when hosted, else the configured API. */
function socketUrl(): string {
	const u = new URL('/v1/ssh/terminal', getApiUrl() || location.origin);
	u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
	return u.toString();
}

/**
 * Why a terminal never opened. A browser hides the reason, so this asks the API's /health:
 * an API that answers there but refused the terminal is a backend without this route.
 */
async function whyNoSocket(): Promise<string> {
	const api = getApiUrl() || location.origin;
	try {
		const r = await fetch(new URL('/health', api), { signal: AbortSignal.timeout(5000) });
		if (r.ok) return `MARGIE's API at ${api} is running but has no terminal: it is an older backend. The terminal needs the be-margie API.`;
	} catch {
		// Unreachable: said below.
	}
	return `MARGIE's API at ${api} did not answer.`;
}

export const terminal = new TerminalSession();
