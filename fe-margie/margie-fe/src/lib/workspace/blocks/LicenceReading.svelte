<script lang="ts">
	import { fetchTerms, NOT_YET, type TermsPayload } from '$lib/license';
	import Markdown from '$lib/workspace/viewers/Markdown.svelte';

	/**
	 * What the install statement speaks of: the sentences it accepts, each tool's licence and MARGIE's
	 * licence terms, read when first opened. Folded on Install; open in the statement dialog (InstallGate).
	 */
	let { label = 'Read the licences first', open = false }: { label?: string; open?: boolean } = $props();

	let terms = $state<TermsPayload | null>(null);
	let termsError = $state('');
	async function readTerms() {
		if (terms || termsError) return;
		try {
			terms = await fetchTerms();
		} catch (e) {
			termsError = e instanceof Error ? e.message : String(e);
		}
	}
	$effect(() => {
		if (open) readTerms();
	});
	/** The sentences accepted: the terms' "Your acknowledgments" section, else the acknowledgment list. */
	const accepts = $derived.by(() => {
		if (!terms) return '';
		const md = terms.terms_markdown;
		const at = md.indexOf('## Your acknowledgments');
		const section = at < 0 ? '' : md.slice(md.indexOf('\n', at) + 1).split('\n---')[0].trim();
		return section || terms.acknowledgments.map((a, i) => `${i + 1}. ${a.label}`).join('\n');
	});
	/** The tools a run uses now, by phase; steps switched off for now are left out. */
	const byPhase = $derived(
		[...(terms?.tools ?? [])].filter((t) => !NOT_YET.has(t.id)).sort((a, b) => a.phase - b.phase || a.name.localeCompare(b.name))
	);
	const TIER: Record<string, string> = {
		blocked: 'Your own licence needed',
		commercial_restricted: 'Academic use free; commercial needs permission',
		verify: 'Check its terms',
		attribution: 'Free, cite it',
		permissive: 'Free'
	};
</script>

<details class="lr" {open} ontoggle={(e) => e.currentTarget.open && readTerms()}>
	<summary>{label}</summary>
	{#if termsError}
		<p class="lr-wrong">The licences could not be read: {termsError}</p>
	{:else if !terms}
		<p class="mg-note">Reading the licences…</p>
	{:else}
		{#if accepts}
			<h3 class="lr-h">What you accept</h3>
			<div class="lr-md lr-accepts"><Markdown source={accepts} /></div>
		{/if}
		<h3 class="lr-h">The tools in a run, and their licences <span class="mg-note">{byPhase.length} tools and databases</span></h3>
		<div class="lr-wrap">
			<table class="lr-table">
				<thead>
					<tr><th>Phase</th><th>Tool</th><th>Licence</th><th>Use</th><th>Before you run it</th><th>Links</th></tr>
				</thead>
				<tbody>
					{#each byPhase as t (t.id)}
						<tr class="tier-{t.tier}">
							<td class="ph">{t.phase}</td>
							<td><b>{t.name}</b></td>
							<td>{t.license}</td>
							<td>{TIER[t.tier] ?? t.tier}</td>
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
		<h3 class="lr-h">MARGIE's licensing terms</h3>
		<div class="lr-md"><Markdown source={terms.terms_markdown} /></div>
	{/if}
</details>

<style>
	.lr {
		width: 100%;
		text-align: left;
		font-size: var(--mg-fs-sm);
	}
	.lr > summary {
		cursor: pointer;
		color: var(--mg-accent-ink, var(--mg-accent));
		font-weight: 600;
	}
	.lr-h {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 14px 0 6px;
		font-size: var(--mg-fs-sm);
		font-weight: 650;
	}
	.lr-h .mg-note {
		font-weight: 400;
	}
	.lr-md {
		max-height: 320px;
		padding: 12px 16px;
		overflow: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
	}
	.lr-accepts {
		max-height: none;
	}
	.lr-wrap {
		max-height: 360px;
		overflow: auto;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
	}
	.lr-table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--mg-fs-xs);
	}
	.lr-table th {
		position: sticky;
		top: 0;
		padding: 6px 8px;
		background: var(--cr-card, var(--mg-surface));
		color: var(--mg-text-3);
		font-weight: 600;
		text-align: left;
		white-space: nowrap;
	}
	.lr-table td {
		padding: 6px 8px;
		border-top: 1px solid var(--mg-border);
		vertical-align: top;
	}
	.lr-table .ph {
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.lr-table .act {
		min-width: 220px;
		color: var(--mg-text-2);
	}
	.lr-table .links {
		white-space: nowrap;
	}
	.lr-table .links a + a {
		margin-left: 8px;
	}
	.lr-table .tier-blocked td:nth-child(4) {
		color: var(--mg-warn);
		font-weight: 600;
	}
	.lr-wrong {
		margin: 0;
		color: var(--mg-danger, var(--mg-warn));
	}
</style>
