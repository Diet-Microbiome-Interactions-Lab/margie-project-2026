<script lang="ts">
	import ClusterBoard from '$lib/crisp/ClusterBoard.svelte';
</script>

<svelte:head><title>Resources | MARGIE</title></svelte:head>

<div class="cr-page" data-shade="page-cluster">
	<div class="cr-head">
		<h1 class="cr-title">Resources</h1>
		<p class="cr-lede mg-explain">What SLURM gives your account: where you are, your jobs, your group's allocation and what is in use, and each partition's free CPUs and memory.</p>
	</div>

	<ClusterBoard />
</div>
