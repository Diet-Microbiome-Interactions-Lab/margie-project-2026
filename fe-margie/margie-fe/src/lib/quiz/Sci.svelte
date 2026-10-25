<script lang="ts">
	import { nameRuns } from './names';

	/** Quiz text with its genus and species names in italics. */
	let { text }: { text: string } = $props();
	const runs = $derived(nameRuns(text));
</script>

{#each runs as r, k (k)}{#if r.name}<i>{r.text}</i>{:else}{r.text}{/if}{/each}
