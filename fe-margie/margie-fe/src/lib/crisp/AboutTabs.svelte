<script lang="ts">
	import { page } from '$app/state';

	/** The four About pages as one place: a tab for each, above the page's own title. */
	const TABS = [
		{ href: '/methods', label: 'Methods' },
		{ href: '/readme', label: 'README' },
		{ href: '/contributors', label: 'Contributors and citing' },
		{ href: '/acknowledgements', label: 'Acknowledgements' }
	];
</script>

<nav class="about-tabs" aria-label="About MARGIE">
	{#each TABS as t (t.href)}
		<a href={t.href} aria-current={page.url.pathname === t.href ? 'page' : undefined}>{t.label}</a>
	{/each}
</nav>

<style>
	.about-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		padding: 3px;
		align-self: flex-start;
		border: 1px solid var(--mg-border);
		border-radius: var(--mg-r-sm);
		background: var(--cr-card, var(--mg-surface));
	}
	.about-tabs a {
		padding: 5px 12px;
		border-radius: calc(var(--mg-r-sm) - 2px);
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
		text-decoration: none;
	}
	.about-tabs a:hover {
		color: var(--mg-text);
		background: color-mix(in srgb, var(--mg-text) 6%, transparent);
	}
	.about-tabs a[aria-current='page'] {
		background: var(--mg-accent);
		color: var(--mg-on-accent, #fff);
	}
</style>
