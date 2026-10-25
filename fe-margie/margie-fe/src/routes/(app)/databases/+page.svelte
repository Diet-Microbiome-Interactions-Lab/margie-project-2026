<script lang="ts">
	import { DATABASES, LAB } from '$lib/crisp/about';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';

	/** MARGIE databases: the databases MARGIE generates, to be released here as one download. */
</script>

<svelte:head><title>MARGIE databases | MARGIE</title></svelte:head>

<ReadingPage title="MARGIE databases" lede="The databases MARGIE builds from the genomes she annotates." shade="page-databases">
	<section class="rp-sec" id="release">
		<h2>The first release</h2>
		<p class="rp-lead"><b>{DATABASES.soon}</b></p>
		<p>{DATABASES.about}</p>
		<ul>
			{#each DATABASES.holds as h (h)}<li>{h}</li>{/each}
		</ul>
		<p class="rp-note">Questions about the databases go to the {LAB.name}: <a href="mailto:{LAB.email}?subject=MARGIE-DATABASES">{LAB.email}</a>.</p>
	</section>
</ReadingPage>
