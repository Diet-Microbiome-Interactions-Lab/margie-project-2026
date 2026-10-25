<script lang="ts">
	import { INSTALL_STATEMENT } from '$lib/workspace/install-statement';
	import { tick } from 'svelte';
	import { Lock } from 'lucide-svelte';
	import { installLock } from '../install-lock.svelte';
	import LicenceReading from './LicenceReading.svelte';

	/**
	 * Statement dialog before the first installation, database download or database setup of a place,
	 * with the licences to read and a note on citing. Mounted once per shell; installLock.confirm()
	 * opens it and resolves to the statement or null. Once typed, the place keeps it.
	 */
	let password = $state('');
	let wrong = $state('');
	let checking = $state(false);
	let field = $state<HTMLInputElement | null>(null);

	const req = $derived(installLock.request);
	$effect(() => {
		if (!req) return;
		password = '';
		wrong = '';
		tick().then(() => field?.focus());
	});

	async function go(e: SubmitEvent) {
		e.preventDefault();
		if (!req || !password || checking) return;
		checking = true;
		wrong = await installLock.unlock(password);
		checking = false;
		if (!wrong) req.resolve(password);
	}
</script>

<svelte:window onkeydown={(e) => req && e.key === 'Escape' && req.resolve(null)} />

{#if req}
	<div class="gate-scrim" role="dialog" aria-modal="true" aria-labelledby="gate-title">
		<form class="gate" onsubmit={go}>
			<span class="gate-ic" aria-hidden="true"><Lock size={20} strokeWidth={1.75} /></span>
			<h2 id="gate-title">Before the first installation</h2>
			<p class="what">{req.what}</p>
			<p class="once">You type this once for {installLock.place === 'local' ? 'this computer' : installLock.place || 'this account'}; later installations go ahead.</p>
			<div class="remind">
				<p>Before installing:</p>
				<ul>
					<li>Make sure you have permission to use each tool and its data. Some carry licences of their own (Settings → Licences).</li>
					<li>Cite the original developers of every tool you use, and MARGIE.</li>
				</ul>
			</div>
			<p class="type-it">Type this statement exactly as shown (pasting is not allowed):</p>
			<blockquote class="statement" oncopy={(e) => e.preventDefault()}>{INSTALL_STATEMENT}</blockquote>
			<LicenceReading />
			<input
				bind:this={field}
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
			{#if wrong}<p class="wrong" role="alert">{wrong}</p>{/if}
			<div class="acts">
				<button type="button" class="mg-btn" onclick={() => req.resolve(null)}>Cancel</button>
				<button type="submit" class="mg-btn primary" disabled={!password || checking}>{checking ? 'Checking' : 'Agree and continue'}</button>
			</div>
		</form>
	</div>
{/if}

<style>
	.type-it {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.statement {
		margin: 0;
		padding: 8px 12px;
		border-left: 3px solid var(--mg-accent);
		border-radius: var(--mg-r-sm);
		background: color-mix(in srgb, var(--mg-accent) 6%, transparent);
		color: var(--mg-text);
		font-size: var(--mg-fs-sm);
		user-select: none;
		-webkit-user-select: none;
	}
	.gate-scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
		display: grid;
		place-items: center;
		padding: 16px;
		background: color-mix(in srgb, #000 35%, transparent);
	}
	.gate {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		width: min(100%, 440px);
		max-height: calc(100vh - 32px);
		overflow-y: auto;
		padding: 24px 24px 20px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r);
		background: var(--mg-surface);
		color: var(--mg-text);
		box-shadow: 0 20px 60px rgb(0 0 0 / 0.25);
		text-align: center;
	}
	.gate:has(:global(.lr[open])) {
		width: min(100%, 1000px);
	}
	.once {
		margin: 0;
		color: var(--mg-text-3);
		font-size: var(--mg-fs-xs);
	}
	.gate-ic {
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
	.what {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-text-2);
	}
	.remind {
		width: 100%;
		padding: 10px 14px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface-2);
		font-size: var(--mg-fs-sm);
		line-height: 1.5;
		text-align: left;
		color: var(--mg-text-2);
	}
	.remind p {
		margin: 0 0 4px;
		color: var(--mg-text);
	}
	.remind ul {
		margin: 0;
		padding-left: 18px;
		list-style: disc;
	}
	.remind li + li {
		margin-top: 2px;
	}
	.gate input {
		width: 100%;
		margin-top: 4px;
	}
	.wrong {
		margin: 0;
		font-size: var(--mg-fs-sm);
		color: var(--mg-danger, var(--mg-warn));
	}
	.acts {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		width: 100%;
		margin-top: 4px;
	}
</style>
