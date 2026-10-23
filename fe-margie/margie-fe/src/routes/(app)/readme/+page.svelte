<script lang="ts">
	import '$lib/crisp/about.css';
	import { Download, MonitorDown } from 'lucide-svelte';
	import { DESKTOP_URL } from '$lib/crisp/about';
	import README from '$lib/crisp/readme.md?raw';
	import Markdown from '$lib/workspace/viewers/Markdown.svelte';

	/** README: what MARGIE is and how to use this site, rendered as GitHub shows a README. */
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

<div class="cr-page" data-shade="page-readme">
	<div class="cr-head">
		<h1 class="cr-title">README</h1>
		<div class="cr-head-acts acts">
			<a class="mg-btn small" href={DESKTOP_URL} target="_blank" rel="noreferrer"><MonitorDown size={14} /> Desktop app</a>
			<button type="button" class="mg-btn small" onclick={download}><Download size={14} /> README.md</button>
		</div>
	</div>

	<div class="ab">
		<section class="ab-box readme"><Markdown source={README} /></section>
	</div>
</div>

<style>
	.acts {
		display: flex;
		gap: 8px;
	}
	.readme {
		padding: 22px 30px 28px;
		font-size: var(--mg-fs);
	}
</style>
