<script lang="ts">
	/**
	 * The Terminal page's view of the shell on the cluster. The shell itself lives for the whole
	 * visit (terminal-session.svelte.ts): this shows it, and leaving the page only takes it off
	 * the screen, so the shell, what is running in it and its scrollback are there on return.
	 */
	import '@xterm/xterm/css/xterm.css';
	import { onMount } from 'svelte';
	import { Plug, Unplug } from 'lucide-svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { terminal } from './terminal-session.svelte';

	let box = $state<HTMLElement | null>(null);
	const status = $derived(terminal.status);
	const note = $derived(terminal.note);
	const where = $derived(backend.user && backend.host ? `${backend.user}@${backend.host}` : 'your cluster account');

	onMount(() => {
		if (!box) return;
		const watch = new ResizeObserver(() => terminal.refit());
		watch.observe(box);
		terminal.attach(box);
		return () => watch.disconnect();
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
			<button type="button" class="mg-btn small" onclick={() => terminal.disconnect()}><Unplug size={14} />Disconnect</button>
		{:else}
			<button type="button" class="mg-btn small primary" onclick={() => terminal.connect()}><Plug size={14} />Reconnect</button>
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
