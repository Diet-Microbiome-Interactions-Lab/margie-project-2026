<script lang="ts">
	/**
	 * Sign-in for the hosted site (lib/hosted.ts): MARGIE's own look and colours in each browser, one card.
	 * Signs in to the cluster API, or creates an account there with the cluster
	 * login and SSH key the API will use; then opens the interface. People outside
	 * Purdue (reviewers, collaborators) ask for an account by email instead. MARGIE's logo
	 * turns in on the left and turns again on a click (back on a double-click), the sign-in sits
	 * on the right (the logo on top on a phone); under the logo, a link opens a small game
	 * (GenomePuzzle).
	 */
	import '@fontsource/ibm-plex-sans/400.css';
	import '@fontsource/ibm-plex-sans/500.css';
	import '@fontsource/ibm-plex-sans/600.css';
	import '@fontsource/ibm-plex-sans/700.css';
	import '@fontsource/ibm-plex-mono/400.css';
	import '$lib/workspace/workspace.css';
	import '$lib/crisp/crisp.css';
	import { onMount } from 'svelte';
	import { fade, slide } from 'svelte/transition';
	import { Check, ChevronRight, CircleAlert, Copy, Database, KeyRound, LoaderCircle, Mail, Server, X } from 'lucide-svelte';
	import DatabasesInfo from '$lib/crisp/DatabasesInfo.svelte';
	import CrispMark from '$lib/crisp/CrispMark.svelte';
	import Corner from '$lib/workspace/Corner.svelte';
	import GenomePuzzle from '$lib/workspace/GenomePuzzle.svelte';
	import MargieLogo from '$lib/workspace/MargieLogo.svelte';
	import SizeSliders from '$lib/workspace/SizeSliders.svelte';
	import { LAB, DATABASES } from '$lib/crisp/about';
	import { crispVars } from '$lib/crisp/theme';
	import { isLoggedIn, setToken } from '$lib/auth';
	import { getApiUrl } from '$lib/config';
	import { DEFAULT_PREFS, sanitizePrefs, styleString } from '$lib/workspace/prefs';
	import { ui } from '$lib/workspace/ui.svelte';

	let mode = $state<'signin' | 'create' | 'request'>('signin');
	/** The MARGIE databases, opened from the top bar in a popup. */
	let dbOpen = $state(false);
	let username = $state('');
	let password = $state('');
	let clusterHost = $state('');
	let clusterUser = $state('');
	let privateKey = $state('');
	let busy = $state(false);
	let problem = $state('');
	/** The clusters this MARGIE accepts accounts on (GET /v1/auth/policy); empty: any. */
	let clusters = $state<string[]>([]);

	onMount(() => {
		if (isLoggedIn()) {
			ui.restore();
			location.replace(ui.home());
			return;
		}
		ui.restore();
		fetch(`${getApiUrl()}/v1/auth/policy`)
			.then((r) => (r.ok ? r.json() : { clusters: [] }))
			.then((d) => (clusters = Array.isArray(d?.clusters) ? d.clusters : []))
			.catch(() => {});
		const dark = matchMedia('(prefers-color-scheme: dark)');
		ui.systemDark = dark.matches;
		const onDark = (e: MediaQueryListEvent) => (ui.systemDark = e.matches);
		dark.addEventListener('change', onDark);
		return () => dark.removeEventListener('change', onDark);
	});

	// FastAPI sends a string for handled errors and a list for validation errors.
	function describe(detail: unknown, fallback: string): string {
		if (typeof detail === 'string') return detail;
		if (Array.isArray(detail)) return detail.map((d) => `${d?.loc?.at(-1) ?? 'field'}: ${d?.msg ?? 'invalid'}`).join('; ');
		return fallback;
	}

	async function signIn() {
		const res = await fetch(`${getApiUrl()}/v1/auth/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password })
		});
		if (res.status === 401) throw new Error('Wrong username or password.');
		if (!res.ok) throw new Error(describe((await res.json().catch(() => ({}))).detail, `Could not sign in (${res.status}).`));
		setToken((await res.json()).access_token);
		ui.restore();
		location.assign(ui.home());
	}

	async function createAccount() {
		const res = await fetch(`${getApiUrl()}/v1/auth/register`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password, cluster_host: clusterHost.trim(), cluster_username: clusterUser.trim(), private_key: privateKey })
		});
		if (!res.ok) throw new Error(describe((await res.json().catch(() => ({}))).detail, `Could not create the account (${res.status}).`));
		// Registration also checks that SSH to the cluster works, so signing in follows at once.
		await signIn();
	}

	async function submit(e: Event) {
		e.preventDefault();
		busy = true;
		problem = '';
		try {
			if (mode === 'signin') await signIn();
			else await createAccount();
		} catch (e) {
			problem = e instanceof TypeError ? `Can't reach the server at ${getApiUrl() || location.origin}.` : e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	// How to make a key, with the cluster and account filled in as they are typed.
	let keyHelp = $state(false);
	/** The genome puzzle under the logo, folded until asked for. */
	let game = $state(false);
	const host = $derived(clusterHost.trim() || 'cluster.address.edu');
	const who = $derived(clusterUser.trim() || 'your-username');
	const keyCmds = $derived({
		make: 'ssh-keygen -t ed25519 -N "" -f ~/.ssh/margie_ed25519',
		install: `ssh-copy-id -i ~/.ssh/margie_ed25519.pub ${who}@${host}`,
		installWin: `type $env:USERPROFILE\\.ssh\\margie_ed25519.pub | ssh ${who}@${host} "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"`,
		show: 'cat ~/.ssh/margie_ed25519'
	});
	/** The text just copied: its button shows a tick and Copied for a moment, once the copy worked. */
	let copied = $state('');
	let copiedTimer: ReturnType<typeof setTimeout> | undefined;
	function copy(text: string) {
		navigator.clipboard?.writeText(text).then(
			() => {
				copied = text;
				clearTimeout(copiedTimer);
				copiedTimer = setTimeout(() => (copied = ''), 1800);
			},
			() => {}
		);
	}

	// ------------------------------------------------ outside Purdue: an account on request
	const CONTACT = LAB.email;
	let req = $state({ name: '', institution: '', email: '', purpose: '', message: '' });
	/** The request as typed, nothing added: their mail app sends it to CONTACT. */
	const mailto = $derived.by(() => {
		const body = [
			`Name: ${req.name.trim()}`,
			`Institution: ${req.institution.trim()}`,
			`Email: ${req.email.trim()}`,
			`Purpose of use: ${req.purpose.trim()}`,
			'',
			req.message.trim()
		].join('\n');
		return `mailto:${CONTACT}?subject=${encodeURIComponent('MARGIE access request')}&body=${encodeURIComponent(body)}`;
	});
	const canRequest = $derived(!!req.name.trim() && !!req.institution.trim() && /\S+@\S+\.\S+/.test(req.email.trim()) && !!req.purpose.trim());

	const canSubmit = $derived(!!username && !!password && (mode === 'signin' || (!!clusterHost.trim() && !!clusterUser.trim() && !!privateKey.trim())));
	/** MARGIE's own colours, the same in each browser; light or dark, text and the reading aids as chosen. */
	const look = $derived(
		sanitizePrefs({
			...DEFAULT_PREFS,
			interface: 'crisp',
			...Object.fromEntries((['theme', 'textSize', 'textScale', 'fieldScale', 'typeface', 'monoface', 'contrast', 'vision'] as const).map((k) => [k, ui.prefs[k]]))
		})
	);
	const vars = $derived(styleString(crispVars(look, ui.dark)) + '; --cr-page: var(--mg-accent); ' + ui.motionStyle);
</script>

<svelte:head><title>Sign in | MARGIE</title></svelte:head>
<svelte:window onkeydown={(e) => e.key === 'Escape' && dbOpen && (dbOpen = false)} />

{#snippet copyButton(text: string, label: string)}
	<button type="button" class="mg-icon-btn" aria-label={label} onclick={() => copy(text)}>
		{#if copied === text}<Check size={14} />{:else}<Copy size={14} />{/if}
	</button>
	{#if copied === text}<span class="copied" role="status" transition:fade={{ duration: ui.ms(120) }}>Copied</span>{/if}
{/snippet}

<div class="crisp signin" data-mg-root data-theme={ui.dark ? 'dark' : 'light'} data-motion={ui.motion} style={vars}>
	<header class="bar">
		<span class="brand"><CrispMark size={22} /><span class="word">MARGIE</span><span class="platform">Bioinformatics Supercomputing Platform</span></span>
		<button type="button" class="db-open" aria-haspopup="dialog" onclick={() => (dbOpen = true)}><Database size={14} />MARGIE databases</button>
		<span class="grow"></span>
		<Corner base="crisp" colours={false} account={false}>
			{#snippet customize()}
				<SizeSliders />
			{/snippet}
		</Corner>
	</header>

	<main class="content">
		<div class="page">
			<section class="welcome" aria-label="MARGIE">
				<MargieLogo size="var(--logo-size)" turn="click" float={false} />
				<p class="full">Mostly Automated Rapid Genome Inference Environment</p>
				<p class="motto">Annotate with confidence: a genome-centric, context-dependent approach</p>
				<button type="button" class="bored" aria-expanded={game} onclick={() => (game = !game)}>
					{game ? 'Hide the puzzle' : 'Solve Puzzle'}
				</button>
				{#if game}
					<div class="game" transition:slide={{ duration: ui.ms(240) }}><GenomePuzzle /></div>
				{/if}
			</section>

			<div class="side">
				<header class="st-head">
					<h1 class="cr-title">{mode === 'signin' ? 'Sign in' : mode === 'create' ? 'New account' : 'Access from outside Purdue'}</h1>
					<p class="cr-lede">
						{mode === 'request' ? 'Reviewers and collaborators get a username and password to sign in with.' : 'Sign in to run MARGIE on your cluster.'}
					</p>
				</header>

				<section class="card">
					<header class="card-head"><h2><span class="num"><Server size={14} /></span>Account</h2></header>
					<div class="card-body">
						<div class="tabs" role="tablist" aria-label="Account">
							<button type="button" role="tab" aria-selected={mode === 'signin'} onclick={() => (mode = 'signin')}>Sign in</button>
							<button type="button" role="tab" aria-selected={mode === 'create'} onclick={() => (mode = 'create')}>Create account</button>
							<button type="button" role="tab" aria-selected={mode === 'request'} onclick={() => (mode = 'request')}>Outside Purdue</button>
						</div>

						{#if problem}
							<p class="error" role="alert" transition:fade={{ duration: ui.ms(150) }}><CircleAlert size={16} /> <span>{problem}</span></p>
						{/if}

						{#if mode === 'request'}
							<!-- No cluster account: a request for one to sign in with. -->
							<div class="form">
								<div class="hint request">
									<p>
										MARGIE runs on Purdue's HPC cluster, so she needs an account there. If you are not affiliated with Purdue, or are a
										collaborator or a reviewer, please email the address below to get a username and password to sign in.
									</p>
									<p>
										You can fill in the form below or request access from your institutional email. Legitimate requests should get a
										username and password in less than 72 hours.
									</p>
									<p>
										Please note: requests from personal email addresses may not get a reply. Once MARGIE is released to the public,
										everyone will be able to access and use the site. Cheers!
									</p>
								</div>
								<address class="contact">
									<span class="contact-head">Contact</span>
									<span class="addr"><a class="mg-link" href="mailto:{CONTACT}">{CONTACT}</a>{@render copyButton(CONTACT, 'Copy the address')}</span>
								</address>
								<div class="fields">
									<label class="field">
										<span class="label">Your name</span>
										<input class="mg-input" bind:value={req.name} autocomplete="name" />
									</label>
									<label class="field">
										<span class="label">Institution</span>
										<input class="mg-input" bind:value={req.institution} autocomplete="organization" />
									</label>
									<label class="field">
										<span class="label">Email</span>
										<input class="mg-input" type="email" bind:value={req.email} autocomplete="email" />
									</label>
									<label class="field">
										<span class="label">Purpose of use</span>
										<input class="mg-input" bind:value={req.purpose} />
									</label>
									<label class="field wide">
										<span class="label">Message</span>
										<textarea class="mg-input" rows="4" bind:value={req.message}></textarea>
									</label>
								</div>
								<div class="acts">
									<span class="hint">Opens your mail app, addressed to {CONTACT}.</span>
									<a class="mg-btn primary" class:off={!canRequest} href={canRequest ? mailto : undefined} aria-disabled={!canRequest}><Mail size={15} /> Send request</a>
								</div>
							</div>
						{:else}
						<form class="form" onsubmit={submit}>
							<div class="fields">
								<label class="field">
									<span class="label">Username</span>
									<input class="mg-input" bind:value={username} autocomplete="username" spellcheck="false" required />
								</label>
								<label class="field">
									<span class="label">Password</span>
									<input class="mg-input" type="password" bind:value={password} autocomplete={mode === 'signin' ? 'current-password' : 'new-password'} required />
								</label>
								{#if mode === 'create'}
									<p class="hint span">This is your MARGIE login. Jobs run on the cluster under the cluster account below.</p>
									<label class="field">
										<span class="label">Cluster address</span>
										<input class="mg-input" bind:value={clusterHost} placeholder={clusters[0]?.replace('*', 'login') || 'login.cluster.example.edu'} spellcheck="false" required />
										{#if clusters.length}<span class="hint">Accounts on {clusters.join(', ')} only.</span>{/if}
									</label>
									<label class="field">
										<span class="label">Cluster username</span>
										<input class="mg-input" bind:value={clusterUser} placeholder="jdoe" autocomplete="off" spellcheck="false" required />
									</label>
									<label class="field span">
										<span class="label">SSH private key</span>
										<textarea class="mg-input mono" rows="5" bind:value={privateKey} placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" spellcheck="false" required></textarea>
										<span class="hint">Paste a private key whose public key is already in ~/.ssh/authorized_keys on the cluster. It is stored encrypted.</span>
									</label>
									<div class="field span keyhelp">
										<button type="button" class="kh-toggle" aria-expanded={keyHelp} onclick={() => (keyHelp = !keyHelp)}>
											<ChevronRight size={15} class="chev" /><KeyRound size={14} /> Don't have a key yet? How to make one
										</button>
										{#if keyHelp}
											<div class="kh-body" transition:fade={{ duration: ui.ms(120) }}>
												<p class="hint">Three commands in a terminal on your own computer (macOS, Linux, or Windows PowerShell). The key has no passphrase: MARGIE's server uses it without anyone there to type one. The cluster address and username above are filled in below.</p>
												<ol class="kh-steps">
													<li>
														<span>Make a key just for MARGIE</span>
														<span class="kh-cmd"><code>{keyCmds.make}</code>{@render copyButton(keyCmds.make, 'Copy the command')}</span>
													</li>
													<li>
														<span>Put its public half on the cluster (asks for your cluster password, and Duo, once)</span>
														<span class="kh-cmd"><code>{keyCmds.install}</code>{@render copyButton(keyCmds.install, 'Copy the command')}</span>
														<span class="hint">Windows PowerShell has no ssh-copy-id; use this instead:</span>
														<span class="kh-cmd"><code>{keyCmds.installWin}</code>{@render copyButton(keyCmds.installWin, 'Copy the command')}</span>
													</li>
													<li>
														<span>Show the private key and paste all of it, from BEGIN to END, into the box above</span>
														<span class="kh-cmd"><code>{keyCmds.show}</code>{@render copyButton(keyCmds.show, 'Copy the command')}</span>
													</li>
												</ol>
												<p class="hint">To take MARGIE's access away later, delete the line ending in <code>margie_ed25519</code> from <code>~/.ssh/authorized_keys</code> on the cluster.</p>
											</div>
										{/if}
									</div>
								{/if}
							</div>
							<div class="acts">
								<button type="submit" class="mg-btn primary" disabled={!canSubmit || busy}>
									{#if busy}<LoaderCircle size={15} class="spin" />{/if}
									{mode === 'signin' ? 'Sign in' : 'Create account'}
								</button>
							</div>
						</form>
						{/if}
					</div>
				</section>

				<p class="foot">Want to run MARGIE on your own computer? Get the desktop app, or use the <code>margie</code> command.</p>
			</div>
		</div>
	</main>

	{#if dbOpen}
		<button type="button" class="db-scrim" aria-label="Close" onclick={() => (dbOpen = false)} transition:fade={{ duration: ui.ms(120) }}></button>
		<div class="db-pop" role="dialog" aria-modal="true" aria-labelledby="db-pop-h" transition:fade={{ duration: ui.ms(140) }}>
			<header class="db-pop-head">
				<div>
					<h2 id="db-pop-h">MARGIE databases</h2>
					<p>{DATABASES.lede}</p>
				</div>
				<span class="grow"></span>
				<button type="button" class="mg-icon-btn" aria-label="Close" onclick={() => (dbOpen = false)}><X size={16} /></button>
			</header>
			<DatabasesInfo />
		</div>
	{/if}
</div>

<style>
	.signin {
		display: flex;
		flex-direction: column;
		height: 100vh;
		height: 100dvh;
		color: var(--mg-text);
		font-family: var(--mg-font);
		font-size: var(--cr-fs-body);
	}
	.bar {
		/* Above the page, so the theme and Customize menus open over it rather than under it. */
		position: relative;
		z-index: 5;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 16px;
		height: 60px;
		padding: 0 16px 0 20px;
		border-bottom: 1px solid var(--mg-border);
		background: var(--cr-bar-bg);
		backdrop-filter: saturate(1.4) blur(12px);
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 9px;
	}
	.word {
		font-size: calc(var(--cr-fs-body) * 1.3);
		font-weight: 700;
		letter-spacing: 0.06em;
	}
	/* As in the app's top bar: the platform's name after a hairline, from tablet width up. */
	.platform {
		display: none;
		margin-left: 2px;
		padding-left: 11px;
		border-left: 1px solid var(--mg-border);
		color: var(--mg-text-2);
		font-size: var(--cr-fs-body);
		font-weight: 400;
	}
	@media (min-width: 640px) {
		.platform {
			display: inline;
		}
	}
	.grow {
		flex-grow: 1;
	}
	.content {
		flex-grow: 1;
		min-height: 0;
		overflow: auto;
		background: var(--mg-bg);
	}
	/* Two columns of one width, both centred: the logo on the left, the sign-in on the right. */
	.page {
		width: 100%;
		max-width: 1160px;
		min-height: 100%;
		margin: 0 auto;
		padding: calc(var(--cr-gutter) * 2) var(--cr-gutter);
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		align-items: center;
		gap: calc(var(--cr-gutter) * 2);
	}
	.side {
		justify-self: center;
		width: 100%;
		max-width: 560px;
		display: flex;
		flex-direction: column;
		gap: var(--cr-gutter);
	}
	.st-head {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 4px 0 2px;
	}
	.card {
		display: flex;
		flex-direction: column;
		min-width: 0;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--cr-card);
		box-shadow: var(--cr-card-shadow);
		overflow: hidden;
	}
	.card-head {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: calc(var(--cr-fs-body) * 3.4);
		padding: 10px 18px;
		border-bottom: 1px solid var(--mg-border);
	}
	.card-head h2 {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: var(--cr-fs-section);
		font-weight: 650;
	}
	.num {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 50%;
		background: color-mix(in srgb, var(--mg-accent-base) 12%, var(--mg-surface));
		color: var(--mg-accent-ink, var(--mg-accent-base));
	}
	.card-body {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 18px;
	}
	.tabs {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 2px;
		padding: 3px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-text) 4%, var(--mg-surface));
	}
	.tabs button {
		height: calc(var(--mg-ctl-sm) - 8px);
		padding: 0 12px;
		border: none;
		border-radius: var(--mg-r-sm);
		background: none;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--cr-fs-meta);
		font-weight: 500;
		cursor: pointer;
	}
	.tabs button[aria-selected='true'] {
		background: var(--mg-seg-sel);
		box-shadow:
			var(--mg-shadow-sm),
			0 0 0 1px var(--mg-border);
		color: var(--mg-accent-ink, var(--mg-text));
		font-weight: 600;
	}
	/* MARGIE databases: a button after the platform's name, and its popup. */
	.db-open {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 30px;
		padding: 0 11px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		color: var(--mg-text);
		font: inherit;
		font-size: var(--cr-fs-meta);
		white-space: nowrap;
		cursor: pointer;
	}
	.db-open:hover {
		border-color: var(--mg-border-strong, var(--mg-text-3));
	}
	.db-scrim {
		position: fixed;
		inset: 0;
		z-index: 70;
		border: none;
		background: rgb(0 0 0 / 0.32);
		cursor: default;
	}
	.db-pop {
		position: fixed;
		z-index: 71;
		top: 50%;
		left: 50%;
		width: min(560px, calc(100vw - 32px));
		max-height: calc(100vh - 48px);
		overflow: auto;
		padding: 22px 24px 20px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		box-shadow: 0 18px 48px rgb(0 0 0 / 0.22);
		color: var(--mg-text);
		font-size: var(--cr-fs-body);
		line-height: 1.6;
		transform: translate(-50%, -50%);
	}
	.db-pop-head {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		margin-bottom: 10px;
	}
	.db-pop-head h2 {
		margin: 0;
		font-size: calc(var(--cr-fs-body) * 1.35);
		font-weight: 650;
	}
	.db-pop-head p {
		margin: 2px 0 0;
		color: var(--mg-text-2);
	}
	.db-pop :global(p) {
		margin: 0 0 10px;
	}
	.db-pop :global(.dbi-lead) {
		font-size: var(--cr-fs-section);
	}
	.db-pop :global(.dbi-list) {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0 0 12px;
		padding-left: 1.3em;
		list-style: disc;
	}
	.db-pop :global(.rp-note) {
		color: var(--mg-text-2);
		font-size: var(--cr-fs-meta);
	}
	@media (max-width: 520px) {
		.db-open {
			padding: 0 8px;
		}
	}
	.form {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px 18px;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}
	.span {
		grid-column: 1 / -1;
	}
	.label {
		font-size: var(--cr-fs-meta);
		font-weight: 600;
		color: var(--mg-text-2);
	}
	.field > .mg-input,
	.field textarea {
		width: 100%;
	}
	.keyhelp {
		gap: 10px;
	}
	.kh-toggle {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 0;
		border: none;
		background: none;
		color: var(--mg-accent-ink, var(--mg-accent-base));
		font: inherit;
		font-size: var(--cr-fs-meta);
		font-weight: 600;
		cursor: pointer;
	}
	.kh-toggle[aria-expanded='true'] :global(.chev) {
		transform: rotate(90deg);
	}
	.kh-body {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 12px 14px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: color-mix(in srgb, var(--mg-text) 3%, var(--mg-surface));
	}
	.kh-steps {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding-left: 20px;
		font-size: var(--cr-fs-meta);
	}
	.kh-steps li {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.kh-cmd {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}
	.kh-cmd code {
		flex: 1;
		min-width: 0;
		padding: 5px 8px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-family: var(--mg-mono);
		font-size: 0.85em;
		overflow-x: auto;
		white-space: nowrap;
	}
	.hint {
		font-size: var(--cr-fs-meta);
		color: var(--mg-text-3);
	}
	.wide {
		grid-column: 1 / -1;
	}
	.request {
		display: flex;
		flex-direction: column;
		gap: 8px;
		line-height: 1.5;
	}
	.request p {
		margin: 0;
	}
	/* Who to write to: the address, with a copy button. */
	.contact {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 12px;
		padding: 10px 14px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-text) 3%, var(--mg-surface));
		font-size: var(--cr-fs-meta);
		font-style: normal;
		color: var(--mg-text-2);
	}
	.contact-head {
		font-weight: 600;
		color: var(--mg-text);
	}
	.copied {
		font-size: var(--cr-fs-micro);
		font-weight: 600;
		color: var(--mg-ok);
		white-space: nowrap;
	}
	.addr {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		vertical-align: middle;
	}
	a.mg-btn {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		text-decoration: none;
	}
	a.mg-btn.off {
		opacity: 0.5;
		pointer-events: none;
	}
	.acts {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 12px;
	}
	.error {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 12px 16px;
		border: 1px solid color-mix(in srgb, var(--mg-danger) 45%, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--mg-danger-soft);
		font-size: var(--cr-fs-meta);
	}
	.error :global(svg) {
		flex-shrink: 0;
		margin-top: 3px;
		color: var(--mg-danger);
	}
	/* The logo, MARGIE's full name and her motto, rising in after it. */
	.welcome {
		--logo-size: clamp(190px, 19vw, 240px);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		text-align: center;
	}
	.welcome p {
		margin: 0;
		animation: rise 520ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
	}
	.welcome .full {
		margin-top: 8px;
		font-size: calc(var(--cr-fs-body) * 1.2);
		font-weight: 600;
		animation-delay: 400ms;
	}
	.welcome .motto {
		text-wrap: balance;
		color: var(--mg-text-2);
		animation-delay: 520ms;
	}
	.bored {
		display: inline-flex;
		align-items: center;
		margin-top: 8px;
		padding: 6px 14px;
		border: 1px solid color-mix(in srgb, var(--mg-accent-base) 35%, var(--mg-border));
		border-radius: 999px;
		background: var(--mg-surface);
		color: var(--mg-accent-ink, var(--mg-accent-base));
		font: inherit;
		font-size: var(--cr-fs-meta);
		font-weight: 600;
		cursor: pointer;
		transition: background 120ms ease-out;
	}
	.bored:hover {
		background: color-mix(in srgb, var(--mg-accent-base) 8%, var(--mg-surface));
	}
	.game {
		display: flex;
		justify-content: center;
		width: 100%;
		padding-top: 10px;
	}
	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
	}
	:global([data-motion='off']) .welcome p {
		animation: none;
	}
	@media (prefers-reduced-motion: reduce) {
		.welcome p {
			animation: none;
		}
	}
	.foot {
		text-align: center;
		font-size: var(--cr-fs-meta);
		color: var(--mg-text-3);
	}
	code {
		font-family: var(--mg-mono);
		font-size: 0.9em;
	}
	:global(.spin) {
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	/* A phone or a narrow window: the logo on top, smaller, then the sign-in. */
	@media (max-width: 860px) {
		.page {
			grid-template-columns: minmax(0, 1fr);
			align-items: start;
			align-content: start;
			gap: calc(var(--cr-gutter) * 1.5);
		}
		.welcome {
			--logo-size: 160px;
		}
	}
	@media (max-width: 520px) {
		.fields {
			grid-template-columns: minmax(0, 1fr);
		}
		/* A tab name on two lines stays inside its tab. */
		.tabs button {
			height: auto;
			min-height: calc(var(--mg-ctl-sm) - 8px);
			padding: 4px 6px;
			line-height: 1.25;
		}
	}
</style>
