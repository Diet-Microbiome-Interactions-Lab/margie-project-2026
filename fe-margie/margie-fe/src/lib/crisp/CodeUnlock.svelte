<script lang="ts">
	import { Lock } from 'lucide-svelte';
	import { keepCodeKey } from '$lib/cluster/code-key';
	import { call } from '$lib/cluster/http';

	/** Where the server keeps the code behind a password: asks for it, then `onopen` reads the code again. */
	let { onopen }: { onopen: () => void } = $props();
	let typed = $state('');
	let busy = $state(false);
	let wrong = $state(false);

	async function open() {
		const password = typed.trim();
		if (!password || busy) return;
		busy = true;
		try {
			await call('POST', '/v1/code/unlock', { password });
			keepCodeKey(password);
			typed = '';
			wrong = false;
			onopen();
		} catch {
			wrong = true;
		} finally {
			busy = false;
		}
	}
</script>

<form
	class="cu"
	onsubmit={(e) => {
		e.preventDefault();
		open();
	}}
>
	<span class="cu-why"><Lock size={14} aria-hidden="true" /> The code is shown with its password.</span>
	<input class="mg-input" type="password" bind:value={typed} placeholder="Password" aria-label="Code password" aria-invalid={wrong || undefined} autocomplete="off" spellcheck="false" />
	<button type="submit" class="mg-btn small primary" disabled={!typed.trim() || busy}>{busy ? 'Opening…' : 'Show the code'}</button>
	{#if wrong}<span class="cu-wrong" role="alert">That is not the password.</span>{/if}
</form>

<style>
	.cu {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 10px;
		padding: 10px 12px;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--mg-surface);
		font-size: var(--mg-fs-sm);
	}
	.cu-why {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--mg-text-2);
	}
	.cu input {
		width: 220px;
		max-width: 100%;
	}
	.cu-wrong {
		color: var(--mg-danger);
	}
</style>
