<script lang="ts">
	import { genomeList } from '$lib/crisp/genomes';
	import AnalyzeBoard from '$lib/crisp/AnalyzeBoard.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';

	/**
	 * Analyze page: genome selection, run setup and the start button, with a status line under the
	 * title and Atlas's evidence grid while a run goes.
	 */
	const n = $derived(ws.genomes.length);
	const account = $derived(ws.setting('compute.cluster_default.account'));
	const genomes = $derived(genomeList());
	const waiting = $derived(genomes.filter((g) => g.file && g.state !== 'done'));
	const done = $derived(genomes.filter((g) => g.state === 'done'));
	const plural = (count: number, one: string, many = one + 's') => `${count} ${count === 1 ? one : many}`;
	/* True unless a required item is known to be missing (rows still being checked do not count). */
	const setupOk = $derived(!ws.setup.some((r) => r.required && (r.tone === 'warn' || r.tone === 'danger')));

	/** Status line and the next action, if any. */
	const status = $derived.by((): { text: string; action?: { label: string; href: string } } => {
		const p = ws.progress;
		// Only the genomes are waited for; the jobs and the rest fill in as they come.
		if (!ws.genomesRead && !ws.loaded) return { text: 'Reading your genomes…' };
		if (ws.active && p)
			return {
				text: `Annotating${p.current ? ` ${p.current}` : ''}: ${p.stage.toLowerCase()}, ${p.genomes.filter((g) => g.state === 'done').length} of ${p.genomes.length} genomes done.`,
				action: { label: 'View log', href: `/jobs/${ws.active.id}` }
			};
		if (ws.active) return { text: `${ws.active.label.replace(/ with .*$/, '')}.`, action: { label: 'View log', href: `/jobs/${ws.active.id}` } };
		if (!n) return { text: 'No genomes yet. Add FASTA files to start.', action: { label: 'Add genomes', href: '#genomes' } };
		if (waiting.length && !setupOk)
			return {
				text: `${plural(waiting.length, 'genome')} waiting. Install is not complete (${ws.setupReady.ok} of ${ws.setupReady.total}).`,
				action: { label: 'Go to Install', href: '/install' }
			};
		if (waiting.length) return { text: `${plural(waiting.length, 'genome')} ready to annotate.` };
		return { text: `All ${plural(done.length, 'genome')} annotated.`, action: { label: 'Open Results', href: '/results' } };
	});

	/** Evidence-grid columns: the running run's tools (all when it names none), else the chosen ones. */
	const runTools = $derived.by(() => {
		const args = ws.active?.args ?? [];
		const named = args.flatMap((a, i) => (args[i - 1] === '--tool' ? [a] : []));
		const list = named.length
			? named
			: ws.active?.tools?.length
				? ws.active.tools
				: !ws.active && ws.chosenTools.length
					? ws.chosenTools
					: ws.tools.map((t) => t.name);
		return ['operon', ...list.filter((t) => t !== 'operon')];
	});
</script>

<svelte:head><title>Analyze | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-analyze">
	<header class="cr-head">
		<h1 class="cr-title">Analyze</h1>
	</header>

	<!-- Where things stand, on one thin line: for reading only. -->
	<p class="an-status" role="status">
		<span class="an-dot" class:going={!!ws.active} aria-hidden="true"></span>
		<span class="an-text">{status.text}</span>
		{#if status.action}<a class="mg-link" href={status.action.href}>{status.action.label}</a>{/if}
		<span class="mg-grow"></span>
		{#if done.length && waiting.length}<span class="an-meta">{done.length} annotated</span>{/if}
		{#if backend.cluster && backend.user}
			<span class="an-meta">runs as <b class="mg-mono">{backend.user}@{backend.host.split('.')[0]}</b>{account ? `, account ${account}` : ''}</span>
		{/if}
	</p>

	<AnalyzeBoard tools={runTools} />
</div>

<style>
	.an-status {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 12px;
		margin: -4px 0 0;
		padding: 0 2px;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.an-dot {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--mg-ok);
	}
	.an-dot.going {
		background: var(--mg-accent);
		animation: an-pulse 1.6s ease-in-out infinite;
	}
	@keyframes an-pulse {
		50% {
			opacity: 0.35;
		}
	}
	.an-text {
		color: var(--mg-text);
	}
	.an-meta {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.an-meta b {
		font-weight: 500;
		color: var(--mg-text-2);
	}
	:global([data-motion='off']) .an-dot {
		animation: none;
	}
</style>
