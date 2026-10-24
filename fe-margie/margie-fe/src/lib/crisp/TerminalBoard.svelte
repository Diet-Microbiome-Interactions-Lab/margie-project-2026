<script lang="ts">
	/**
	 * The Terminal page's view of the shell on the cluster. The shell itself lives for the whole
	 * visit (terminal-session.svelte.ts): this shows it, and leaving the page only takes it off
	 * the screen, so the shell, what is running in it and its scrollback are there on return.
	 */
	import '@xterm/xterm/css/xterm.css';
	import { onMount } from 'svelte';
	import { ChevronRight, Plug, Unplug } from 'lucide-svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { terminal } from './terminal-session.svelte';

	let box = $state<HTMLElement | null>(null);
	const status = $derived(terminal.status);
	const note = $derived(terminal.note);
	const where = $derived(backend.user && backend.host ? `${backend.user}@${backend.host}` : 'your cluster account');

	/** Commands worth knowing, by what they are for; a click types `put` at the prompt. */
	const HELP: { title: string; rows: { cmd: string; put: string; what: string }[] }[] = [
		{
			title: 'Moving around',
			rows: [
				{ cmd: 'pwd', put: 'pwd', what: 'Shows the folder you are in' },
				{ cmd: 'ls -lh', put: 'ls -lh', what: "Lists the folder's files with sizes and dates" },
				{ cmd: 'cd <folder>', put: 'cd ', what: 'Goes into a folder' },
				{ cmd: 'cd ..', put: 'cd ..', what: 'Goes up one folder' },
				{ cmd: 'cd -', put: 'cd -', what: 'Goes back to the folder you were in before' },
				{ cmd: 'cd ~', put: 'cd ~', what: 'Goes to your home folder' }
			]
		},
		{
			title: 'Reading files',
			rows: [
				{ cmd: 'head -n 20 <file>', put: 'head -n 20 ', what: 'Shows the first 20 lines' },
				{ cmd: 'tail -n 20 <file>', put: 'tail -n 20 ', what: 'Shows the last 20 lines' },
				{ cmd: 'tail -f <file>', put: 'tail -f ', what: 'Follows a growing log (Ctrl+C stops)' },
				{ cmd: 'less <file>', put: 'less ', what: 'Reads a file page by page (q quits)' },
				{ cmd: 'wc -l <file>', put: 'wc -l ', what: "Counts a file's lines" },
				{ cmd: 'grep -i <text> <file>', put: 'grep -i ', what: 'Shows the lines with the text, in any case (-r searches a folder)' }
			]
		},
		{
			title: 'Files and folders',
			rows: [
				{ cmd: 'du -sh <folder>', put: 'du -sh ', what: "Shows a folder's total size" },
				{ cmd: 'mkdir -p <folder>', put: 'mkdir -p ', what: 'Makes a folder, with any above it' },
				{ cmd: 'cp <from> <to>', put: 'cp ', what: 'Copies a file (-r for a folder)' },
				{ cmd: 'mv <from> <to>', put: 'mv ', what: 'Moves or renames a file or folder' }
			]
		},
		{
			title: 'Your SLURM jobs',
			rows: [
				{ cmd: 'squeue --me', put: 'squeue --me', what: 'Your jobs, running and waiting' },
				{ cmd: 'sacct -X -S today', put: 'sacct -X -S today', what: "Today's jobs, finished ones too" },
				{ cmd: 'seff <job id>', put: 'seff ', what: "A finished job's CPU and memory use" },
				{ cmd: 'scancel <job id>', put: 'scancel ', what: 'Cancels one of your jobs' }
			]
		}
	];

	onMount(() => {
		if (!box) return;
		const watch = new ResizeObserver(() => terminal.refit());
		watch.observe(box);
		terminal.attach(box);
		return () => watch.disconnect();
	});
</script>

<details class="thelp">
	<summary><ChevronRight size={14} aria-hidden="true" />Helpful commands<span>Tab completes a name, ↑ brings back the last command, Ctrl+C stops what is running</span></summary>
	<div class="thelp-groups">
		{#each HELP as g (g.title)}
			<section>
				<h3>{g.title}</h3>
				<ul>
					{#each g.rows as r (r.cmd)}
						<li>
							<button type="button" class="mg-mono" title="Type it at the prompt" disabled={status !== 'open'} onclick={() => terminal.type(r.put)}>{r.cmd}</button>
							<span>{r.what}</span>
						</li>
					{/each}
				</ul>
			</section>
		{/each}
	</div>
	<p class="thelp-note">A click types the command at the prompt; finish it (a name in angle brackets is yours to fill in) and press Enter.</p>
</details>

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
	/* Helpful commands: folded above the terminal, the four groups two by two. */
	.thelp {
		margin-bottom: 10px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
	}
	.thelp summary {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px 10px;
		padding: 10px 14px;
		font-size: var(--mg-fs-sm);
		font-weight: 600;
		cursor: pointer;
		list-style: none;
	}
	.thelp summary::-webkit-details-marker {
		display: none;
	}
	.thelp summary :global(svg) {
		color: var(--mg-text-3);
		transition: transform 160ms ease;
	}
	.thelp[open] summary :global(svg) {
		transform: rotate(90deg);
	}
	.thelp summary span {
		font-size: var(--mg-fs-xs);
		font-weight: 400;
		color: var(--mg-text-3);
	}
	.thelp-groups {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 460px), 1fr));
		gap: 16px 28px;
		padding: 2px 14px 4px;
	}
	.thelp h3 {
		margin: 0 0 6px;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.thelp ul {
		display: flex;
		flex-direction: column;
		gap: 5px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.thelp li {
		display: grid;
		grid-template-columns: minmax(0, 11.5rem) minmax(0, 1fr);
		align-items: baseline;
		gap: 10px;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.thelp li button {
		justify-self: start;
		max-width: 100%;
		padding: 1px 6px;
		overflow: hidden;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 3%, var(--mg-surface));
		color: var(--mg-text);
		font-size: var(--mg-fs-xs);
		text-align: left;
		text-overflow: ellipsis;
		white-space: nowrap;
		cursor: pointer;
	}
	.thelp li button:hover:not(:disabled) {
		border-color: var(--mg-accent);
	}
	.thelp li button:disabled {
		cursor: default;
	}
	.thelp-note {
		margin: 10px 14px 12px;
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
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
