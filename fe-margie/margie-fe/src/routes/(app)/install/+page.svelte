<script lang="ts">
	import { Lock } from 'lucide-svelte';
	import InstallBoard from '$lib/crisp/InstallBoard.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { installLock } from '$lib/workspace/install-lock.svelte';
	import { INSTALL_STATEMENT } from '$lib/workspace/install-statement';
	import { fetchLocalTerms, fetchTerms, NOT_YET, type TermsPayload } from '$lib/license';
	import Markdown from '$lib/workspace/viewers/Markdown.svelte';
	import StoresCheck from '$lib/cluster/StoresCheck.svelte';

	/** Install page, locked until the install statement is typed for this computer or cluster account. */
	$effect(() => {
		if (installLock.place) installLock.check();
	});

	let password = $state('');
	let wrong = $state('');
	let trying = $state(false);
	const where = $derived(backend.cluster ? (installLock.place ? `for ${installLock.place}` : 'for this account') : 'on this computer');

	// ------------------------------------------------ the licences the statement speaks of
	let terms = $state<TermsPayload | null>(null);
	let termsError = $state('');
	async function readTerms() {
		if (terms || termsError) return;
		try {
			if (!backend.cluster && !ws.overview) await ws.loadOverview().catch(() => {});
			terms = await (backend.cluster ? fetchTerms() : fetchLocalTerms());
		} catch (e) {
			termsError = e instanceof Error ? e.message : String(e);
		}
	}
	/** The tools a run uses now, by phase; steps switched off for now are left out. */
	const byPhase = $derived(
		[...(terms?.tools ?? [])].filter((t) => !NOT_YET.has(t.id)).sort((a, b) => a.phase - b.phase || a.name.localeCompare(b.name))
	);
	/** On this computer: the tools that wait for their own licence (Settings → Licences), by id. */
	const localGated = $derived(backend.cluster ? null : new Set(ws.overview?.licences.tools ?? []));
	const opensHere = (t: { id: string; tier: string }) => !localGated?.has(t.id) && t.tier !== 'blocked';
	const TIER: Record<string, string> = {
		blocked: 'Your own licence needed',
		commercial_restricted: 'Academic use free; commercial needs permission',
		verify: 'Check its terms',
		attribution: 'Free, cite it',
		permissive: 'Free'
	};

	async function unlock(e: SubmitEvent) {
		e.preventDefault();
		if (!password || trying) return;
		trying = true;
		wrong = await installLock.unlock(password);
		trying = false;
		if (!wrong) password = '';
	}
</script>

