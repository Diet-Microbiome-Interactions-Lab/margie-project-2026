<script lang="ts">
	/**
	 * Layout for every page of the site: restores preferences, tracks the system's light or
	 * dark and its motion setting, starts the workspace polling, and puts the frame around
	 * the page (AppShell, in the look of Dane's original pages).
	 */
	import '@fontsource/ibm-plex-mono/400.css';
	import '@fontsource/ibm-plex-mono/500.css';
	import '$lib/workspace/workspace.css';
	import '$lib/workspace/motion/motion.css';
	import '$lib/crisp/crisp.css';
	import '$lib/crisp/skeleton-look.css';
	import '$lib/crisp/theme-effects.css';
	import { onMount } from 'svelte';
	import AppShell from '$lib/crisp/AppShell.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { catchDownloads } from '$lib/cluster/downloads';
	import { ui } from '$lib/workspace/ui.svelte';
	import { HOSTED } from '$lib/hosted';

	let { children } = $props();

	const dark = matchMedia('(prefers-color-scheme: dark)');
	const reduce = matchMedia('(prefers-reduced-motion: reduce)');
	ui.restore();
	ui.systemDark = dark.matches;
	ui.reducedMotion = reduce.matches;

	onMount(() => {
		const onDark = (e: MediaQueryListEvent) => (ui.systemDark = e.matches);
		const onReduce = (e: MediaQueryListEvent) => (ui.reducedMotion = e.matches);
		const save = () => ui.flush();
		dark.addEventListener('change', onDark);
		reduce.addEventListener('change', onReduce);
		addEventListener('pagehide', save);
		// In cluster mode, file links are intercepted and fetched with the sign-in.
		backend.refresh();
		if (HOSTED && !backend.cluster) {
			// The website has no local mode: nothing to show before signing in.
			location.replace('/signin');
			return;
		}
		const release = backend.cluster ? catchDownloads() : null;
		ws.loadAll();
		ws.startPolling();
		return () => {
			release?.();
			dark.removeEventListener('change', onDark);
			reduce.removeEventListener('change', onReduce);
			removeEventListener('pagehide', save);
			ws.stopPolling();
			ui.flush();
		};
	});
</script>

<svelte:head>
	<title>MARGIE</title>
	<meta name="color-scheme" content={ui.dark ? 'dark' : 'light'} />
</svelte:head>

<AppShell>{@render children()}</AppShell>
