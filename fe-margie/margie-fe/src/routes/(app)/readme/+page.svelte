<script lang="ts">
	import '$lib/crisp/about.css';
	import { ArrowRight, Download, FileCode, MonitorDown } from 'lucide-svelte';
	import { DESKTOP_URL } from '$lib/crisp/about';
	import README from '$lib/crisp/readme.md?raw';
	import Markdown from '$lib/workspace/viewers/Markdown.svelte';

	/**
	 * README: what MARGIE is and how to use this site, rendered as GitHub shows a README. The
	 * code card (the Code page) stands where the README marks it, under How does MARGIE work.
	 */
	const [BEFORE, AFTER] = README.split('<!-- code-card -->');
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
		<section class="ab-box readme">
			<Markdown source={BEFORE} />
			{#if AFTER !== undefined}
				<a class="ab-go" href="/code">
					<FileCode size={26} />
					<span class="ab-go-text">
						<b>Read the code behind each step</b>
						<span>Consolidation | Labeling | Operon database | Scoring | Fingerprinting | Fingerprint databases: the Python scripts as MARGIE runs them, highlighted, with line numbers.</span>
					</span>
					<span class="ab-go-to">Open the code <ArrowRight size={15} /></span>
				</a>
				<Markdown source={AFTER} />
			{/if}
		</section>
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
	@media (max-width: 640px) {
		.readme {
			padding: 16px;
		}
	}
</style>