<svelte:head><title>Install | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-setup">
	<div class="cr-head">
		<h1 class="cr-title">Install</h1>
		<p class="cr-lede" class:mg-explain={installLock.unlocked}>
			{#if !installLock.unlocked}
				Installing sets up tools under their own licences, so it opens once you confirm the statement below; it then stays open {where}.
			{:else if backend.cluster}
				What your cluster account needs before a run: a connection, a SLURM account and the licence terms. Tools and databases are
				installed by the cluster's administrators.
			{:else}
				What this computer needs before a run: a container app, the tools' images and their reference data. Folders and resource limits
				are in <a class="mg-link" href="/settings">Settings</a>.
			{/if}
		</p>
		<span class="cr-meta">{installLock.unlocked && ws.overview ? `${ws.setupReady.ok} of ${ws.setupReady.total} ready` : ''}</span>
	</div>

	{#if installLock.unlocked}
		<InstallBoard />
	{:else if !installLock.known}
		<p class="mg-note">Checking…</p>
	{:else}
		<form class="lock" onsubmit={unlock}>
			<span class="lock-ic" aria-hidden="true"><Lock size={22} strokeWidth={1.75} /></span>
			<h2>Before installing</h2>
			<p class="mg-note">Type this statement exactly as shown to confirm it (pasting is not allowed):</p>
			<blockquote class="lock-statement" oncopy={(e) => e.preventDefault()}>{INSTALL_STATEMENT}</blockquote>
			{#if !backend.cluster}
				<p class="mg-note">
					Open to use: RASTtk, Prodigal, Pfam, COG, PGAP, GTDB-Tk, QUAST, the operon finder, the envelope stage and MARGIE's own scripts. The
					other tools install and run once you also accept their licences in Settings → Licences.
				</p>
			{/if}
			<!-- What is being agreed to: each tool's licence, and MARGIE's own terms. -->
			<details class="lock-read" ontoggle={(e) => e.currentTarget.open && readTerms()}>
				<summary>Read the licences first</summary>
				{#if termsError}
					<p class="lock-wrong">The licences could not be read: {termsError}</p>
				{:else if !terms}
					<p class="mg-note">Reading the licences…</p>
				{:else}
					<h3 class="lock-h">MARGIE's licensing terms</h3>
					<div class="lock-md"><Markdown source={terms.terms_markdown} /></div>
					<h3 class="lock-h">The tools in a run, and their licences <span class="mg-note">{byPhase.length} tools and databases</span></h3>
					<div class="lock-table-wrap">
						<table class="lock-table">
							<thead>
								<tr>
									<th>Phase</th><th>Tool</th><th>Licence</th><th>Use</th>{#if localGated}<th>Here</th>{/if}<th>Before you run it</th><th>Links</th>
								</tr>
							</thead>
							<tbody>
								{#each byPhase as t (t.id)}
									<tr class="tier-{t.tier}">
										<td class="ph">{t.phase}</td>
										<td><b>{t.name}</b></td>
										<td>{t.license}</td>
										<td>{TIER[t.tier] ?? t.tier}</td>
										{#if localGated}<td>{opensHere(t) ? 'Open' : 'Accept its licence first'}</td>{/if}
										<td class="act">{t.user_action}</td>
										<td class="links">
											{#if t.license_url}<a class="mg-link" href={t.license_url} target="_blank" rel="noopener noreferrer">Licence</a>{/if}
											{#if t.obtain_url}<a class="mg-link" href={t.obtain_url} target="_blank" rel="noopener noreferrer">{t.license_url ? 'Provider' : 'Licence and provider'}</a>{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</details>
			<div class="lock-row">
				<input
					class="mg-input"
					type="text"
					autocomplete="off"
					spellcheck="false"
					placeholder="Type the statement"
					aria-label="Install statement"
					bind:value={password}
					oninput={() => (wrong = '')}
					onpaste={(e) => e.preventDefault()}
					ondrop={(e) => e.preventDefault()}
				/>
				<button class="mg-btn primary" type="submit" disabled={!password || trying}>{trying ? 'Checking' : 'Agree and unlock'}</button>
			</div>
			{#if wrong}<p class="lock-wrong" role="alert">{wrong}</p>{/if}
		</form>
		{#if backend.cluster}
			<!-- MARGIE's own databases need no statement: what is in your working folder, and what is still to copy. -->
			<section class="mg-card lock-dbs" id="databases" aria-labelledby="lock-dbs-h">
				<h2 id="lock-dbs-h">Your databases</h2>
				<StoresCheck />
			</section>
		{/if}
	{/if}
</div>

<style>
	.lock-dbs {
		margin-top: var(--cr-gutter, 20px);
	}
	.lock-dbs h2 {
		margin: 0;
		padding: var(--mg-pad) var(--mg-pad) 10px;
		font-size: var(--mg-fs-lg);
		font-weight: 650;
	}
	.lock-statement {
		margin: 0;
		padding: 10px 14px;
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
		color: var(--mg-text);
		text-align: left;
		user-select: none;
		-webkit-user-select: none;
	}
	.lock-read {
		width: 100%;
		text-align: left;
		font-size: var(--mg-fs-sm);
	}
	.lock-read > summary {
		cursor: pointer;
		color: var(--mg-accent-ink, var(--mg-accent));
		font-weight: 600;
	}
	.lock-h {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 14px 0 6px;
		font-size: var(--mg-fs-sm);
		font-weight: 650;
	}
	.lock-h .mg-note {
		font-weight: 400;
	}
	.lock-md {
		max-height: 320px;
		padding: 12px 16px;
		overflow: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
	}
	.lock-table-wrap {
		max-height: 360px;
		overflow: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
	}
	.lock-table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--mg-fs-xs);
	}
	.lock-table th {
		position: sticky;
		top: 0;
		padding: 6px 8px;
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text-3);
		font-weight: 600;
		text-align: left;
		white-space: nowrap;
	}
	.lock-table td {
		padding: 6px 8px;
		border-top: 1px solid var(--mg-border);
		vertical-align: top;
	}
	.lock-table .ph {
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.lock-table .act {
		min-width: 220px;
		color: var(--mg-text-2);
	}
	.lock-table .links {
		white-space: nowrap;
	}
	.lock-table .links a + a {
		margin-left: 8px;
	}
	.lock-table .tier-blocked td:nth-child(4) {
		color: var(--mg-warn);
		font-weight: 600;
	}
	/* Wider while the licences are open, so their table has room. */
	.lock:has(.lock-read[open]) {
		width: min(100%, 1100px);
	}
	.lock {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		width: min(100%, 640px);
		margin: calc(var(--mg-gap) * 2) auto 0;
		padding: calc(var(--mg-gap) * 2.5) calc(var(--mg-gap) * 2);
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		text-align: center;
	}
	.lock-ic {
		display: grid;
		place-items: center;
		width: 48px;
		height: 48px;
		border-radius: 12px;
		background: color-mix(in srgb, var(--mg-accent) 12%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	h2 {
		margin: 4px 0 0;
		font-size: var(--mg-fs-lg);
		font-weight: 650;
	}
	.lock-row {
		display: flex;
		gap: 8px;
		width: 100%;
		margin-top: 6px;
	}
	.lock-row input {
		flex: 1;
		min-width: 0;
	}
	.lock-wrong {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-danger, var(--mg-warn));
	}
</style>
