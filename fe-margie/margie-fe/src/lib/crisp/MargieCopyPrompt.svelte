<script lang="ts">
	import { RefreshCw } from 'lucide-svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { ws } from '$lib/workspace/data.svelte';

	/**
	 * Offers the latest MARGIE when the account runs a copy the website keeps as it is (a folder of
	 * the user's own, an edited copy, or a link to another one): once after each sign-in, and from
	 * Notices. It says what moves where before the update, follows the update, and says where the
	 * previous copy went. Keeping the current copy leaves everything as it is.
	 */

	// This sign-in (its token's end): the dialog opens by itself once per sign-in.
	const SEEN = 'margie.copy.asked';
	const signin = (() => {
		try {
			return (localStorage.getItem('bsp_token') ?? '').slice(-16);
		} catch {
			return '';
		}
	})();
	function seen(): boolean {
		try {
			return localStorage.getItem(SEEN) === signin;
		} catch {
			return false;
		}
	}
	function markSeen() {
		try {
			localStorage.setItem(SEEN, signin);
		} catch {
			// asked again on the next page load
		}
	}

	$effect(() => {
		if (backend.cluster && ws.margieCopyKept && !ws.margieUpdating && !seen()) {
			markSeen();
			ws.margiePromptOpen = true;
		}
	});

	const c = $derived(ws.margieCopy);
	const up = $derived(c?.update ?? null);
	const tilde = (p: string) => (c?.home && p.startsWith(c.home) ? `~${p.slice(c.home.length)}` : p);
	const short = (sha?: string) => (sha ? sha.slice(0, 7) : '');
	let refused = $state('');
	let starting = $state(false);

	const why = $derived.by(() => {
		if (!c) return '';
		const version = c.current ? ` (version ${short(c.current.commit)}${c.current.date ? ` of ${c.current.date}` : ''})` : '';
		if (c.state === 'own-folder')
			return `Your account runs MARGIE from a folder of your own, ${tilde(c.path)}${version}. The website runs it as it is and installs updates in its own copy.`;
		if (c.state === 'edited')
			return `Your account runs MARGIE's copy in ${tilde(c.checkout)}${version}, with edited files. The website keeps edited copies as they are.`;
		if (c.state === 'other-copy') return `${tilde(c.path)} links to another copy of MARGIE, ${tilde(c.points_to)}${version}. The website runs it as it is.`;
		return '';
	});

	async function update() {
		starting = true;
		refused = await ws.updateMargieCopy();
		starting = false;
	}

	function close() {
		ws.margiePromptOpen = false;
		refused = '';
	}
</script>

<svelte:window onkeydown={(e) => ws.margiePromptOpen && e.key === 'Escape' && !ws.margieUpdating && close()} />

