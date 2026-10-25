<script lang="ts">
	import '$lib/crisp/about.css';
	import { ArrowLeft, ArrowRight, Gauge, LockKeyhole } from 'lucide-svelte';
	import FaqList from '$lib/crisp/FaqList.svelte';

	/**
	 * FAQ: how MARGIE works, question by question (FaqList), on its own page so Methods stays short.
	 * Opened from the sidebar and from Methods; a link to /faq#<question id> opens that question.
	 */
</script>

<svelte:head><title>FAQ | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-faq">
	<div class="cr-head">
		<a class="mg-link fq-back" href="/methods"><ArrowLeft size={14} /> Methods</a>
		<h1 class="cr-title">Frequently asked questions</h1>
		<p class="cr-lede">How each step works, with the papers it rests on and the code that does it.</p>
	</div>

	<div class="ab fq-read">
		<a class="ab-go" href="/methods/scores">
			<Gauge size={26} />
			<span class="ab-go-text">
				<b>Reading the scores</b>
				<span>C3's two channels | the genome pool it compares against | what each tier means | a gene scored in five genomes | the check against EcoCyc. Opens with a password the lab gives on request.</span>
			</span>
			<span class="ab-go-to"><LockKeyhole size={14} /> Open <ArrowRight size={15} /></span>
		</a>
		<FaqList />
	</div>
</div>

<style>
	.fq-back {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: var(--mg-fs-sm);
	}
	/* Reading size, as on Methods (both follow Customize → text size). */
	.fq-read :global(.ab-box) {
		font-size: var(--mg-fs-lg);
		line-height: 1.65;
	}
	.fq-read :global(.ab-go-text) {
		font-size: var(--mg-fs);
	}
</style>
