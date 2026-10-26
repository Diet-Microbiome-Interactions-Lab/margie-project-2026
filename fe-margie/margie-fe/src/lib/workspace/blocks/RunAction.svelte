<script lang="ts">
	import { uiBase } from '../base.svelte';
	import { backend } from '../backend.svelte';
	import { ws } from '../data.svelte';
	import { ui } from '../ui.svelte';
	import ProgressBar from '../ProgressBar.svelte';
	import { ArrowRight, CircleAlert, Database, Lock } from 'lucide-svelte';
	import { onMount } from 'svelte';
	import Switch from '../Switch.svelte';
	import { runEmails } from '../run-emails.svelte';

	/**
	 * Start button with a sentence on what it will do; when blocked, it is replaced by the
	 * first blocker and its fix.
	 */

	const runtimeReady = $derived(ws.overview?.runtime.ready ?? true);
	const n = $derived(ws.genomes.length);
	const tools = $derived(ws.chosenTools.length);
	const plural = (count: number, one: string, many = one + 's') => `${count} ${count === 1 ? one : many}`;

	/** The first blocker and its fix. */
	const blocker = $derived.by((): { text: string; fix?: { label: string; run: () => void }; href?: string } | null => {
		if (!n) return { text: backend.cluster ? 'No genomes in the input folder on the cluster yet.' : 'No genomes to annotate yet.', href: '#genomes' };
		if (!ws.tools.length) return { text: 'Still reading which tools are available.' };
		if (!runtimeReady) return { text: backend.cluster ? 'The cluster cannot be reached.' : 'The container app is not running.', href: uiBase.to('/install') };
		// Backend-reported rows (cluster): the first not ready, and where to fix it.
		const unready = ws.setup.find((r) => r.required && r.tone !== 'ok' && r.href);
		// The licence terms are accepted on Analyze itself, just above.
		if (unready) return { text: `${unready.label}: ${unready.value.toLowerCase()}.`, href: unready.id === 'terms' ? '#licence' : uiBase.to(unready.href as string) };
		const need = [...new Set([...ws.needs.images, ...ws.needs.databases])];
		if (need.length && backend.cluster) {
			// Cluster tools are installed by its administrators; this only points there.
			return {
				text: `${plural(need.length, 'tool')} not where the cluster config points: ${need.slice(0, 3).join(', ')}${need.length > 3 ? '…' : ''}`,
				href: uiBase.to('/install#installed')
			};
		}
		if (need.length) {
			return {
				text: `${plural(need.length, 'tool')} still to install: ${need.slice(0, 3).join(', ')}${need.length > 3 ? '…' : ''}`,
				fix: { label: 'Install them', run: () => ws.build('all', need) }
			};
		}
		return null;
	});

	/** What the button will do. */
	const sentence = $derived(
		(tools ? `Annotate ${plural(n, 'genome')} with ${plural(tools, 'tool')}` : `Call genes on ${plural(n, 'genome')}`) +
			(ws.noCache ? ', without the cache' : '')
	);
	const outputDir = $derived(ws.resultRoots.outputRoot.split('/').filter(Boolean).at(-1) ?? 'output');
	const onCluster = $derived(backend.cluster ? ' on the cluster' : '');
	/** Runs going now: this one starts beside them, in a folder of its own. */
	const going = $derived(ws.running.filter((r) => r.kind === 'annotate').length);
	const under = $derived(
		tools
			? `the gene caller first, then the annotation tools | results to ${outputDir}/${onCluster}`
			: `no annotation tools chosen | gene calls to ${outputDir}/${onCluster}`
	);

	let starting = $state(false);
	/** Asking before the next run skips the cache. */
	let askingCache = $state(false);
	/** True while the user's databases are still being copied. */
	const copying = $derived(ws.storesBusy && !ws.storesOp?.op?.startsWith('backup:'));

	// The emails about runs are the cluster website's (services/run_mail.py), switched as on the User profile.
	onMount(() => {
		if (backend.cluster && !runEmails.loaded) runEmails.load();
	});

	async function start() {
		starting = true;
		const run = await ws.annotate();
		starting = false;
		if (run) ui.notify('Started', 'ok');
	}
</script>

