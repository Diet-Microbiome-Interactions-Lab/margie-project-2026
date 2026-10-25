<script lang="ts">
	import { ArrowRight, Download, FileCode, MonitorDown } from 'lucide-svelte';
	import { DESKTOP_URL } from '$lib/crisp/about';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';
	import README from '$lib/crisp/readme.md?raw';
	import Markdown from '$lib/workspace/viewers/Markdown.svelte';

	/**
	 * README: what MARGIE is and how to use this site, one card per section of the README. The title
	 * and tagline open the page; the code card (the Code page) stands where the README marks it.
	 */
	const [HEAD, ...REST] = README.split(/^## /m);
	const TAGLINE = HEAD.match(/^\*\*(.+)\*\*$/m)?.[1] ?? '';
	const INTRO = HEAD.replace(/^# .*\n+/, '').replace(/^\*\*.+\*\*\n+/m, '');
	const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
	const SECTIONS = REST.map((chunk) => {
		const title = chunk.slice(0, chunk.indexOf('\n')).trim();
		return { title, id: slug(title), parts: chunk.slice(chunk.indexOf('\n') + 1).split('<!-- code-card -->') };
	});

	function download() {
		const url = URL.createObjectURL(new Blob([README], { type: 'text/markdown' }));
		const a = Object.assign(document.createElement('a'), { href: url, download: 'MARGIE-README.md' });
		document.body.append(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 10_000);
	}
</script>

<svelte:head><title>README | MARGIE</title></svelte:head>

<ReadingPage title="MARGIE" lede={TAGLINE} shade="page-readme">
	{#snippet actions()}
		<a class="mg-btn small" href={DESKTOP_URL} target="_blank" rel="noreferrer"><MonitorDown size={14} /> Desktop app</a>
		<button type="button" class="mg-btn small" onclick={download}><Download size={14} /> README.md</button>
	{/snippet}

	<section class="rp-sec" id="about" data-toc="About MARGIE">
		<h2>About MARGIE</h2>
		<Markdown source={INTRO} />
	</section>

	{#each SECTIONS as s (s.id)}
		<section class="rp-sec" id={s.id} data-toc={s.title}>
			<h2>{s.title}</h2>
			{#each s.parts as part, k (k)}
				{#if k > 0}
					<a class="rp-link" href="/code">
						<span class="rp-link-icon"><FileCode size={24} /></span>
						<span class="rp-link-text">
							<b>The code behind each step</b>
							<span>Consolidation | Labeling | Operon database | Scoring | Fingerprinting | Fingerprint databases | Genome map | Reports</span>
						</span>
						<ArrowRight size={18} />
					</a>
				{/if}
				{#if part.trim()}<Markdown source={part} />{/if}
			{/each}
		</section>
	{/each}
</ReadingPage>
