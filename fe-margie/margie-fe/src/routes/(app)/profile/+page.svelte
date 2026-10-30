<script lang="ts">
	/**
	 * User profile: who you are (AboutYou) beside the cluster account MARGIE runs as, its
	 * connection and its credentials. Everything a run reads from config.yaml is on Settings,
	 * so it is set in one place.
	 */
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { authHeaders, clearToken } from '$lib/auth.js';
	import { getApiUrl } from '$lib/config';
	import AboutYou from '$lib/crisp/AboutYou.svelte';

	const API_URL = getApiUrl();

	let user = $state<{ username: string; cluster_username: string; cluster_host: string; home_dir: string } | null>(null);
	let error = $state('');
	let checking = $state(true);
	let connected = $state(false);
	let connDetail = $state('');
	let connAction = $state('');

	// ------------------------------------------------ changing the credentials
	let editing = $state(false);
	let host = $state('');
	let username = $state('');
	let key = $state('');
	let showKey = $state(false);
	let saving = $state(false);
	let credError = $state('');
	let credDone = $state('');

	function signedOut(res: Response): boolean {
		if (res.status !== 401) return false;
		clearToken();
		goto('/signin');
		return true;
	}

	async function loadUser() {
		try {
			const res = await fetch(`${API_URL}/v1/auth/me`, { headers: authHeaders() });
			if (signedOut(res)) return;
			if (!res.ok) throw new Error('Your account could not be read.');
			user = await res.json();
			host = user?.cluster_host ?? '';
			username = user?.cluster_username ?? '';
			await checkConnection();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
			checking = false;
		}
	}

	/** Asks the backend whether it reaches the cluster with the saved credentials. */
	async function checkConnection() {
		checking = true;
		error = '';
		try {
			const res = await fetch(`${API_URL}/v1/ssh/status`, { headers: authHeaders() });
			if (signedOut(res)) return;
			if (!res.ok) throw new Error('MARGIE’s server did not answer.');
			const d = await res.json();
			connected = !!d.connected;
			// The backend's reason for a failure, shown instead of "could not connect".
			connDetail = connected ? '' : (d.detail ?? '');
			connAction = connected ? '' : (d.action ?? '');
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
			connected = false;
		} finally {
			checking = false;
		}
	}

	/** Sends only what changed; the backend tries the new credentials before keeping them. */
	// ------------------------------------------------ deleting the account
	let deleting = $state(false);
	let delPassword = $state('');
	let delBusy = $state(false);
	let delError = $state('');
	async function deleteAccount() {
		delBusy = true;
		delError = '';
		try {
			const res = await fetch(`${API_URL}/v1/auth/delete-account`, {
				method: 'POST',
				headers: { ...authHeaders(), 'Content-Type': 'application/json' },
				body: JSON.stringify({ password: delPassword })
			});
			const d = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'The account could not be deleted.');
			clearToken();
			goto('/signin');
		} catch (e) {
			delError = e instanceof Error ? e.message : String(e);
		} finally {
			delBusy = false;
		}
	}

	// ------------------------------------------------ removing MARGIE's copy from the cluster
	let removing = $state(false);
	let remPassword = $state('');
	let remBusy = $state(false);
	let remError = $state('');
	let remDone = $state('');
	async function removeClusterCopy() {
		remBusy = true;
		remError = '';
		remDone = '';
		try {
			const res = await fetch(`${API_URL}/v1/auth/remove-cluster-copy`, {
				method: 'POST',
				headers: { ...authHeaders(), 'Content-Type': 'application/json' },
				body: JSON.stringify({ password: remPassword })
			});
			const d = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : "MARGIE's copy could not be removed.");
			removing = false;
			remPassword = '';
			remDone = "MARGIE's copy and the stored language-model keys were removed from your cluster home. MARGIE sets the copy up again before your next run.";
		} catch (e) {
			remError = e instanceof Error ? e.message : String(e);
		} finally {
			remBusy = false;
		}
	}

	async function saveCredentials() {
		credError = '';
		credDone = '';
		const payload: Record<string, string> = {};
		if (host.trim() && host.trim() !== user?.cluster_host) payload.cluster_host = host.trim();
		if (username.trim() && username.trim() !== user?.cluster_username) payload.cluster_username = username.trim();
		if (key.trim()) payload.private_key = key;
		if (!Object.keys(payload).length) {
			credError = 'Nothing has changed.';
			return;
		}
		saving = true;
		try {
			const res = await fetch(`${API_URL}/v1/auth/update-credentials`, { method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload) });
			if (signedOut(res)) return;
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				throw new Error(typeof d.detail === 'string' ? d.detail : 'The credentials could not be saved.');
			}
			key = '';
			credDone = 'Saved. The connection is checked again.';
			await loadUser();
		} catch (e) {
			credError = e instanceof Error ? e.message : String(e);
		} finally {
			saving = false;
		}
	}

	onMount(loadUser);
