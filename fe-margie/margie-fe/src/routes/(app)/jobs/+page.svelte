<script lang="ts">
	import { Eraser } from 'lucide-svelte';
	import JobsBoard from '$lib/crisp/JobsBoard.svelte';
	import RefreshButton from '$lib/workspace/blocks/RefreshButton.svelte';
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

	/** Finished jobs leave the list after a backup of it is saved; running ones stay. */
	const finished = $derived(ws.runs.length - ws.running.length);
	let clearing = $state(false);
	async function clearHistory() {
		const sure = confirm(
			`Clear the job history?\n\n${finished} finished job${finished === 1 ? '' : 's'} will leave this list. A backup of the list is saved first, ` +
				'in your working folder (job-history-backups). Jobs still running stay.\n\n' +
				'Results, run folders and the cached tool results in your MARGIE database are not touched.'
		);
		if (!sure) return;
		clearing = true;
		await ws.clearRuns();
		clearing = false;
	}
</script>

<svelte:head><title>Jobs | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-runs">
	<div class="cr-head">
		<h1 class="cr-title">Jobs</h1>
		<p class="cr-lede">{ws.runs.length ? counts : 'Every job started from MARGIE, with its log.'}</p>
		<div class="cr-head-acts">
			{#if finished}
				<button type="button" class="mg-btn small" disabled={clearing} title="Back up the job list, then clear the finished jobs from it" onclick={clearHistory}>
					<Eraser size={14} />{clearing ? 'Clearing…' : 'Clear history'}
				</button>
			{/if}
			<RefreshButton title="Read the jobs again" run={() => ws.loadRuns()} />
		</div>
	</div>

	<JobsBoard />
</div>
