<script lang="ts">
	import JobsBoard from '$lib/crisp/JobsBoard.svelte';
	import { ws } from '$lib/workspace/data.svelte';

	const count = (status: string) => ws.runs.filter((r) => r.status === status).length;
	/** "2 running | 12 finished | 22 failed | 16 stopped", leaving out what is zero. */
	const counts = $derived(
		[
			[ws.running.length, 'running'],
			[count('completed'), 'finished'],
			[count('failed'), 'failed'],
			[count('cancelled'), 'stopped']
		]
			.filter(([n]) => n)
			.map(([n, w]) => `${n} ${w}`)
			.join(' | ')
	);
</script>

<svelte:head><title>Jobs | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-runs">
	<div class="cr-head">
		<h1 class="cr-title">Jobs</h1>
		<p class="cr-lede">{ws.runs.length ? counts : 'Every job started from MARGIE, with its log.'}</p>
	</div>

	<JobsBoard />
</div>
