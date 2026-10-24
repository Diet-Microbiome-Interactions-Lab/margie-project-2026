<script lang="ts">
	/**
	 * Sign-in for the hosted site (lib/hosted.ts): MARGIE's own look, one card.
	 * Signs in to the cluster API, or creates an account there with the cluster
	 * login and SSH key the API will use; then opens the interface. People outside
	 * Purdue (reviewers, collaborators) ask for an account by email instead. MARGIE's logo
	 * turns in below the box.
	 */
	import '@fontsource/ibm-plex-sans/400.css';
	import '@fontsource/ibm-plex-sans/500.css';
	import '@fontsource/ibm-plex-sans/600.css';
	import '@fontsource/ibm-plex-sans/700.css';
	import '@fontsource/ibm-plex-mono/400.css';
	import '$lib/workspace/workspace.css';
	import '$lib/crisp/crisp.css';
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import { ChevronRight, CircleAlert, Copy, KeyRound, LoaderCircle, Mail, Server } from 'lucide-svelte';
	import CrispMark from '$lib/crisp/CrispMark.svelte';
	import Corner from '$lib/workspace/Corner.svelte';
	import MargieLogo from '$lib/workspace/MargieLogo.svelte';
	import SizeSliders from '$lib/workspace/SizeSliders.svelte';
	import { crispVars } from '$lib/crisp/theme';
	import { isLoggedIn, setToken } from '$lib/auth';
	import { getApiUrl } from '$lib/config';
	import { styleString } from '$lib/workspace/prefs';
	import { ui } from '$lib/workspace/ui.svelte';

	let mode = $state<'signin' | 'create' | 'request'>('signin');
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
	const host = $derived(clusterHost.trim() || 'cluster.address.edu');
	const who = $derived(clusterUser.trim() || 'your-username');
	const keyCmds = $derived({
		make: 'ssh-keygen -t ed25519 -N "" -f ~/.ssh/margie_ed25519',
		install: `ssh-copy-id -i ~/.ssh/margie_ed25519.pub ${who}@${host}`,
		installWin: `type $env:USERPROFILE\\.ssh\\margie_ed25519.pub | ssh ${who}@${host} "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"`,
		show: 'cat ~/.ssh/margie_ed25519'
	});
	function copy(text: string) {
		navigator.clipboard?.writeText(text).then(
			() => ui.notify('Copied', 'ok'),
			() => {}
		);
	}

	// ------------------------------------------------ outside Purdue: an account on request
	const CONTACT = 'lindems@purdue.edu';
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
	const vars = $derived(styleString(crispVars(ui.prefs, ui.dark)) + '; --cr-page: var(--mg-accent); ' + ui.motionStyle);
</script>

<svelte:head><title>Sign in | MARGIE</title></svelte:head>

<div class="crisp signin" data-mg-root data-theme={ui.dark ? 'dark' : 'light'} data-motion={ui.motion} style={vars}>
	<header class="bar">
		<span class="brand"><CrispMark size={22} /><span class="word">MARGIE</span></span>
		<span class="grow"></span>
		<Corner base="crisp" account={false}>
			{#snippet customize()}
				<SizeSliders />
			{/snippet}
		</Corner>
	</header>

	<main class="content">
		<div class="page">
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
							<p class="hint">
								MARGIE runs on Purdue's HPC cluster, so it needs an account there. To ask for a username and password, send this
								request, or write to
								<span class="addr"><a class="mg-link" href="mailto:{CONTACT}">{CONTACT}</a><button type="button" class="mg-icon-btn" aria-label="Copy the address" onclick={() => copy(CONTACT)}><Copy size={14} /></button></span>.
								Then sign in with them under Sign in.
							</p>
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
													<span class="kh-cmd"><code>{keyCmds.make}</code><button type="button" class="mg-icon-btn" aria-label="Copy" onclick={() => copy(keyCmds.make)}><Copy size={14} /></button></span>
												</li>
												<li>
													<span>Put its public half on the cluster (asks for your cluster password, and Duo, once)</span>
													<span class="kh-cmd"><code>{keyCmds.install}</code><button type="button" class="mg-icon-btn" aria-label="Copy" onclick={() => copy(keyCmds.install)}><Copy size={14} /></button></span>
													<span class="hint">Windows PowerShell has no ssh-copy-id; use this instead:</span>
													<span class="kh-cmd"><code>{keyCmds.installWin}</code><button type="button" class="mg-icon-btn" aria-label="Copy" onclick={() => copy(keyCmds.installWin)}><Copy size={14} /></button></span>
												</li>
												<li>
													<span>Show the private key and paste all of it, from BEGIN to END, into the box above</span>
													<span class="kh-cmd"><code>{keyCmds.show}</code><button type="button" class="mg-icon-btn" aria-label="Copy" onclick={() => copy(keyCmds.show)}><Copy size={14} /></button></span>
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

			<section class="welcome" aria-label="MARGIE">
				<MargieLogo size="clamp(150px, 34vw, 190px)" />
				<p class="full">Mostly Automated Rapid Genome Inference Environment</p>
				<p class="motto">Annotate with confidence: a genome-centric, context-dependent approach</p>
			</section>

			<p class="foot">Want to run MARGIE on your own computer? Get the desktop app, or use the <code>margie</code> command.</p>
		</div>
	</main>
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
	.grow {
		flex-grow: 1;
	}
	.content {
		flex-grow: 1;
		min-height: 0;
		overflow: auto;
		background: var(--mg-bg);
	}
	.page {
		width: 100%;
		max-width: 560px;
		margin: 0 auto;
		padding: calc(var(--cr-gutter) * 2) var(--cr-gutter) calc(var(--cr-gutter) * 3);
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
	/* Below the box: the logo, MARGIE's full name and its motto, rising in after it. */
	.welcome {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding-top: 6px;
		text-align: center;
	}
	.welcome p {
		margin: 0;
		animation: rise 520ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
	}
	.welcome .full {
		margin-top: 4px;
		font-weight: 600;
		animation-delay: 400ms;
	}
	.welcome .motto {
		text-wrap: balance;
		font-size: var(--cr-fs-meta);
		color: var(--mg-text-2);
		animation-delay: 520ms;
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
	@media (max-width: 520px) {
		.fields {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
