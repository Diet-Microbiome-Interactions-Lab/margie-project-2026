<script lang="ts">
	import { Database } from 'lucide-svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';

	/**
	 * The databases choice, when databases are in an earlier format (user_stores.formats): your own
	 * working copies, or, before a first setup, the group's ones it would copy. Fresh databases of
	 * your own, or yours kept (the group's copied, for a first setup); with the server's note on
	 * updated databases and whom to ask for them, where it sets one. It opens once per sign-in, from
	 * Notices, and before a first setup (ws.setupStores waits for the choice).
	 */
	const SEEN = 'margie.db.asked';
	const signin = (() => {
		try {
			return (localStorage.getItem('bsp_token') ?? '').slice(-16);
		} catch {
			return '';
		}
	})();
	$effect(() => {
		if (!backend.cluster || !ws.databasesEarlier || ws.dbChoice || ws.margiePromptOpen || ws.storesBusy) return;
		try {
			if (localStorage.getItem(SEEN) === signin) return;
			localStorage.setItem(SEEN, signin);
		} catch {
			return;
		}
		ws.offerDatabases();
	});

	const req = $derived(ws.dbChoice);
	const f = $derived(ws.storeFormats);
	const mine = $derived(ws.databasesEarlier === 'mine');
	const earlier = $derived((f?.stores ?? []).filter((s) => (mine ? s.working : s.base)?.format === 'earlier'));
	const folder = $derived.by(() => {
		const p = (mine ? earlier[0]?.working : earlier[0]?.base)?.path ?? '';
		const cut = p.lastIndexOf('/', p.lastIndexOf('/') - 1);
		return cut > 0 ? p.slice(0, cut) : p;
	});
	const named = (label: string) => (label.startsWith('MARGIE') ? label : label[0].toLowerCase() + label.slice(1));
	const names = (xs: string[]) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs.at(-1)}`);
	const what = $derived(names(earlier.map((s) => named(s.label))));
	// Nothing in an earlier format by the time it opens: no choice to make.
	$effect(() => {
		if (req && !earlier.length) req.resolve(null);
	});
</script>

<svelte:window onkeydown={(e) => req && e.key === 'Escape' && req.resolve(null)} />

{#if req && earlier.length}
	<div class="dc-scrim" role="dialog" aria-modal="true" aria-labelledby="dc-title">
		<div class="dc">
			<span class="dc-ic" aria-hidden="true"><Database size={20} strokeWidth={1.75} /></span>
			{#if mine}
				<h2 id="dc-title">Your databases are in an earlier format</h2>
				<p class="dc-lede">
					Your {what} in your databases folder{folder ? ` (${folder})` : ''} were made by an earlier version of MARGIE, in an earlier format than this
					version writes.
				</p>
			{:else}
				<h2 id="dc-title">Your group's databases are in an earlier format</h2>
				<p class="dc-lede">
					The {what} in your group's folder{folder ? ` (${folder})` : ''} were made by an earlier version of MARGIE, in an earlier format than this version
					writes. A first setup copies them into your databases folder.
				</p>
			{/if}
			{#if f?.note}
				<p class="dc-note">{f.note}</p>
			{/if}
			{#if f?.contact}
				<p class="dc-contact">Ask for the updated databases: <a class="mg-link" href={`mailto:${f.contact}?subject=${encodeURIComponent('MARGIE updated databases')}`}>{f.contact}</a></p>
			{/if}
			<ul class="dc-list">
				{#if mine}
					<li>
						<b>Set up fresh databases:</b> new versions start empty, with MARGIE's starter operon reference (29 genomes), and each run adds its genomes to them.
						Runs use the new ones; your current copies stay in your databases folder.
					</li>
					<li><b>Keep my databases:</b> runs use them as they do now.</li>
				{:else}
					<li><b>Set up fresh databases:</b> your own start empty, with MARGIE's starter operon reference (29 genomes), and each run adds its genomes to them.</li>
					<li><b>Copy the group's databases:</b> a one-time copy into your databases folder, in the earlier format.</li>
				{/if}
			</ul>
			<p class="mg-note">The setup runs as a SLURM job on a compute node. Settings → Databases offers fresh databases later too.</p>
			<div class="dc-acts">
				{#if mine}
					<button type="button" class="mg-btn" onclick={() => req.resolve(null)}>Keep my databases</button>
				{:else}
					<button type="button" class="mg-btn" onclick={() => req.resolve(null)}>{req.from === 'signin' ? 'Later' : 'Cancel'}</button>
					<button type="button" class="mg-btn" onclick={() => req.resolve('group')}>Copy the group's databases</button>
				{/if}
				<button type="button" class="mg-btn primary" onclick={() => req.resolve('fresh')}>Set up fresh databases</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.dc-scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
		display: grid;
		place-items: center;
		padding: 16px;
		background: color-mix(in srgb, #000 35%, transparent);
	}
	.dc {
		display: flex;
		flex-direction: column;
		gap: 10px;
		width: min(100%, 560px);
		max-height: calc(100vh - 32px);
		overflow-y: auto;
		padding: 24px 24px 20px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		color: var(--mg-text);
		box-shadow: 0 20px 60px rgb(0 0 0 / 0.25);
	}
	.dc-ic {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		border-radius: 12px;
		background: color-mix(in srgb, var(--mg-accent) 12%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	h2 {
		margin: 2px 0 0;
		font-size: var(--mg-fs-lg);
		font-weight: 500;
	}
	p {
		margin: 0;
	}
	.dc-lede,
	.dc-contact {
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.dc-note {
		padding: 8px 12px;
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
		font-size: var(--mg-fs-sm);
	}
	.dc-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding-left: 18px;
		font-size: var(--mg-fs-sm);
	}
	.dc-acts {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 6px;
	}
</style>