<!-- First cluster run copies the databases to scratch; the run starts when done (ws.start, #watchStores). -->
{#if ws.storesOp && (ws.storesBusy || ws.storesOp.state === 'failed') && !ws.storesOp.op?.startsWith('backup:')}
	<div class="stores-setup">
		<ProgressBar
			percent={ws.storesOp.percent}
			state={ws.storesOp.state}
			label={ws.storesOp.state === 'queued'
				? 'Setting up your databases: waiting for a SLURM slot'
				: `Setting up your databases${ws.storesOp.label && !['Starting', 'Finished'].includes(ws.storesOp.label) ? `: ${ws.storesOp.label}` : ''}`}
			detail={ws.storesOp.state === 'failed'
				? ws.storesOp.message || 'The copy did not finish.'
				: 'A one-time copy of the base databases to your databases folder. The run starts by itself when it finishes.'}
			log={[...(ws.storesOp.log ?? []), ...(ws.storesOp.slurm_out ?? [])]}
			onstop={() => ws.stopStores()}
		/>
	</div>
{/if}
{#if going && !blocker}
	<p class="also mg-note">{going === 1 ? 'A run is going' : `${going} runs are going`}; this starts another beside it, with its own results folder.</p>
{/if}
<button type="button" class="go mg-btn primary" disabled={!!blocker || starting || copying} onclick={start}>
	{starting ? 'Starting…' : copying ? 'Starts when your databases are ready' : sentence}
</button>
{#if blocker}
	<div class="blocked" role="status">
		<span class="b-icon" aria-hidden="true"><CircleAlert size={15} strokeWidth={2.3} /></span>
		<p>{blocker.text}</p>
		{#if blocker.fix}
			<button type="button" class="b-fix" onclick={blocker.fix.run}>{blocker.fix.label}</button>
		{:else if blocker.href}
			<!-- The licence step on Analyze opens when it is the way there. -->
			<a class="b-fix" href={blocker.href} onclick={() => blocker?.href === '#licence' && ui.setFolded('analyze:licence', false)}>Take me there <ArrowRight size={14} /></a>
		{/if}
	</div>
{:else}
	<p class="under mg-note">{under}</p>
{/if}
{#if backend.cluster}
	<!-- MARGIE's cache, on by default; skipping it for the next run is unlocked after a yes. -->
	<div class="cache" class:off={ws.noCache}>
		<span class="c-ic" aria-hidden="true"><Database size={15} /></span>
		<span class="c-text">
			{#if ws.noCache}
				<b>The next run does not use the cache</b>
				<small>Each tool runs on each genome and keeps its raw output in original_container_outputs. Its results still go into the cache.</small>
			{:else}
				<b>MARGIE's cache: on (recommended)</b>
				<small>Genomes and proteins annotated before come back from MARGIE's database, with their processed tables; those tools do not run again.</small>
			{/if}
		</span>
		{#if ws.noCache}
			<button type="button" class="mg-link quiet" onclick={() => (ws.noCache = false)}>Use the cache again</button>
		{:else if !askingCache}
			<button type="button" class="mg-btn small" onclick={() => (askingCache = true)}><Lock size={13} /> Run without the cache</button>
		{/if}
	</div>
	{#if askingCache && !ws.noCache}
		<div class="cache-ask" role="alertdialog" aria-labelledby="cache-ask-t">
			<b id="cache-ask-t">Run the next run without the cache?</b>
			<ul>
				<li>Each tool runs on each genome, including genomes and proteins annotated before, and keeps the container's raw output.</li>
				<li>The run takes longer and uses more of your SLURM time.</li>
				<li>Its results still go into MARGIE's database and the cache, as in other runs.</li>
				<li>This is for the next run only; the runs after it use the cache again.</li>
			</ul>
			<div class="cache-go">
				<button type="button" class="mg-btn small primary" onclick={() => ((ws.noCache = true), (askingCache = false))}>Yes, without the cache</button>
				<button type="button" class="mg-link quiet" onclick={() => (askingCache = false)}>Keep the cache</button>
			</div>
		</div>
	{/if}
	<div class="mail">
		<Switch label="Email me about my runs" checked={runEmails.on && !!runEmails.to} disabled={!runEmails.loaded || !runEmails.to} onchange={(on) => runEmails.set(on)} />
		<span>
			<b>Email me about my runs</b>
			{#if !runEmails.loaded}
				<small>when a run completes, fails, or has been pending for more than an hour</small>
			{:else if runEmails.to}
				<small>when a run completes, fails, or has been pending for more than an hour; to {runEmails.to}</small>
			{:else}
				<small>Set an email on your <a class="mg-link" href={uiBase.to('/profile')}>User profile</a> to get them.</small>
			{/if}
		</span>
	</div>
{/if}

<style>
	.also {
		margin: 0 0 8px;
		text-align: center;
	}
	.go {
		/* Styled explicitly so other .mg-btn rules cannot change it. */
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		width: 100%;
		height: calc(var(--mg-ctl) * 1.45);
		border-color: transparent;
		border-radius: var(--mg-r-sm);
		background: var(--mg-accent);
		color: var(--mg-on-accent);
		font-size: var(--mg-fs-lg);
		font-weight: 650;
		box-shadow: none;
	}
	.go::before {
		content: '';
		flex: none;
		width: 12px;
		height: 14px;
		background: currentColor;
		clip-path: polygon(0 0, 100% 50%, 0 100%);
	}
	.go:not(:disabled):hover {
		animation: none;
	}
	.go:disabled {
		box-shadow: none;
	}
	.stores-setup {
		margin-bottom: 12px;
		padding: 12px 14px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
	}
	.under {
		margin-top: 8px;
		text-align: center;
	}
	.cache {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 12px;
		margin-top: 12px;
		padding: 10px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
		text-align: left;
	}
	.cache.off {
		border-color: color-mix(in srgb, var(--mg-warn) 55%, var(--mg-border));
	}
	.c-ic {
		display: inline-flex;
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.cache.off .c-ic {
		color: var(--mg-warn);
	}
	.c-text {
		display: flex;
		flex: 1 1 260px;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.c-text small {
		color: var(--mg-text-3);
	}
	.cache-ask {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 8px;
		padding: 12px 14px;
		border: 1px solid color-mix(in srgb, var(--mg-warn) 55%, var(--mg-border));
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
		text-align: left;
	}
	.cache-ask ul {
		margin: 0;
		padding-left: 18px;
		color: var(--mg-text-2);
	}
	.cache-go {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 14px;
	}
	.mail {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		margin-top: 10px;
		font-size: var(--mg-fs-sm);
	}
	.mail span {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 2px 8px;
		min-width: 0;
	}
	.mail b {
		font-weight: 600;
	}
	.mail small {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	/* What stops a run: one line in the warning colour, with its fix (the bell lists it too). */
	.blocked p {
		margin: 0;
	}
	.blocked {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: 6px 10px;
		margin-top: 8px;
		padding: 0;
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
	}
	.b-icon {
		display: inline-flex;
		color: var(--mg-warn);
	}
	.b-fix {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 0;
		border: none;
		background: none;
		color: var(--mg-accent-ink);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.b-fix:hover {
		text-decoration: underline;
	}
	:global([data-motion='off']) .go {
		animation: none !important;
	}
</style>
