<script lang="ts">
	import { ArrowRight, LockKeyhole } from 'lucide-svelte';
	import FaqList from '$lib/crisp/FaqList.svelte';
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';
	import { HOSTED } from '$lib/hosted';

	/**
	 * FAQ: how MARGIE works, question by question (FaqList), on its own page so Methods stays short.
	 * Opened from the sidebar and from Methods; a link to /faq#<question id> opens that question.
	 * The desktop app has no code or locked pages, so its FAQ has neither.
	 */
</script>

<svelte:head><title>FAQ | MARGIE</title></svelte:head>

{#snippet quiz()}
	<a class="rp-link" href="/quiz?topic=margie">
		<span class="rp-link-text">
			<b>MARGIE quiz</b>
			<span>Questions on what MARGIE does, from first steps to the scoring, at three levels.</span>
		</span>
		<ArrowRight size={20} />
	</a>
{/snippet}

<ReadingPage
	title="Frequently asked questions"
	lede="How each step works, with the papers it rests on{HOSTED ? ' and the code that does it' : ''}."
	shade="page-faq"
>
	{#if HOSTED}
		<div class="rp-pair">
			<a class="rp-link" href="/methods/scores">
				<span class="rp-link-text">
					<b>Reading the scores</b>
					<span>C3's two channels, the genome pool, the tiers and the check against EcoCyc. Opens with a password the lab gives on request.</span>
				</span>
				<LockKeyhole size={20} />
			</a>
			{@render quiz()}
		</div>
	{:else}
		{@render quiz()}
	{/if}
	<FaqList />
</ReadingPage>
