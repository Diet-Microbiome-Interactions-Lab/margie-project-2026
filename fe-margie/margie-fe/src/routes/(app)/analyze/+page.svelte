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

	/** Before a run, a short checklist: genomes, tools, then only what still needs doing. */
	type Check = { ok: boolean; text: string; href?: string; info?: boolean };
	const checklist = $derived.by((): Check[] => {
		const tools = ws.chosenTools.length;
		const items: Check[] = [
			{ ok: n > 0, text: n ? plural(n, 'genome') : 'Add genomes', href: '#genomes' },
			{ ok: true, text: tools ? plural(tools, 'tool') : 'Gene calling only', href: '#tools' }
		];
		// The licence terms have their own step on this page, so they are not repeated here.
		const todo = ws.setup.filter((r) => r.required && r.id !== 'terms' && (r.tone === 'warn' || r.tone === 'danger'));
		for (const r of todo) items.push({ ok: false, text: `${r.label}: ${r.value.toLowerCase()}`, href: r.id === 'terms' ? '#licence' : r.href });
		if (!todo.length && ws.setup.length) items.push({ ok: true, text: backend.cluster ? 'Cluster ready' : 'Ready', href: '/install' });
		if (backend.cluster && ws.stores && !ws.stores.ready) {
			// Copies already put in the working folder are used as they are; the rest are copied once.
			const own = ws.stores.stores.some((x) => !x.version && x.found?.ready);
			items.push({ ok: true, info: true, text: own ? 'First run uses your own copies and copies the rest' : 'First run copies your databases', href: '/install#databases' });
		}
		return items;
	});
</script>

<svelte:head><title>Analyze | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-analyze">
	<header class="cr-head">
		<h1 class="cr-title">Analyze</h1>
		{#if backend.cluster && backend.user}
			<span class="cr-meta">runs as <b class="mg-mono">{backend.user}@{backend.host.split('.')[0]}</b>{account ? `, account ${account}` : ''}</span>
		{/if}
	</header>

	<!-- While a run goes: where it is. Otherwise: a short checklist, with only what still needs doing. -->
	{#if ws.active || !ws.genomesRead}
		<p class="an-status" role="status">
			<span class="an-dot" class:going={!!ws.active} aria-hidden="true"></span>
			<span class="an-text">{status.text}</span>
			{#if status.action}<a class="mg-link" href={status.action.href}>{status.action.label}</a>{/if}
		</p>
	{:else}
		<ul class="an-check" aria-label="Before a run">
			{#each checklist as c (c.text)}
				<li class:ok={c.ok && !c.info} class:todo={!c.ok} class:info={c.info}>
					<span class="an-mark" aria-hidden="true">{c.info ? 'i' : c.ok ? '✓' : '!'}</span>
					{#if c.href}<a href={c.href}>{c.text}</a>{:else}{c.text}{/if}
				</li>
			{/each}
		</ul>
	{/if}

	<AnalyzeBoard />
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
	/* The checklist: one row of small items, green when done, amber when it needs doing. */
	.an-check {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 8px;
		margin: -4px 0 0;
		padding: 0;
		list-style: none;
		font-size: var(--mg-fs-sm);
	}
	.an-check li {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 3px 10px 3px 4px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--mg-text) 5%, transparent);
	}
	.an-check a {
		color: inherit;
		text-decoration: none;
	}
	.an-check a:hover {
		text-decoration: underline;
	}
	.an-mark {
		display: grid;
		place-items: center;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		font-size: 11px;
		font-weight: 700;
		color: var(--mg-on-accent, #fff);
		background: var(--mg-text-3);
	}
	.an-check li.ok .an-mark {
		background: var(--mg-ok);
	}
	.an-check li.todo {
		background: color-mix(in srgb, var(--mg-warn) 12%, transparent);
	}
	.an-check li.todo .an-mark {
		background: var(--mg-warn);
	}
	.an-check li.info .an-mark {
		background: var(--mg-accent);
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
	:global([data-motion='off']) .an-dot {
		animation: none;
	}
</style>
