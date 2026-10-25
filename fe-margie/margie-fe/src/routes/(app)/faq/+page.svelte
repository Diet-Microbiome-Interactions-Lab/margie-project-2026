<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	/** The FAQ lives on Methods; /faq (and /faq#<question>) opens it there. */
	onMount(() => goto(`/methods${location.hash || '#faq'}`, { replaceState: true }));
</script>
