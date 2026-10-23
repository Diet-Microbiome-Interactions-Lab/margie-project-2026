<script lang="ts">
	import { ChevronRight, Copy } from 'lucide-svelte';
	import { api, type Run } from '$lib/api';
	import { ui } from '$lib/workspace/ui.svelte';

	/**
	 * The command a job ran, set out as a script to run again from a shell on the cluster:
	 * it enters the code's folder, then dane_wf with one argument to a line. MARGIE keeps it
	 * beside the job's results (run-command.sh); for an older job it is rebuilt from the
	 * job's record. Sits at the top of a dark log, folded away or open.
	 */
	let { run, foldId = 'jobs:command' }: { run: Run; foldId?: string } = $props();

	let got = $state<{ id: string; script: string; exact: boolean; file: string | null } | null>(null);
	$effect(() => {
		const id = run.id;
		if (got?.id === id) return;
		got = null;
		api<{ script: string; exact: boolean; file: string | null }>(`/runs/${encodeURIComponent(id)}/command`)
			.then((d) => {
				if (run.id === id && d?.script) got = { id, ...d };
			})
			.catch(() => {
				// Not an annotation, or a backend without the route: the one line the run carries.
			});
	});
	const script = $derived(got?.id === run.id ? got.script.trimEnd() : run.command ? `$ ${run.command}` : '');
	const shut = $derived(ui.isFolded(foldId));

	async function copy() {
		// Run from a shell, the comments are harmless; copied, they say where it came from.
		try {
			await navigator.clipboard.writeText(script.replace(/^\$ /, '') + '\n');
			ui.notify('The command is copied.', 'ok');
		} catch {
			ui.notify('Could not reach the clipboard', 'error');
		}
	}
</script>

{#if script}
	<div class="jc" class:shut>
		<div class="jc-head">
			<button type="button" class="jc-fold" aria-expanded={!shut} onclick={() => ui.toggleFold(foldId)}>
				<ChevronRight size={13} class="chev" />Command
			</button>
			{#if got && got.id === run.id}
				<span class="jc-note" title={got.exact ? got.file : 'This job ran before MARGIE kept its command, so the licence settings it ran with are not in it'}>
					{got.exact ? 'run-command.sh in its output folder' : 'rebuilt from its record'}
				</span>
			{/if}
			<span class="jc-grow"></span>
			<button type="button" class="jc-btn" title="Copy the command to run it yourself" onclick={copy}><Copy size={13} />Copy command</button>
		</div>
		{#if !shut}
			<pre class="jc-out mg-mono">{#each script.split('\n') as l, k (k)}<span class:rem={l.startsWith('#')}>{l}</span>
{/each}</pre>
		{/if}
	</div>
{/if}

<style>
	.jc {
		border-bottom: 1px solid rgba(255, 255, 255, 0.09);
	}
	.jc-head {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 5px 8px 5px calc(var(--mg-pad) - 4px);
	}
	.jc-fold {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 2px 4px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: #c9d0d6;
		font: inherit;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		cursor: pointer;
	}
	.jc-fold:hover {
		color: #fff;
	}
	.jc-fold :global(.chev) {
		transition: transform 160ms ease;
	}
	.jc-fold[aria-expanded='true'] :global(.chev) {
		transform: rotate(90deg);
	}
	.jc-note {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 11px;
		color: #8b949c;
	}
	.jc-grow {
		flex: 1;
	}
	.jc-btn {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 5px;
		height: 24px;
		padding: 0 9px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: var(--mg-r-sm);
		background: none;
		color: #c9d0d6;
		font: inherit;
		font-size: 12px;
		cursor: pointer;
	}
	.jc-btn:hover {
		border-color: rgba(255, 255, 255, 0.3);
		color: #fff;
	}
	.jc-out {
		max-height: 230px;
		margin: 0;
		padding: 2px var(--mg-pad) 10px;
		overflow: auto;
		font-size: 11.5px;
		line-height: 1.55;
		white-space: pre;
		color: color-mix(in srgb, var(--mg-accent) 55%, #fff);
	}
	.jc-out .rem {
		color: #7d868e;
	}
	:global([data-motion='off']) .jc * {
		transition: none !important;
	}
</style>
