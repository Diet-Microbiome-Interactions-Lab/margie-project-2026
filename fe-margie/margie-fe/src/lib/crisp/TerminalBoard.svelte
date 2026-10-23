<script lang="ts">
	/**
	 * A shell on the cluster, as the signed-in account: xterm.js in the page, relayed by
	 * MARGIE's API over a WebSocket (/v1/ssh/terminal, api/routers/terminal.py). The
	 * sign-in token goes in the first message, never in the URL.
	 */
	import '@xterm/xterm/css/xterm.css';
	import { onMount } from 'svelte';
	import { Plug, Unplug } from 'lucide-svelte';
	import { getToken } from '$lib/auth';
	import { getApiUrl } from '$lib/config';
	import { backend } from '$lib/workspace/backend.svelte';

	type XTerm = import('@xterm/xterm').Terminal;
	type Fit = import('@xterm/addon-fit').FitAddon;

	let box = $state<HTMLElement | null>(null);
	let status = $state<'idle' | 'connecting' | 'open' | 'closed'>('idle');
	let note = $state('');
	let term: XTerm | null = null;
	let fit: Fit | null = null;
	let sock: WebSocket | null = null;

	const where = $derived(backend.user && backend.host ? `${backend.user}@${backend.host}` : 'your cluster account');
	const say = (s: string) => term?.write(s);

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

	function connect() {
		if (!term) return;
		sock?.close();
		note = '';
		status = 'connecting';
		term.reset();
		say('\x1b[2mSigning in to the cluster…\x1b[0m\r\n');
		const s = new WebSocket(socketUrl());
		s.binaryType = 'arraybuffer';
		sock = s;
		let opened = false;
		s.onopen = () => {
			opened = true;
			s.send(JSON.stringify({ token: getToken() ?? '', cols: term?.cols ?? 120, rows: term?.rows ?? 32 }));
		};
		s.onmessage = (e) => {
			if (typeof e.data === 'string') {
				try {
					const m = JSON.parse(e.data) as { type: string; message?: string };
					if (m.type === 'error' && m.message) {
						note = m.message;
						say(`\r\n\x1b[31m${m.message}\x1b[0m\r\n`);
					}
				} catch {
					// Not a control message: nothing to show.
				}
				return;
			}
			if (status !== 'open') status = 'open';
			term?.write(new Uint8Array(e.data as ArrayBuffer));
		};
		s.onclose = async () => {
			if (sock !== s) return;
			status = 'closed';
			if (!opened) {
				const why = await whyNoSocket();
				if (sock !== s) return;
				note = why;
				say(`\r\n\x1b[31m${why}\x1b[0m\r\n`);
				return;
			}
			say('\r\n\x1b[2m[the shell has closed: Reconnect opens a new one]\x1b[0m\r\n');
		};
	}

	function disconnect() {
		sock?.close();
	}

	onMount(() => {
		let gone = false;
		let watch: ResizeObserver | null = null;
		(async () => {
			const [{ Terminal }, { FitAddon }] = await Promise.all([import('@xterm/xterm'), import('@xterm/addon-fit')]);
			if (gone || !box) return;
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
			t.open(box);
			f.fit();
			term = t;
			fit = f;
			t.onData((data) => {
				if (sock?.readyState === WebSocket.OPEN) sock.send(JSON.stringify({ type: 'input', data }));
			});
			t.onResize(({ cols, rows }) => {
				if (sock?.readyState === WebSocket.OPEN) sock.send(JSON.stringify({ type: 'resize', cols, rows }));
			});
			watch = new ResizeObserver(() => {
				try {
					fit?.fit();
				} catch {
					// Hidden or zero-sized for a moment: the next resize fits it.
				}
			});
			watch.observe(box);
			connect();
			t.focus();
		})();
		return () => {
			gone = true;
			watch?.disconnect();
			sock?.close();
			sock = null;
			term?.dispose();
			term = null;
		};
	});
</script>

<section class="termcard" aria-label="Terminal on the cluster">
	<header class="tbar">
		<span class="led {status}" aria-hidden="true"></span>
		<span class="tstate">
			{status === 'open' ? `Connected as ${where}` : status === 'connecting' ? 'Connecting…' : status === 'closed' ? 'Disconnected' : 'Starting…'}
		</span>
		{#if note}<span class="tnote" title={note}>{note}</span>{/if}
		<span class="mg-grow"></span>
		{#if status === 'open' || status === 'connecting'}
			<button type="button" class="mg-btn small" onclick={disconnect}><Unplug size={14} />Disconnect</button>
		{:else}
			<button type="button" class="mg-btn small primary" onclick={connect}><Plug size={14} />Reconnect</button>
		{/if}
	</header>
	<div class="screen" bind:this={box}></div>
</section>

<style>
	.termcard {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: #14171b;
	}
	.tbar {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 46px;
		padding: 6px 10px 6px 14px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.09);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
	}
	.led {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--mg-border-strong);
	}
	.led.open {
		background: var(--mg-ok, #2e9d5b);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-ok, #2e9d5b) 22%, transparent);
	}
	.led.connecting {
		background: var(--mg-accent);
	}
	.tstate {
		font-weight: 500;
		white-space: nowrap;
	}
	.tnote {
		overflow: hidden;
		color: var(--mg-danger, #c0392b);
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	/* The padding sits on the terminal itself: the fit addon subtracts the terminal's own padding,
	   not its box's, so padding here would size one row too many and hide the last line. */
	.screen {
		flex: 1 1 auto;
		height: max(380px, calc(100vh - 260px));
		min-height: 0;
		overflow: hidden;
	}
	.screen :global(.xterm) {
		height: 100%;
		padding: 8px 6px 8px 10px;
	}
</style>
