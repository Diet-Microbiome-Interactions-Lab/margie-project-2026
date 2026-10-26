<script lang="ts">
	import { DATABASES } from '$lib/crisp/about';
	import DatabasesInfo from '$lib/crisp/DatabasesInfo.svelte';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';

	/** MARGIE databases: the databases MARGIE generates, to be released here as one download. */
</script>

<svelte:head><title>MARGIE databases | MARGIE</title></svelte:head>

<ReadingPage title="MARGIE databases" lede={DATABASES.lede} shade="page-databases">
	<section class="rp-sec" id="release">
		<h2>The first release</h2>
		<DatabasesInfo />
	</section>
</ReadingPage>