{#if ws.margiePromptOpen && c}
	<div class="mc-scrim" role="dialog" aria-modal="true" aria-labelledby="mc-title">
		<div class="mc">
			<span class="mc-ic" aria-hidden="true"><RefreshCw size={20} strokeWidth={1.75} /></span>
			{#if up?.state === 'running'}
				<h2 id="mc-title">Updating MARGIE in your account</h2>
				<p class="mc-lede">This takes a few minutes. You can keep working here; runs start once the update has finished.</p>
				<div class="mc-bar" aria-hidden="true"><span></span></div>
				<div class="mc-acts"><button type="button" class="mg-btn" onclick={close}>Hide</button></div>
			{:else if up?.state === 'done' && up.result}
				<h2 id="mc-title">MARGIE is up to date</h2>
				<p class="mc-lede">Your account runs version {short(up.result.commit)} from {tilde(c.install)}.</p>
				{#if up.result.moved.length}
					<p class="mc-h">Your previous copy is in</p>
					<ul class="mc-list">
						{#each up.result.moved as [from, to] (to)}<li><code>{tilde(to)}</code> <span class="mg-note">(was {tilde(from)})</span></li>{/each}
					</ul>
					<p class="mg-note">Its files are as they were; delete the folder when you are done with it.</p>
				{/if}
				<div class="mc-acts"><button type="button" class="mg-btn primary" onclick={close}>Close</button></div>
			{:else}
				<h2 id="mc-title">A newer MARGIE is ready for your account</h2>
				{#if up?.state === 'failed' && up.result}
					<p class="mc-fail" role="alert">
						The last update stopped: {up.result.message || 'a step failed'}.{up.result.restored ? ' The moved folders went back, and your current copy is in use.' : ''}
					</p>
				{/if}
				<p class="mc-lede">{why}</p>
				{#if c.latest}<p class="mc-ver">Latest version: <code>{short(c.latest.commit)}</code></p>{/if}
				{#if c.state === 'edited' && c.edited.length}
					<details class="mc-edits">
						<summary>Edited files ({c.edited.length})</summary>
						<ul>{#each c.edited as f (f)}<li><code>{f}</code></li>{/each}</ul>
					</details>
				{/if}

				<p class="mc-h">Update now:</p>
				<ul class="mc-list">
					{#each c.moves as m (m)}
						<li>Moves <code>{tilde(m)}</code> into <code>{tilde(c.previous_versions)}/</code>, in a folder named for the date and time of the update, with its files as they are.</li>
					{/each}
					{#if c.state === 'other-copy'}<li>Points <code>{tilde(c.path)}</code> at the new copy; <code>{tilde(c.points_to)}</code> stays where it is.</li>{/if}
					<li>Installs the latest MARGIE in <code>{tilde(c.install)}</code> and links <code>{tilde(c.path)}</code> to it.</li>
					<li>Keeps your settings (<code>~/.config/bioinformatics-tools</code>), databases, genomes and results where they are.</li>
					<li>Takes a few minutes. If a step fails, the moved folders go back and your current copy stays in use.</li>
				</ul>
				<p class="mg-note">Keep my current copy: runs use it as they do now. This is offered again in Notices and at your next sign-in.</p>
				{#if refused}<p class="mc-fail" role="alert">{refused}</p>{/if}
				<div class="mc-acts">
					<button type="button" class="mg-btn" onclick={close}>Keep my current copy</button>
					<button type="button" class="mg-btn primary" disabled={starting} onclick={update}>{starting ? 'Starting' : 'Update now'}</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.mc-scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
		display: grid;
		place-items: center;
		padding: 16px;
		background: color-mix(in srgb, #000 35%, transparent);
	}
	.mc {
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
	.mc-ic {
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
	.mc-lede,
	.mc-ver {
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.mc-h {
		margin-top: 4px;
		font-size: var(--mg-fs-sm);
		font-weight: 600;
	}
	.mc-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding-left: 18px;
		font-size: var(--mg-fs-sm);
	}
	code {
		font-family: var(--mg-mono, 'IBM Plex Mono', monospace);
		font-size: 0.92em;
		overflow-wrap: anywhere;
	}
	.mc-edits {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-2);
	}
	.mc-edits ul {
		margin: 4px 0 0;
		padding-left: 18px;
	}
	.mc-fail {
		padding: 8px 12px;
		border-left: 3px solid var(--mg-warn);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-warn) 10%, transparent);
		font-size: var(--mg-fs-sm);
	}
	.mc-bar {
		height: 4px;
		overflow: hidden;
		border-radius: 2px;
		background: var(--mg-surface-2, var(--mg-border));
	}
	.mc-bar span {
		display: block;
		width: 35%;
		height: 100%;
		border-radius: 2px;
		background: var(--mg-accent);
		animation: mc-slide 1.6s ease-in-out infinite;
	}
	@keyframes mc-slide {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(290%);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.mc-bar span {
			animation: none;
			width: 100%;
			opacity: 0.5;
		}
	}
	.mc-acts {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 6px;
	}
</style>
