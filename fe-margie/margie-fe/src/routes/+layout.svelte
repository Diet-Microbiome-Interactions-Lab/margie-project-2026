<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { afterNavigate, goto } from '$app/navigation';
	import favicon from '$lib/assets/favicon.svg';
	import { backend } from '$lib/workspace/backend.svelte';
	import { isLoggedIn } from '$lib/auth.js';
	import { useClusterBackend } from '$lib/config';
	import { HOSTED } from '$lib/hosted';

	let { children } = $props();

	// Rechecked on every navigation (including the one after signing in).
	afterNavigate(() => backend.refresh());

	// The website: every page needs a signed-in cluster account, except signing in.
	// The pages bring their own top bar (routes/(app)/+layout.svelte); sign-in has none.
	const PUBLIC_PATHS = HOSTED ? ['/signin'] : ['/signin', '/login', '/register'];

	onMount(() => {
		// Clears stored settings from older versions that pointed at a local backend.
		useClusterBackend();
		const path = window.location.pathname;
		if (HOSTED && ['/start', '/login', '/register'].some((p) => path.startsWith(p))) {
			location.replace('/signin');
			return;
		}
		if (!PUBLIC_PATHS.some((p) => path.startsWith(p)) && !isLoggedIn()) goto(HOSTED ? '/signin' : '/login');
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
{@render children()}
