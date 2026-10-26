<script lang="ts">
	import { DATABASES, LAB } from '$lib/crisp/about';

	/** The MARGIE databases and what their first release holds: the databases page, and the sign-in page's popup. */
</script>

<p class="rp-lead dbi-lead"><b>{DATABASES.soon}</b></p>
<p>{DATABASES.about}</p>
<ul class="dbi-list">
	{#each DATABASES.holds as h (h)}<li>{h}</li>{/each}
</ul>
<p class="rp-note">Questions about the databases go to the {LAB.name}: <a href="mailto:{LAB.email}?subject=MARGIE-DATABASES">{LAB.email}</a>.</p>
