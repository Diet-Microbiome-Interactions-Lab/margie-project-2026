<script lang="ts">
	import { onMount } from 'svelte';
	import { Cpu, MapPin, RefreshCw, Users } from 'lucide-svelte';
	import { api } from '$lib/api';
	import { uiBase } from '$lib/workspace/base.svelte';

	/**
	 * Cluster → Resources: SLURM as the user sees it (GET /v1/ssh/cluster_resources): where the
	 * site's commands run, the user's jobs, each account's group
	 * allocation and what is in use, and every partition's free CPUs and memory. Refreshes
	 * every 30 seconds while open.
	 */
	type Tres = Record<string, number>;
	interface Job {
		id: string;
		name: string;
		partition: string;
		state: string;
		time: string;
		limit: string;
		nodes: string;
		cpus: string;
		nodelist: string;
		reason: string;
		account: string;
		interactive: boolean;
	}
	interface Account {
		name: string;
		partitions: string[];
		qos: string[];
		max_jobs: string;
		max_submit: string;
		limits: Tres;
		group_jobs: string;
		in_use: Tres;
		mine: Tres;
		running: number;
		my_running: number;
		/** Who is using the account now: running jobs and what they hold, and jobs waiting. */
		users?: { user: string; me: boolean; running: number; cpu: number; mem: number; gpu: number; waiting: number; waiting_cpu: number }[];
	}
	interface Partition {
		name: string;
		default: boolean;
		up: boolean;
		time_limit: string;
		nodes: number;
		cpus: { allocated: number; idle: number; other: number; total: number };
		mem_per_node_mb: number;
		gres: string;
		node_states: Record<string, number>;
		cpus_ready: number;
		mem_free_mb: number;
		mem_total_mb: number;
	}
	interface Qos {
		name: string;
		group: string;
		per_user: string;
		jobs_per_user: string;
		max_wall: string;
	}
	interface Resources {
		host: string;
		on_login_node: boolean;
		jobs: Job[];
		interactive: Job[];
		accounts: Account[];
		qos: Qos[];
		partitions: Partition[];
	}

	let data = $state<Resources | null>(null);
	let error = $state('');
	let loading = $state(false);
	let at = $state(0);
	let now = $state(Date.now());

	async function load() {
		loading = true;
		try {
			data = await api<Resources>('/cluster/resources');
			error = '';
			at = Date.now();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		load();
		const poll = setInterval(() => document.visibilityState === 'visible' && load(), 30_000);
		const tick = setInterval(() => (now = Date.now()), 5_000);
		return () => (clearInterval(poll), clearInterval(tick));
	});

	/** Memory from MB, in GB or TB. */
	function mem(mb: number): string {
		if (mb >= 1024 * 1024) return `${(mb / 1024 / 1024).toFixed(1)} TB`;
		if (mb >= 1024) return `${Math.round(mb / 1024).toLocaleString('en-US')} GB`;
		return `${Math.round(mb)} MB`;
	}
	/** A resource's plain name: CPUs, Memory, GPUs, or the cluster's own name for it. */
	const LABEL: Record<string, string> = { cpu: 'CPUs', mem: 'Memory', 'gres/gpu': 'GPUs', node: 'Nodes', billing: 'Billing' };
	const label = (key: string) => LABEL[key] ?? key.replace(/^gres\//, '');
	const amount = (key: string, n: number) => (key === 'mem' ? mem(n) : Math.round(n).toLocaleString('en-US'));
	const pct = (part: number, whole: number) => (whole > 0 ? Math.min(100, Math.max(0, (part / whole) * 100)) : 0);

	const running = $derived(data?.jobs.filter((j) => j.state === 'RUNNING').length ?? 0);
	const pending = $derived(data?.jobs.filter((j) => j.state === 'PENDING').length ?? 0);
	/** Partitions the user's accounts may use; an account with none listed may use them all. */
	const yours = $derived.by(() => {
		const named = data?.accounts.flatMap((a) => a.partitions) ?? [];
		const all = !data?.accounts.length || data.accounts.some((a) => !a.partitions.length);
		return (name: string) => all || named.includes(name);
	});
	const DOWN = ['down', 'drained', 'draining', 'drain', 'maint', 'fail', 'failing', 'planned', 'unknown', 'not_responding'];
	const downOf = (p: Partition) => Object.entries(p.node_states).reduce((n, [s, c]) => n + (DOWN.includes(s) ? c : 0), 0);
	const statesOf = (p: Partition) => Object.entries(p.node_states).map(([s, c]) => `${c} ${s}`).join(', ');
	const qosOf = (name: string) => data?.qos.find((q) => q.name === name);
	const ago = $derived(at ? Math.max(0, Math.round((now - at) / 1000)) : 0);
</script>

<div class="cb">
	{#if error && !data}
		<p class="cb-bad">{error}</p>
	{:else if !data}
		<p class="mg-note">Asking SLURM…</p>
	{:else}
		<!-- Where the site works, and any shell on a compute node. -->
		<section class="cb-strip" aria-label="Where you are">
			<div class="cb-where">
				<MapPin size={16} />
				<div>
					<b>{data.on_login_node ? 'Login node' : 'Node'} <span class="mg-mono">{data.host.split('.')[0]}</span></b>
					<span class="mg-note">The site's commands and the Terminal start here; runs go to compute nodes through SLURM.</span>
				</div>
			</div>
			<div class="cb-counts">
				<span><b>{running}</b> running</span>
				<span><b>{pending}</b> waiting</span>
				<button type="button" class="mg-btn small" onclick={load} disabled={loading} title="Ask SLURM again"><RefreshCw size={13} class={loading ? 'mg-spin' : ''} />{ago ? `${ago}s ago` : 'Now'}</button>
			</div>
		</section>
		{#if error}<p class="cb-bad">{error} (showing the last answer)</p>{/if}

		<!-- Each account: the group's allocation and what is in use. -->
		{#each data.accounts as a (a.name)}
			<section class="cb-card" aria-label="Account {a.name}">
				<header>
					<Users size={15} />
					<h2>Account <span class="mg-mono">{a.name}</span></h2>
					<span class="mg-note">{a.running} running in the group, {a.my_running} yours</span>
					<span class="mg-grow"></span>
					{#each a.qos as q (q)}
						{@const info = qosOf(q)}
						<span class="cb-chip" title={info?.max_wall ? `Longest job: ${info.max_wall}` : 'No time limit of its own'}>{q}{info?.max_wall ? ` | ${info.max_wall}` : ''}</span>
					{/each}
				</header>
				<div class="cb-bars">
					{#each Object.entries(a.limits) as [key, limit] (key)}
						{@const used = a.in_use[key] ?? 0}
						{@const mine = a.mine[key] ?? 0}
						<div class="cb-bar">
							<div class="cb-bar-head">
								<b>{label(key)}</b>
								<span><b>{amount(key, Math.max(0, limit - used))}</b> left of {amount(key, limit)}</span>
							</div>
							<div class="cb-meter" role="meter" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={used} aria-label="{label(key)} in use">
								<i class="mine" style="width: {pct(mine, limit)}%"></i><i class="others" style="width: {pct(used - mine, limit)}%"></i>
							</div>
							<span class="mg-note">{amount(key, used)} in use, {amount(key, mine)} by you</span>
						</div>
					{:else}
						<p class="mg-note">No group limit is set for this account; the partitions' own limits apply.</p>
					{/each}
					{#if a.users?.length}
						<div class="cb-who">
							<span class="cb-who-h">Using it now</span>
							<ul>
								{#each a.users as u (u.user)}
									<li class:me={u.me}>
										<b class="mg-mono">{u.user}</b>{#if u.me}<span class="mg-note">you</span>{/if}
										<span class="cb-who-what">
											{u.running
												? `${u.running} running | ${amount('cpu', u.cpu)} CPUs | ${mem(u.mem)}${u.gpu ? ` | ${u.gpu} GPU${u.gpu === 1 ? '' : 's'}` : ''}`
												: 'nothing running'}{u.waiting ? ` | ${u.waiting} waiting (${amount('cpu', u.waiting_cpu)} CPUs)` : ''}
										</span>
									</li>
								{/each}
							</ul>
						</div>
					{:else}
						<p class="mg-note">Nobody has a job running or waiting in this account right now.</p>
					{/if}
					{#if !Object.keys(a.limits).includes('cpu') || !Object.keys(a.limits).includes('mem')}
						<div class="cb-inuse">
							<span>In use now: <b>{amount('cpu', a.in_use.cpu ?? 0)}</b> CPUs, <b>{mem(a.in_use.mem ?? 0)}</b> memory{a.in_use['gres/gpu'] ? `, ${a.in_use['gres/gpu']} GPUs` : ''}</span>
							<span class="mg-note">yours: {amount('cpu', a.mine.cpu ?? 0)} CPUs, {mem(a.mine.mem ?? 0)}</span>
							{#if a.max_jobs || a.max_submit}<span class="mg-note">Up to {a.max_jobs || '∞'} running and {a.max_submit || '∞'} queued jobs each</span>{/if}
						</div>
					{/if}
				</div>
			</section>
		{/each}

		<!-- The user's jobs. -->
		<section class="cb-card" aria-label="Your jobs">
			<header><Cpu size={15} /><h2>Your jobs</h2><span class="mg-note">{data.jobs.length ? `${data.jobs.length} in SLURM` : 'None in SLURM right now'}</span></header>
			{#if data.jobs.length}
				<div class="cb-scroll">
					<table class="cb-table">
						<thead><tr><th>Job</th><th>Name</th><th>Partition</th><th>State</th><th>Time</th><th class="num">CPUs</th><th>Node or reason</th></tr></thead>
						<tbody>
							{#each data.jobs as j (j.id)}
								<tr>
									<td class="mg-mono">{j.id}</td>
									<td class="name" title={j.name}>{j.name}{#if j.interactive}<span class="cb-chip">interactive</span>{/if}</td>
									<td>{j.partition}</td>
									<td><span class="cb-state" data-state={j.state.toLowerCase()}>{j.state.toLowerCase()}</span></td>
									<td class="mg-mono">{j.time} / {j.limit}</td>
									<td class="num">{j.cpus}</td>
									<td class="mg-mono">{j.state === 'RUNNING' ? j.nodelist : j.reason}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<!-- Every partition: free CPUs and memory now. -->
		<section class="cb-card" aria-label="Partitions">
			<header><Cpu size={15} /><h2>Partitions</h2><span class="mg-note">Free now, on nodes that take jobs</span></header>
			<div class="cb-scroll">
				<table class="cb-table">
					<thead>
						<tr><th>Partition</th><th>Time limit</th><th>Nodes</th><th>CPUs free</th><th>Memory free</th><th>Per node</th><th>Extras</th></tr>
					</thead>
					<tbody>
						{#each data.partitions as p (p.name)}
							{@const down = downOf(p)}
							<tr class:off={!p.up || !yours(p.name)}>
								<td><b>{p.name}</b>{#if p.default}<span class="cb-chip">default</span>{/if}{#if !p.up}<span class="cb-chip bad">down</span>{:else if !yours(p.name)}<span class="cb-chip">not your account's</span>{/if}</td>
								<td class="mg-mono">{p.time_limit}</td>
								<td title={statesOf(p)}>{p.nodes}{#if down}<span class="cb-down">({down} out)</span>{/if}</td>
								<td>
									<div class="cb-cell">
										<span><b>{p.cpus.idle.toLocaleString('en-US')}</b> of {p.cpus.total.toLocaleString('en-US')}</span>
										<div class="cb-meter small"><i class="free" style="width: {pct(p.cpus.idle, p.cpus.total)}%"></i></div>
									</div>
								</td>
								<td>
									<div class="cb-cell">
										<span><b>{mem(p.mem_free_mb)}</b> of {mem(p.mem_total_mb)}</span>
										<div class="cb-meter small"><i class="free" style="width: {pct(p.mem_free_mb, p.mem_total_mb)}%"></i></div>
									</div>
								</td>
								<td class="mg-mono">{mem(p.mem_per_node_mb)}</td>
								<td class="mg-mono">{p.gres || '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}
</div>

<style>
	.cb {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.cb-bad {
		color: var(--mg-danger);
	}
	.cb-strip {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.2fr) auto;
		gap: 0;
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		overflow: hidden;
	}
	.cb-where {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		padding: 12px 16px;
		border-right: 1px solid var(--cr-card-edge, var(--mg-border));
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.cb-where > div {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
		color: var(--mg-text);
	}
	.cb-counts {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 12px 16px;
		color: var(--mg-text-2);
		white-space: nowrap;
	}
	.cb-counts b {
		color: var(--mg-text);
		font-size: 1.15em;
	}
	.cb-who {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.cb-who-h {
		font-size: var(--mg-fs-xs);
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--mg-text-3);
	}
	.cb-who ul {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 0;
		list-style: none;
	}
	.cb-who li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 10px;
		padding: 5px 8px;
		border-radius: var(--mg-r-sm);
	}
	.cb-who li.me {
		background: color-mix(in srgb, var(--mg-accent) 8%, transparent);
	}
	.cb-who-what {
		color: var(--mg-text-2);
		font-size: var(--mg-fs-sm);
		font-variant-numeric: tabular-nums;
	}
	.cb-card {
		border: 1px solid var(--cr-card-edge, var(--mg-border));
		border-radius: var(--mg-r);
		background: var(--cr-card, var(--mg-surface));
		overflow: hidden;
	}
	.cb-card > header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		padding: 10px 16px;
		border-bottom: 1px solid var(--cr-card-edge, var(--mg-border));
		color: var(--mg-accent-ink, var(--mg-accent));
	}
	.cb-card h2 {
		font-size: var(--cr-fs-meta, 13px);
		font-weight: 650;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--mg-text);
	}
	.cb-chip {
		display: inline-block;
		margin-left: 6px;
		padding: 1px 7px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--mg-accent) 12%, transparent);
		color: var(--mg-accent-ink, var(--mg-accent));
		font-size: var(--mg-fs-xs, 11px);
		font-weight: 600;
		white-space: nowrap;
	}
	.cb-chip.bad {
		background: color-mix(in srgb, var(--mg-danger) 14%, transparent);
		color: var(--mg-danger);
	}
	.cb-bars {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 14px 24px;
		padding: 14px 16px;
	}
	.cb-bar {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.cb-bar-head {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		color: var(--mg-text-2);
	}
	.cb-bar-head b {
		color: var(--mg-text);
	}
	.cb-meter {
		display: flex;
		height: 10px;
		border-radius: 999px;
		background: var(--mg-surface-2);
		overflow: hidden;
	}
	.cb-meter.small {
		height: 6px;
		max-width: 160px;
	}
	.cb-meter i {
		display: block;
		height: 100%;
		transition: width var(--mo-2, 300ms) ease;
	}
	.cb-meter .mine {
		background: var(--mg-accent);
	}
	.cb-meter .others {
		background: color-mix(in srgb, var(--mg-accent) 40%, var(--mg-surface-2));
	}
	.cb-meter .free {
		background: var(--mg-ok);
	}
	.cb-inuse {
		display: flex;
		flex-direction: column;
		gap: 3px;
		color: var(--mg-text-2);
	}
	.cb-inuse b {
		color: var(--mg-text);
	}
	.cb-scroll {
		overflow-x: auto;
	}
	.cb-table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--cr-fs-meta, 13px);
	}
	.cb-table th {
		padding: 8px 16px;
		background: var(--mg-surface-2);
		color: var(--mg-text-3);
		font-weight: 600;
		text-align: left;
		white-space: nowrap;
	}
	.cb-table td {
		padding: 8px 16px;
		border-top: 1px solid var(--mg-border);
		vertical-align: middle;
		white-space: nowrap;
	}
	.cb-table .num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.cb-table .name {
		max-width: 260px;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.cb-table tr.off td {
		color: var(--mg-text-3);
	}
	.cb-cell {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.cb-down {
		margin-left: 5px;
		color: var(--mg-warn);
	}
	.cb-state {
		font-weight: 600;
		color: var(--mg-text-3);
	}
	.cb-state[data-state='running'] {
		color: var(--mg-ok);
	}
	.cb-state[data-state='pending'] {
		color: var(--mg-warn);
	}
	@media (max-width: 900px) {
		.cb-strip {
			grid-template-columns: minmax(0, 1fr);
		}
		.cb-where {
			border-right: none;
			border-bottom: 1px solid var(--cr-card-edge, var(--mg-border));
		}
	}
</style>
