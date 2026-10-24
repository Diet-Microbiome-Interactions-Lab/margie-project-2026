<script lang="ts">
	/**
	 * The User profile's own details: name, email, institution, department or lab, ORCID iD.
	 * Kept with the account on MARGIE's server (PUT /v1/auth/profile), all optional; with the
	 * switch for emails about the user's runs, saved as it is flipped.
	 */
	import { onMount } from 'svelte';
	import { authHeaders } from '$lib/auth.js';
	import { getApiUrl } from '$lib/config';
	import { ui } from '$lib/workspace/ui.svelte';
	import Switch from '$lib/workspace/Switch.svelte';
	import { runEmails } from '$lib/workspace/run-emails.svelte';

	const FIELDS = [
		{ key: 'full_name', label: 'Name', placeholder: 'Your full name', type: 'text', auto: 'name' },
		{ key: 'email', label: 'Email', placeholder: 'you@university.edu', type: 'email', auto: 'email' },
		{ key: 'institution', label: 'Institution', placeholder: 'e.g. Purdue University', type: 'text', auto: 'organization' },
		{ key: 'department', label: 'Department or lab', placeholder: 'e.g. Food Science, Lindemann lab', type: 'text', auto: 'off' },
		{ key: 'orcid', label: 'ORCID iD', placeholder: '0000-0000-0000-0000', type: 'text', auto: 'off' }
	] as const;
	type Key = (typeof FIELDS)[number]['key'];

	let saved = $state<Record<Key, string>>({ full_name: '', email: '', institution: '', department: '', orcid: '' });
	let draft = $state<Record<Key, string>>({ ...saved });
	let saving = $state(false);
	let loaded = $state(false);
	const changed = $derived(FIELDS.some((f) => (draft[f.key] ?? '') !== (saved[f.key] ?? '')));

	function take(d: Record<string, string> & { notify_runs?: boolean }) {
		for (const f of FIELDS) saved[f.key] = d[f.key] ?? '';
		draft = { ...saved };
		// The run-emails switch (shared with Analyze) takes the same profile.
		runEmails.take(d);
		loaded = true;
	}

	onMount(async () => {
		try {
			const res = await fetch(`${getApiUrl()}/v1/auth/me`, { headers: authHeaders() });
			if (res.ok) take(await res.json());
		} catch {
			// Shown as not loaded; the page's own sections say whether the server answers.
		}
	});

	async function save() {
		saving = true;
		try {
			const res = await fetch(`${getApiUrl()}/v1/auth/profile`, {
				method: 'PUT',
				headers: { ...authHeaders(), 'Content-Type': 'application/json' },
				body: JSON.stringify(draft)
			});
			const d = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Your details could not be saved.');
			take(d);
			ui.notify('Your details are saved.', 'ok');
		} catch (e) {
			ui.notify(e instanceof Error ? e.message : String(e), 'error');
		} finally {
			saving = false;
		}
	}
</script>

<section class="about" aria-labelledby="about-t">
	<header>
		<h2 id="about-t">About you</h2>
		<span class="who">All optional; kept with your MARGIE account</span>
	</header>
	<form
		class="fields"
		onsubmit={(e) => {
			e.preventDefault();
			save();
		}}
	>
		{#each FIELDS as f (f.key)}
			<label>
				<span>{f.label}</span>
				<input class="mg-input" type={f.type} autocomplete={f.auto} placeholder={f.placeholder} disabled={!loaded} bind:value={draft[f.key]} />
			</label>
		{/each}
		<div class="acts">
			<button type="button" class="mg-btn small" disabled={!changed || saving} onclick={() => (draft = { ...saved })}>Discard</button>
			<button type="submit" class="mg-btn small primary" disabled={!changed || saving}>{saving ? 'Saving…' : 'Save'}</button>
		</div>
	</form>
	<div class="notify">
		<Switch label="Email me about my runs" checked={runEmails.on} disabled={!loaded} onchange={(on) => runEmails.set(on)} />
		<span>
			<b>Email me about my runs</b>
			<small>
				When a run completes, fails, or has been pending for more than an hour{runEmails.to ? `; to ${runEmails.to}` : '; add an email above to get them'}.
			</small>
		</span>
	</div>
</section>

<style>
	.about {
		display: flex;
		flex-direction: column;
		gap: 12px;
		width: 100%;
		min-width: 0;
		padding: 16px 18px;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
	}
	header {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 6px 14px;
	}
	/* A small label at the top of the box, as on Cluster account beside it. */
	h2 {
		flex: 1;
		margin: 0;
		font-size: var(--mg-fs-xs);
		font-weight: 650;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.who {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	/* Three rows of two: the buttons take the sixth cell. */
	.fields {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px 12px;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	label span {
		font-size: var(--mg-fs-xs);
		font-weight: 600;
		color: var(--mg-text-2);
	}
	label input {
		width: 100%;
		height: 34px;
	}
	.notify {
		display: flex;
		align-items: center;
		gap: 10px;
		padding-top: 10px;
		border-top: 1px solid var(--mg-border);
	}
	.notify span {
		display: flex;
		flex-direction: column;
		min-width: 0;
		font-size: var(--mg-fs-sm);
	}
	.notify b {
		font-weight: 600;
	}
	.notify small {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.acts {
		display: flex;
		align-items: flex-end;
		justify-content: flex-end;
		gap: 8px;
	}
	@media (max-width: 700px) {
		.fields {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
