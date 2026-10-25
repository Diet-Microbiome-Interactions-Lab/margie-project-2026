<script lang="ts">
	import { transfers } from '$lib/cluster/transfers.svelte';

	/**
	 * How far a wait has got: the bytes arrived and the time left while a file is read from the
	 * cluster (transfers), or, while the server reads it for us, an estimate from the file's size and
	 * the speed of earlier reads. With neither, the seconds so far.
	 */
	let { label, path = '', size = 0 }: { label: string; path?: string; size?: number } = $props();

	const opened = Date.now();
	let now = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (now = Date.now()), 250);
		return () => clearInterval(t);
	});

	const live = $derived(transfers.find(path));
	const total = $derived(live?.total || size);
	const counted = $derived(!!live?.total);
	const elapsed = $derived(Math.max(0.001, (now - (live?.started ?? opened)) / 1000));
	const rate = $derived(live && live.loaded > 0 && elapsed > 0.8 ? live.loaded / elapsed : transfers.rate);
	/** Bytes in hand: counted while the file arrives, estimated while the server reads it. */
	const done = $derived(counted ? (live?.loaded ?? 0) : Math.min(total * 0.95, elapsed * rate));
	const fraction = $derived(total ? Math.min(1, done / total) : 0);
	const left = $derived(total ? Math.max(0, (total - done) / rate) : 0);

	const mb = (n: number) => `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)} MB`;
	const time = (s: number) => (s < 1 ? 'under a second' : s < 90 ? `${Math.ceil(s)} s` : `${Math.round(s / 60)} min`);
	const note = $derived(
		counted
			? `${mb(done)} of ${mb(total)} | about ${time(left)} left`
			: total
				? `${mb(total)} | about ${time(left)} left, estimated from earlier loads`
				: `${Math.floor(elapsed)} s so far`
	);
</script>

<div class="ldp" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={total ? Math.round(fraction * 100) : undefined}>
	<div class="ldp-top">
		<span class="ldp-label">{label}</span>
		<span class="ldp-note">{note}</span>
	</div>
	<div class="ldp-bar" class:open={!total}>
		<span style:width={total ? `${(fraction * 100).toFixed(1)}%` : undefined}></span>
	</div>
</div>

<style>
	.ldp {
		display: flex;
		flex-direction: column;
		gap: 6px;
		width: min(420px, 100%);
	}
	.ldp-top {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 4px 12px;
		font-size: var(--mg-fs-sm);
	}
	.ldp-label {
		color: var(--mg-text);
		font-weight: 600;
	}
	.ldp-note {
		color: var(--mg-text-3);
		font-variant-numeric: tabular-nums;
	}
	.ldp-bar {
		position: relative;
		height: 6px;
		overflow: hidden;
		border-radius: 3px;
		background: color-mix(in srgb, var(--mg-text) 10%, transparent);
	}
	.ldp-bar span {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: 3px;
		background: var(--mg-accent);
		transition: width 240ms linear;
	}
	/* Size unknown: a band that runs along the bar. */
	.ldp-bar.open span {
		width: 30%;
		animation: ldp-run 1.4s ease-in-out infinite;
	}
	@keyframes ldp-run {
		from {
			left: -30%;
		}
		to {
			left: 100%;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.ldp-bar.open span {
			animation: none;
			width: 100%;
			opacity: 0.4;
		}
	}
</style>
