<script lang="ts">
	import { ArrowRight, Gauge, Lightbulb, LockKeyhole } from 'lucide-svelte';
	import FaqList from '$lib/crisp/FaqList.svelte';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';

	/**
	 * FAQ: how MARGIE works, question by question (FaqList), on its own page so Methods stays short.
	 * Opened from the sidebar and from Methods; a link to /faq#<question id> opens that question.
	 */
</script>

<svelte:head><title>FAQ | MARGIE</title></svelte:head>

<ReadingPage title="Frequently asked questions" lede="How each step works, with the papers it rests on and the code that does it." shade="page-faq">
	<div class="rp-pair">
		<a class="rp-link" href="/methods/scores">
			<span class="rp-link-icon"><Gauge size={24} /></span>
			<span class="rp-link-text">
				<b>Reading the scores</b>
				<span>C3's two channels, the genome pool, the tiers and the check against EcoCyc. Opens with a password the lab gives on request.</span>
			</span>
			<LockKeyhole size={18} />
		</a>
		<a class="rp-link" href="/quiz?topic=margie">
			<span class="rp-link-icon"><Lightbulb size={24} /></span>
			<span class="rp-link-text">
				<b>MARGIE quiz</b>
				<span>Questions on what MARGIE does, from first steps to the scoring, at three levels.</span>
			</span>
			<ArrowRight size={18} />
		</a>
	</div>
	<FaqList />
</ReadingPage>
