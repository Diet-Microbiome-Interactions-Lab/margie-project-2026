<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { afterNavigate, beforeNavigate, goto } from '$app/navigation';
	import { updated } from '$app/state';
	import { ui } from '$lib/workspace/ui.svelte';
	import { crispVars } from '$lib/crisp/theme';
	import favicon from '$lib/assets/favicon.svg';
	import { backend } from '$lib/workspace/backend.svelte';
	import { isLoggedIn } from '$lib/auth.js';
	import { useClusterBackend } from '$lib/config';
	import { HOSTED } from '$lib/hosted';

	let { children } = $props();

	// The page's own colour behind everything, and kept for the next load's first paint (app.html).
	$effect(() => {
		const bg = crispVars(ui.prefs, ui.dark)['--mg-bg'];
		const root = document.documentElement.style;
		root.background = bg;
		root.colorScheme = ui.dark ? 'dark' : 'light';
		try {
			localStorage.setItem('margie.ui.paint', JSON.stringify({ dark: ui.dark, bg }));
		} catch {
			// Storage blocked: the next load starts from the system's light or dark.
		}
	});

	// Rechecked on every navigation (including the one after signing in).
	afterNavigate(() => backend.refresh());

	// A new version deployed while this tab was open: said once, and the next click loads it whole.
	let toldUpdated = false;
	$effect(() => {
		if (updated.current && !toldUpdated) {
			toldUpdated = true;
			ui.notify('MARGIE has a new version: it loads with your next click.', 'info');
		}
	});
	beforeNavigate(({ willUnload, to }) => {
		if (updated.current && !willUnload && to?.url) location.href = to.url.href;
	});

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