</script>

<svelte:head><title>User profile | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-profile">
	<div class="cr-head">
		<h1 class="cr-title">User profile</h1>
		<p class="cr-lede mg-explain">
			Your details, and the cluster account MARGIE runs as. What a run reads, its folders, databases and resources, is on
			<a class="mg-link" href="/settings">Settings</a>.
		</p>
	</div>

	{#if error}<p class="pf-msg bad" role="alert">{error}</p>{/if}

	<div class="pf-pair">
		<AboutYou />

		<section class="pf-box" aria-labelledby="pf-acct">
			<header class="pf-head">
				<h2 id="pf-acct">Cluster account</h2>
				<span class="pf-state" class:ok={!checking && connected} class:bad={!checking && !connected}>
					<i aria-hidden="true"></i>{checking ? 'Checking' : connected ? 'Connected' : 'Not connected'}
				</span>
			</header>

			<dl class="pf-cells">
				<div><dt>Cluster</dt><dd class="mg-mono" title={user?.cluster_host}>{user?.cluster_host || '–'}</dd></div>
				<div><dt>Username</dt><dd class="mg-mono">{user?.cluster_username || '–'}</dd></div>
				<div><dt>Home folder</dt><dd class="mg-mono" title={user?.home_dir}>{user?.home_dir || '–'}</dd></div>
				<div><dt>Signed in to MARGIE as</dt><dd>{user?.username || '–'}</dd></div>
			</dl>

			{#if !checking && !connected}
				<p class="pf-msg bad">
					{connDetail || `MARGIE could not reach ${user?.cluster_host || 'the cluster'}.`}
					{#if connAction === 're-register'}
						<!-- The stored key cannot be decrypted, so registering again is the only fix. -->
						<a class="mg-link" href="/register">Register again</a>
					{:else}
						Check the credentials below, then try again.
					{/if}
				</p>
			{/if}

			<div class="pf-acts">
				<button type="button" class="mg-btn small" disabled={checking} onclick={checkConnection}>{checking ? 'Checking…' : 'Check again'}</button>
				<button type="button" class="mg-btn small" aria-expanded={editing} onclick={() => (editing = !editing)}>{editing ? 'Close' : 'Change credentials'}</button>
			</div>

			{#if editing}
				<form
					class="pf-fields"
					onsubmit={(e) => {
						e.preventDefault();
						saveCredentials();
					}}
				>
					<label>
						<span>Cluster host</span>
						<input class="mg-input mg-mono" bind:value={host} placeholder="login.cluster.example.edu" spellcheck="false" autocomplete="off" disabled={saving} />
					</label>
					<label>
						<span>Username</span>
						<input class="mg-input mg-mono" bind:value={username} placeholder="your cluster username" spellcheck="false" autocomplete="username" disabled={saving} />
					</label>
					<div class="wide">
						<span class="pf-key-head">
							<label for="pf-key">SSH private key</label>
							<button type="button" class="mg-link quiet" onclick={() => (showKey = !showKey)}>{showKey ? 'Hide' : 'Show'}</button>
						</span>
						<textarea
							id="pf-key"
							class="mg-input mg-mono"
							class:masked={!showKey}
							rows="4"
							bind:value={key}
							placeholder="Leave empty to keep the current key"
							spellcheck="false"
							disabled={saving}
						></textarea>
					</div>
					{#if credError}<p class="pf-msg bad wide" role="alert">{credError}</p>{/if}
					{#if credDone}<p class="pf-msg ok wide" role="status">{credDone}</p>{/if}
					<div class="pf-acts wide">
						<button type="submit" class="mg-btn small primary" disabled={saving}>{saving ? 'Saving…' : 'Save credentials'}</button>
					</div>
				</form>
			{/if}
		</section>
	</div>

	<section class="pf-box pf-delete" aria-labelledby="pf-del">
		<header class="pf-head"><h2 id="pf-del">Delete account</h2></header>
		<p class="pf-del-text">
			Deletes your MARGIE account: your sign-in, your details here and the stored cluster key, and withdraws your acceptance of the
			licence terms, recorded with the licence records as acceptances are. Your home on the cluster stays as it is, since other MARGIE
			accounts (here or in the desktop app) can use the same cluster account: MARGIE's copy, config.yaml, databases and results stay. To
			remove MARGIE's copy as well, use Remove MARGIE from the cluster below first. To use MARGIE again, sign up again and accept the terms
			again.
		</p>
		{#if deleting}
			<form
				class="pf-del-form"
				onsubmit={(e) => {
					e.preventDefault();
					deleteAccount();
				}}
			>
				<label>
					<span>Your MARGIE password</span>
					<input class="mg-input" type="password" autocomplete="current-password" bind:value={delPassword} disabled={delBusy} />
				</label>
				<button type="submit" class="mg-btn small danger" disabled={!delPassword || delBusy}>{delBusy ? 'Deleting…' : 'Delete my account'}</button>
				<button type="button" class="mg-btn small" disabled={delBusy} onclick={() => ((deleting = false), (delPassword = ''), (delError = ''))}>Cancel</button>
			</form>
			{#if delError}<p class="pf-msg bad" role="alert">{delError}</p>{/if}
		{:else}
			<div><button type="button" class="mg-btn small" onclick={() => (deleting = true)}>Delete account…</button></div>
		{/if}
	</section>

	<section class="pf-box pf-delete" aria-labelledby="pf-rem">
		<header class="pf-head"><h2 id="pf-rem">Remove MARGIE from the cluster</h2></header>
		<p class="pf-del-text">
			Removes MARGIE's copy from your home on the cluster (~/margie-project-2026, with any edits to its workflow, and the
			~/bioinformatics-tools link) and the stored language-model API keys. Every MARGIE account on this cluster account, here or in the
			desktop app, runs from that copy, so MARGIE leaves it in place while one of your runs is in SLURM or the desktop app's server is
			running. Your config.yaml, databases and results stay, and MARGIE sets the copy up again before your next run.
		</p>
		{#if removing}
			<form
				class="pf-del-form"
				onsubmit={(e) => {
					e.preventDefault();
					removeClusterCopy();
				}}
			>
				<label>
					<span>Your MARGIE password</span>
					<input class="mg-input" type="password" autocomplete="current-password" bind:value={remPassword} disabled={remBusy} />
				</label>
				<button type="submit" class="mg-btn small danger" disabled={!remPassword || remBusy}>{remBusy ? 'Removing…' : "Remove MARGIE's copy"}</button>
				<button type="button" class="mg-btn small" disabled={remBusy} onclick={() => ((removing = false), (remPassword = ''), (remError = ''))}>Cancel</button>
			</form>
			{#if remError}<p class="pf-msg bad" role="alert">{remError}</p>{/if}
		{:else}
			<div><button type="button" class="mg-btn small" onclick={() => ((removing = true), (remDone = ''))}>Remove MARGIE from the cluster…</button></div>
			{#if remDone}<p class="pf-msg" role="status">{remDone}</p>{/if}
		{/if}
	</section>
</div>

<style>
	/* Two boxes of one height side by side, as on Home's drawing of the page. */
	.pf-pair {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--cr-stack, 16px);
		align-items: stretch;
	}
	.pf-pair > :global(*) {
		min-width: 0;
	}
	.pf-del-text {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.pf-del-form {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 8px 10px;
	}
	.pf-del-form label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: min(100%, 260px);
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-2);
	}
	.pf-box {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: var(--cr-box-pad, 16px 18px);
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
	}
	.pf-head {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.pf-head h2 {
		flex: 1;
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.pf-state {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-3);
	}
	.pf-state i {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: currentColor;
	}
	.pf-state.ok {
		color: var(--mg-ok);
	}
	.pf-state.bad {
		color: var(--mg-danger);
	}

	/* Facts in even cells: two across. */
	.pf-cells {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin: 0;
	}
	.pf-cells div {
		min-width: 0;
		padding: 8px 10px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
	}
	.pf-cells dt {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.pf-cells dd {
		margin: 2px 0 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text);
	}

	.pf-fields {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px 12px;
		padding-top: 12px;
		border-top: 1px solid var(--mg-border);
	}
	.pf-fields label,
	.pf-fields .wide {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.pf-fields .wide {
		grid-column: 1 / -1;
	}
	.pf-fields label > span,
	.pf-key-head label {
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-2);
	}
	.pf-key-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.pf-fields input {
		width: 100%;
		height: 34px;
	}
	.pf-fields textarea {
		width: 100%;
		resize: vertical;
		font-size: 11.5px;
	}
	.masked {
		-webkit-text-security: disc;
	}
	.pf-acts {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 8px;
		margin-top: auto;
	}
	.pf-msg {
		margin: 0;
		font-size: var(--mg-fs-sm);
	}
	.pf-msg.bad {
		color: var(--mg-danger);
	}
	.pf-msg.ok {
		color: var(--mg-ok);
	}
	@media (max-width: 900px) {
		.pf-pair {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
