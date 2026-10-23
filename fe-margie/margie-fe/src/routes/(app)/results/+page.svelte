<script lang="ts">
	import ResultsBoard from '$lib/crisp/ResultsBoard.svelte';
	import { ws } from '$lib/workspace/data.svelte';
	import RefreshButton from '$lib/workspace/blocks/RefreshButton.svelte';
</script>

<svelte:head><title>Results | MARGIE</title></svelte:head>

<div class="cr-page fill" data-shade="page-results">
	<div class="cr-head">
		<h1 class="cr-title">Results</h1>
		<span class="cr-meta">{ws.results.length ? `${ws.finished.length} of ${ws.results.length} finished` : ''}</span>
		<div class="cr-head-acts">
			<RefreshButton title="Read the results again" run={() => Promise.allSettled([ws.loadResults(), ws.loadRuns()])} />
		</div>
	</div>

	<ResultsBoard />
</div>

<style>
	/* At least the window's height; taller with the report, and the page scrolls both ways. */
	.fill {
		min-height: 100%;
		padding-bottom: 16px;
	}
</style>
