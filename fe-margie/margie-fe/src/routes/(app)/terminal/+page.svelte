<script lang="ts">
	import TerminalBoard from '$lib/crisp/TerminalBoard.svelte';
</script>

<svelte:head><title>Terminal | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-terminal">
	<div class="cr-head">
		<h1 class="cr-title">Terminal</h1>
		<p class="cr-lede mg-explain">A shell on your cluster account, as on a login node. It stays open while MARGIE is open, across pages, until you Disconnect or close the site. Long work belongs in SLURM (sbatch).</p>
	</div>

	<TerminalBoard />
</div>
