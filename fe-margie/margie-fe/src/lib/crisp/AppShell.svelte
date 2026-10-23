<script lang="ts">
	/**
	 * The site's frame, in the look of Dane's original pages (lib/Navibar.svelte in biolab-fe):
	 * Skeleton's app bar with the menu button, the home link and the account on the right,
	 * a side drawer of pages, and every colour from the Skeleton theme on <html>. Under the
	 * bar, the pages as tabs; around the page, MARGIE's own parts (running job, help text,
	 * genome drop, install check, guided steps, Customize, notices).
	 */
	import type { Snippet } from 'svelte';
	import { cubicOut } from 'svelte/easing';
	import { fade, fly } from 'svelte/transition';
	import { page } from '$app/state';
	import { BookOpen, ChartPie, Eye, FolderOpen, Gauge, House, ListChecks, LogOut, Menu, MonitorDown, Package, Palette, Play, SlidersHorizontal, SquareTerminal, UserRound, Users, X } from 'lucide-svelte';
	import { DESKTOP_URL } from './about';
	import { AppBar } from '@skeletonlabs/skeleton-svelte';
	import avatar from '$lib/assets/neuromancer.jpg';
	import RunRing from '$lib/crisp/RunRing.svelte';
	import GenomeDrop from '$lib/workspace/GenomeDrop.svelte';
	import InstallGate from '$lib/workspace/blocks/InstallGate.svelte';
	import Field from '$lib/workspace/Field.svelte';
	import Seg from '$lib/workspace/Seg.svelte';
	import AppearanceControls from '$lib/workspace/AppearanceControls.svelte';
	import { SHADE_NAMES, SHADE_ORDER } from '$lib/workspace/shades';
	import Switch from '$lib/workspace/Switch.svelte';
	import ThemeEditor from '$lib/workspace/ThemeEditor.svelte';
	import { presetChange, PRESETS } from '$lib/workspace/themes';
	import VisionControls from '$lib/workspace/VisionControls.svelte';
	import VisionFilters from '$lib/workspace/VisionFilters.svelte';
	import Resizer from '$lib/workspace/motion/Resizer.svelte';
	import { uiBase } from '$lib/workspace/base.svelte';
	import { backend } from '$lib/workspace/backend.svelte';
	import { clusterParts } from '$lib/workspace/cluster-parts';
	import { ws } from '$lib/workspace/data.svelte';
	import { pageMotion } from '$lib/workspace/motion/page';
	import { thumb } from '$lib/workspace/motion/thumb';
	import { preview, visionAttrs } from '$lib/workspace/preview.svelte';
	import { styleString, type UiPrefs } from '$lib/workspace/prefs';
	import { ui } from '$lib/workspace/ui.svelte';
	import { visionInfo } from '$lib/workspace/vision';
	import { crispVars } from './theme';
	import { skeletonFromPalette, skeletonVars, statusFromVision } from './skeleton-theme';
	import { SKINS, skin } from './skin.svelte';
	import GuideBar from './GuideBar.svelte';
	import Notices from './Notices.svelte';

	let { children }: { children: Snippet } = $props();

	uiBase.set('');

	/** The pages, in the order work goes: annotate and follow it up, set up the cluster, your account. */
	const GROUPS = [
		{
			name: 'Annotate',
			items: [
				{ href: '/analyze', label: 'Analyze', icon: Play, note: 'Add genomes, choose the tools, start a run' },
				{ href: '/jobs', label: 'Jobs', icon: ListChecks, note: 'Progress and the log of every run' },
				{ href: '/results', label: 'Results', icon: ChartPie, note: 'Annotations, maps and reports' },
				{ href: '/files', label: 'Files', icon: FolderOpen, note: 'Browse folders on the cluster' }
			]
		},
		{
			name: 'Cluster',
			items: [
				{ href: '/install', label: 'Install', icon: Package, note: 'Tools, databases and the licence' },
				{ href: '/cluster', label: 'Resources', icon: Gauge, note: 'SLURM: your accounts, jobs, partitions and memory' },
				{ href: '/terminal', label: 'Terminal', icon: SquareTerminal, note: 'A shell on your cluster account' }
			]
		},
		{
			name: 'Account',
			items: [
				{ href: '/settings', label: 'Settings', icon: SlidersHorizontal, note: 'Folders, cores and the steps a run takes' },
				{ href: '/profile', label: 'User profile', icon: UserRound, note: 'Your details, cluster account and SSH key' }
			]
		}
	];
	/** About MARGIE (its four pages share one entry and a tab bar, AboutTabs), and the desktop app's download page. */
	const ABOUT_PAGES = ['/methods', '/readme', '/contributors', '/acknowledgements'];
	const ABOUT: { href: string; label: string; icon: typeof Users; external?: boolean }[] = [
		{ href: '/methods', label: 'About MARGIE', icon: BookOpen },
		{ href: DESKTOP_URL, label: 'Desktop app', icon: MonitorDown, external: true }
	];
	const aboutCurrent = (href: string) => (href === '/methods' ? ABOUT_PAGES.some((p) => current(p)) : current(href));

	/*
	 * The sidebar: the pages down the left, under the bar. The menu button folds it to its
	 * icons (remembered in this browser); on a narrow window it hides, and the button opens
	 * the drawer instead.
	 */
	const RAIL_KEY = 'margie.sidebar';
	let railShut = $state(false);
	try {
		railShut = localStorage.getItem(RAIL_KEY) === 'shut';
	} catch {
		// Not kept: it opens unfolded.
	}
	const narrow = () => matchMedia('(max-width: 820px)').matches;
	function menuButton() {
		if (narrow()) {
			menuOpen = !menuOpen;
			return;
		}
		railShut = !railShut;
		try {
			localStorage.setItem(RAIL_KEY, railShut ? 'shut' : 'open');
		} catch {
			// Not kept.
		}
	}

	/** Simple shows the pages alone; Guided adds the step bar, a tip for each page and all the help text. */
	function setMode(mode: 'clean' | 'guided') {
		ui.update({ mode, welcomed: true });
		if (mode === 'clean') ui.details = false;
	}

	const path = $derived(page.url.pathname.replace(/\/$/, '') || '/');
	const current = (href: string) => (href === '/' ? path === '/' : path === href || path.startsWith(`${href}/`));

	// The Skeleton theme and light or dark, on the whole page (Skeleton reads both from <html>).
	$effect(() => skin.apply(ui.dark));

	/*
	 * The look: MARGIE's own palette (Customize: presets, colours, accent, type, corners,
	 * shades), with Skeleton's tokens taken from it so Dane's parts follow; or, with the
	 * Original palette, the Skeleton theme's own colours throughout, as on Dane's pages.
	 */
	const original = $derived(ui.prefs.palette === 'skeleton');
	/** A colour vision other than typical is chosen (Customize → Vision). */
	const seeing = $derived(ui.prefs.vision !== 'typical');
	const vars = $derived(
		`${styleString({
			...crispVars(ui.prefs, ui.dark),
			...(original ? skeletonVars(ui.dark, seeing) : skeletonFromPalette(ui.dark)),
			// A colour vision chosen: its state colours win, in Skeleton's tokens too.
			...(seeing ? statusFromVision(ui.dark) : {})
		})}; ${ui.motionStyle}`
	);
	/** The palettes offered in the top bar's menu; all the others are in Customize → Colours. */
	const QUICK = ['crisp', 'glow', 'gram', 'agar', 'skeleton', 'paper', 'mint', 'slate', 'contrast'];
	const quickPresets = $derived(QUICK.map((id) => PRESETS.find((p) => p.id === id)).filter((p) => !!p));
	const palette = $derived(ui.prefs.palette || 'crisp');

	/** One line about the run going on, if any. */
	const running = $derived.by(() => {
		const a = ws.active;
		if (!a) return '';
		const p = ws.progress;
		const more = ws.running.length > 1 ? ` | ${ws.running.length} jobs` : '';
		if (p) return `${p.stage} | ${p.genomes.filter((g) => g.state === 'done').length} of ${p.genomes.length} genomes`;
		// Downloads show the percentage, or the megabytes fetched when the total is unknown.
		const what = a.kind === 'build' ? 'Building' : a.kind === 'setup' ? 'Setting up' : 'Running';
		const pct = typeof a.progress === 'number' ? ` | ${a.progress}%` : '';
		return `${what}${pct}${a.progressText ? ` | ${a.progressText}` : ''}${more}`;
	});

	// ------------------------------------------------ the drawer of pages, and the theme menu
	let menuOpen = $state(false);
	let themeOpen = $state(false);
	$effect(() => {
		void path;
		menuOpen = false;
		themeOpen = false;
	});
	const LIGHTS: [UiPrefs['theme'], string][] = [
		['light', 'Light'],
		['dark', 'Dark'],
		['system', 'System']
	];

	// ------------------------------------------------ Customize
	let drawer = $state(false);
	$effect(() => {
		if (drawer) ui.checkDefault();
	});
	let settingDefault = $state(false);
	async function setDefault() {
		settingDefault = true;
		await ui.setDefault();
		settingDefault = false;
	}
	let tab = $state<'look' | 'colours' | 'vision'>('look');
	const TABS = [
		{ id: 'look', label: 'Look' },
		{ id: 'colours', label: 'Colours' },
		{ id: 'vision', label: 'Colour vision deficiency' }
	] as const;
	function open(to: typeof tab) {
		tab = to;
		drawer = true;
	}

	let content = $state<HTMLElement>();

	pageMotion(() => content);

	const who = $derived(backend.cluster ? `Signed in as ${backend.user || 'you'} on ${backend.host || 'the cluster'}` : 'Your profile');
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key !== 'Escape') return;
		drawer = false;
		menuOpen = false;
		themeOpen = false;
	}}
/>

<div class="crisp" data-mg-root data-theme={ui.dark ? 'dark' : 'light'} data-motion={ui.motion} data-shades={original ? 'off' : ui.prefs.shades} data-palette={palette} data-help={ui.explain ? 'on' : 'off'} style={vars} {...visionAttrs()}>
	<VisionFilters />
	<GenomeDrop />
	<InstallGate />

	<AppBar class="mg-appbar">
		<AppBar.Toolbar class="grid-cols-[auto_1fr_auto]">
			<AppBar.Lead>
				<!-- Lined up with the sidebar's icons, in the same column. -->
				<button type="button" class="mg-menu btn-icon hover:preset-tonal" aria-label="Pages" title={railShut ? 'Show the page names' : 'Fold the sidebar'} onclick={menuButton}>
					<Menu size={18} />
				</button>
			</AppBar.Lead>
			<AppBar.Headline>
				<a href="/" class="mg-home inline-flex items-center align-middle gap-2 text-xl font-bold hover:text-primary-600 transition-colors" title="Home">
					<House class="size-5 shrink-0" />
					<span>MARGIE</span>
					<span class="mg-home-sub">Bioinformatics Supercomputing Platform</span>
				</a>
				<!-- Dane's beta note, as a small tag beside the name on every page. -->
				<a
					class="mg-beta"
					href="https://bioinformatics-tools.readthedocs.io/en/latest/"
					target="_blank"
					rel="noopener noreferrer"
					title="Early beta: features may change and some are still in progress. Read the docs.">Early beta</a
				>
			</AppBar.Headline>
			<AppBar.Trail class="items-center">
				{#if running && ws.active}
					<a class="mg-running btn btn-sm preset-tonal-warning" href="/jobs/{ws.active.id}" transition:fade={{ duration: ui.ms(150) }} title="Watch the log">
						<RunRing progress={ws.progress} size={20} compact />
						<span>{running}</span>
					</a>
				{/if}
				{#if backend.cluster}
					{@const c = ws.setup.find((r) => r.id === 'cluster')}
					<!-- The SSH connection, always in view: who, where, and whether it answers. -->
					<a
						class="mg-conn {c ? (c.tone === 'ok' ? 'on' : 'off') : 'wait'}"
						href="/profile"
						title={c ? (c.tone === 'ok' ? `SSH: connected to ${c.value} as ${backend.user}` : `SSH: ${c.detail}`) : 'SSH: checking the connection…'}
					>
						<span class="led" aria-hidden="true"></span>
						<span>{backend.user || 'you'}@{(c?.value || backend.host || 'cluster').split('.')[0]}</span>
					</a>
				{/if}
				<Notices />
				<!-- On a phone these move into the menu (mg-drawer-you), so the bar fits. -->
				<div class="mg-tools">
				<div class="mg-mode" role="radiogroup" aria-label="Help">
					<button type="button" role="radio" aria-checked={!ui.guided} class="btn btn-sm {!ui.guided ? 'preset-filled-primary-500' : 'hover:preset-tonal'}" title="The pages alone, without help text" onclick={() => setMode('clean')}>Simple</button>
					<button type="button" role="radio" aria-checked={ui.guided} class="btn btn-sm {ui.guided ? 'preset-filled-primary-500' : 'hover:preset-tonal'}" title="Steps across the top, a tip for each page, and all the help text" onclick={() => setMode('guided')}>Guided</button>
				</div>
				{#if ui.prefs.vision !== 'typical'}
					<button type="button" class="btn-icon btn-icon-lg preset-tonal-primary" title="Colours adjusted for {visionInfo(ui.prefs.vision).plain.toLowerCase()}" aria-label="Colour vision deficiency" onclick={() => open('vision')}>
						<Eye />
					</button>
				{/if}
				{#if backend.cluster && clusterParts.Compute}<clusterParts.Compute />{/if}
				<span class="relative">
					<button type="button" class="btn-icon btn-icon-lg hover:preset-tonal" title="Appearance: light or dark, colours, type" aria-label="Appearance" aria-expanded={themeOpen} onclick={() => (themeOpen = !themeOpen)}>
						<Palette />
					</button>
					{#if themeOpen}
						<button type="button" class="fixed inset-0 z-40 cursor-default" aria-label="Close the theme menu" onclick={() => (themeOpen = false)}></button>
						<div class="mg-theme card bg-surface-50-950 border border-surface-200-800 shadow-xl absolute right-0 top-full z-50 mt-2 w-72 p-4 space-y-4" role="dialog" aria-label="Theme" transition:fly={{ y: -6, duration: ui.ms(140) }}>
							<div class="space-y-2">
								<p class="text-xs font-bold uppercase tracking-wider opacity-60">Light or dark</p>
								<div class="grid grid-cols-3 gap-1">
									{#each LIGHTS as [value, label] (value)}
										<button type="button" class="btn btn-sm {ui.prefs.theme === value ? 'preset-filled-primary-500' : 'preset-tonal'}" aria-pressed={ui.prefs.theme === value} onclick={() => ui.update({ theme: value })}>{label}</button>
									{/each}
								</div>
							</div>
							<div class="space-y-1">
								<p class="text-xs font-bold uppercase tracking-wider opacity-60">Colours</p>
								{#each quickPresets as pr (pr.id)}
									<button type="button" class="w-full flex items-center gap-3 rounded-base px-2 py-1.5 text-left {palette === pr.id ? 'preset-tonal-primary' : 'hover:preset-tonal'}" aria-pressed={palette === pr.id} onclick={() => ui.update(presetChange(ui.prefs.colours, pr.id === 'crisp' ? '' : pr.id))}>
										<span class="mg-swatch" aria-hidden="true" style="--a: {pr.light.bg}; --b: {pr.light.surface2}; --c: {pr.light.borderStrong}"></span>
										<span class="flex-1 font-medium">{pr.name}</span>
										<span class="text-xs opacity-60 truncate max-w-32">{pr.note}</span>
									</button>
								{/each}
							</div>
							{#if original}
							<div class="space-y-1">
								<p class="text-xs font-bold uppercase tracking-wider opacity-60">Original's theme</p>
								{#each SKINS as s (s.id)}
									<button type="button" class="w-full flex items-center gap-3 rounded-base px-2 py-2 text-left {skin.id === s.id ? 'preset-tonal-primary' : 'hover:preset-tonal'}" aria-pressed={skin.id === s.id} onclick={() => skin.set(s.id)}>
										<span class="flex gap-1" data-theme={s.id} aria-hidden="true">
											<span class="size-3.5 rounded-full bg-primary-500"></span>
											<span class="size-3.5 rounded-full bg-secondary-500"></span>
											<span class="size-3.5 rounded-full bg-tertiary-500"></span>
										</span>
										<span class="flex-1 font-medium">{s.name}</span>
										{#if 'note' in s}<span class="text-xs opacity-60">{s.note}</span>{/if}
									</button>
								{/each}
							</div>
							{/if}
							<button
								type="button"
								class="btn btn-sm preset-tonal w-full"
								onclick={() => {
									themeOpen = false;
									open('colours');
								}}>Customize: colours, type and corners</button
							>
						</div>
					{/if}
				</span>
				<button type="button" class="btn-icon btn-icon-lg hover:preset-tonal" title="Sign out" aria-label="Sign out" onclick={() => backend.signOut()}>
					<LogOut />
				</button>
				</div>
			</AppBar.Trail>
		</AppBar.Toolbar>
	</AppBar>

	<!-- The drawer of pages, as on Dane's pages. -->
	{#if menuOpen}
		<button type="button" class="fixed inset-0 z-40 bg-black/50" aria-label="Close the menu" transition:fade={{ duration: ui.ms(150) }} onclick={() => (menuOpen = false)}></button>
		<nav id="mg-pages" class="mg-drawer fixed top-0 left-0 z-50 h-full w-72 overflow-y-auto bg-surface-100-900 shadow-xl" aria-label="Pages" transition:fly={{ x: -24, duration: ui.ms(180), easing: cubicOut }}>
			<div class="p-4 space-y-4">
				<div class="flex items-center justify-between">
					<h2 class="text-2xl font-bold">Menu <span class="mg-beta mg-beta-menu">Early beta</span></h2>
					<button type="button" class="btn-icon hover:preset-tonal" aria-label="Close the menu" onclick={() => (menuOpen = false)}><X /></button>
				</div>
				<a href="/" class="mg-drawer-item" aria-current={current('/') ? 'page' : undefined}>
					<House size={18} />
					<span><b>Home</b></span>
				</a>
				{#each GROUPS as g (g.name)}
					<div class="space-y-1">
						<p class="px-3 text-xs font-bold uppercase tracking-wider opacity-60">{g.name}</p>
						{#each g.items as n (n.href)}
							<a href={n.href} class="mg-drawer-item" aria-current={current(n.href) ? 'page' : undefined}>
								<n.icon size={18} />
								<span><b>{n.label}</b><small>{n.note}</small></span>
							</a>
						{/each}
					</div>
				{/each}
				<!-- On a phone: what the bar has no room for (mg-tools), with Sign out. -->
				<div class="mg-drawer-you border-t border-surface-300-700 pt-3 space-y-2">
					<p class="px-3 text-xs font-bold uppercase tracking-wider opacity-60">You</p>
					<p class="mg-you-who"><img src={avatar} alt="" class="size-6 rounded-full object-cover" /><span>{who}</span></p>
					<div class="mg-you-row">
						<div class="mg-mode" role="radiogroup" aria-label="Help">
							<button type="button" role="radio" aria-checked={!ui.guided} class="btn btn-sm {!ui.guided ? 'preset-filled-primary-500' : 'hover:preset-tonal'}" onclick={() => setMode('clean')}>Simple</button>
							<button type="button" role="radio" aria-checked={ui.guided} class="btn btn-sm {ui.guided ? 'preset-filled-primary-500' : 'hover:preset-tonal'}" onclick={() => setMode('guided')}>Guided</button>
						</div>
						<div class="mg-mode" role="radiogroup" aria-label="Light or dark">
							{#each LIGHTS as [value, label] (value)}
								<button type="button" role="radio" aria-checked={ui.prefs.theme === value} class="btn btn-sm {ui.prefs.theme === value ? 'preset-filled-primary-500' : 'hover:preset-tonal'}" onclick={() => ui.update({ theme: value })}>{label}</button>
							{/each}
						</div>
					</div>
					<div class="mg-you-row">
						<button
							type="button"
							class="btn btn-sm preset-tonal"
							onclick={() => {
								menuOpen = false;
								open('look');
							}}><SlidersHorizontal size={16} /> Customize</button
						>
						<button type="button" class="btn btn-sm preset-tonal-error" onclick={() => backend.signOut()}><LogOut size={16} /> Sign out</button>
					</div>
				</div>
				<div class="border-t border-surface-300-700 pt-3 space-y-1">
					<p class="px-3 text-xs font-bold uppercase tracking-wider opacity-60">About</p>
					{#each ABOUT as n (n.href)}
						<a href={n.href} class="mg-drawer-item" aria-current={aboutCurrent(n.href) ? 'page' : undefined} target={n.external ? '_blank' : undefined} rel={n.external ? 'noreferrer' : undefined}>
							<n.icon size={18} />
							<span><b>{n.label}</b></span>
						</a>
					{/each}
				</div>
			</div>
		</nav>
	{/if}

	<div class="mg-body">
		<nav class="mg-side" class:shut={railShut} aria-label="Pages">
			<a href="/" class="mg-side-item" aria-current={current('/') ? 'page' : undefined} title="Home">
				<House size={18} /><span>Home</span>
			</a>
			{#each GROUPS as g (g.name)}
				<p class="mg-side-h">{g.name}</p>
				{#each g.items as n (n.href)}
					<a href={n.href} class="mg-side-item" aria-current={current(n.href) ? 'page' : undefined} title={railShut ? n.label : n.note}>
						<n.icon size={18} /><span>{n.label}</span>
					</a>
				{/each}
			{/each}
			<span class="grow"></span>
			<div class="mg-side-about">
				{#each ABOUT as n (n.href)}
					<a href={n.href} class="mg-side-item small" aria-current={aboutCurrent(n.href) ? 'page' : undefined} title={n.external ? `${n.label}: download it` : n.label} target={n.external ? '_blank' : undefined} rel={n.external ? 'noreferrer' : undefined}>
						<n.icon size={15} /><span>{n.label}</span>
					</a>
				{/each}
			</div>
		</nav>
		<div class="mg-page">
			{#if ui.guided}<GuideBar />{/if}
			<main class="content" bind:this={content}>
				{@render children()}
			</main>
		</div>
	</div>

	{#if drawer}
		<button type="button" class="scrim" aria-label="Close Customize" transition:fade={{ duration: ui.ms(180) }} onclick={() => (drawer = false)}></button>
		<div class="drawer" role="dialog" aria-label="Customize" tabindex="-1" style="width: min({ui.size('crisp:drawer', 420)}px, 100%)" transition:fly={{ x: 28, duration: ui.ms(260), easing: cubicOut }}>
			<Resizer id="crisp:drawer" fallback={420} min={340} max={720} edge="left" label="Resize Customize" />
			<header>
				<span class="drawer-icon" aria-hidden="true"><SlidersHorizontal size={16} /></span>
				<h2>Customize</h2>
				<span class="grow"></span>
				<button type="button" class="btn-icon hover:preset-tonal" aria-label="Close" onclick={() => (drawer = false)}><X size={17} /></button>
			</header>
			<div class="tabs" role="tablist" aria-label="Customize" use:thumb>
				{#each TABS as t (t.id)}
					<button type="button" role="tab" aria-selected={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
				{/each}
			</div>
			<div class="drawer-body" role="tabpanel">
				{#if original && tab !== 'vision'}
					<p class="note">Original wears the Skeleton theme's own colours, type and corners. Choose another palette under Colours to set your own.</p>
				{/if}
				{#if tab === 'look'}
					<AppearanceControls />
					<section class="cr-group">
						<h3 class="cr-group-title">Page</h3>
						<Field title="Backdrop">
							<Seg label="Backdrop" value={ui.prefs.backdrop} onpick={(backdrop) => ui.update({ backdrop })} options={[{ value: 'glow', label: 'Glow' }, { value: 'plain', label: 'Plain' }]} />
						</Field>
						<Field title="Colour">
							<Seg label="Colour" value={ui.prefs.tint} onpick={(tint) => ui.update({ tint })} options={[{ value: 'plain', label: 'Plain' }, { value: 'soft', label: 'Soft' }, { value: 'strong', label: 'Strong' }]} />
						</Field>
						<Field title="Shades">
							<Seg label="Shades" value={ui.prefs.shades} onpick={(shades) => ui.update({ shades })} options={SHADE_ORDER.map((v) => ({ value: v, label: SHADE_NAMES[v] }))} />
						</Field>
						<Field title="Contrast">
							<Seg label="Contrast" value={ui.prefs.contrast} onpick={(contrast) => ui.update({ contrast })} options={[{ value: 'normal', label: 'Normal' }, { value: 'more', label: 'More' }, { value: 'high', label: 'High' }]} />
						</Field>
						<Field title="Page width">
							<Seg label="Page width" value={ui.prefs.pageWidth} onpick={(pageWidth) => ui.update({ pageWidth })} options={[{ value: 'narrow', label: 'Narrow' }, { value: 'wide', label: 'Wide' }, { value: 'full', label: 'Full' }]} />
						</Field>
						<Field title="Tables">
							<div class="line-switch">
								<span class="note">Shade every other row of long tables.</span>
								<Switch label="Shade every other row" checked={ui.prefs.stripes} onchange={(stripes) => ui.update({ stripes })} />
							</div>
						</Field>
					</section>
				{:else if tab === 'colours'}
					<ThemeEditor base="crisp" />
				{:else}
					<VisionControls base="crisp" />
				{/if}
			</div>
			<footer>
				<button type="button" class="mg-btn primary set-default" disabled={settingDefault} onclick={setDefault}>Keep these as my default</button>
				<div class="foot-line">
					<span class="saved-dot" aria-hidden="true"></span>
					<span class="note">{ui.hasDefault ? 'MARGIE opens with your default look.' : 'Changes apply now. Keep them as your default to open with them every time.'}</span>
					{#if ui.hasDefault}<button type="button" class="mg-link" onclick={() => ui.resetToDefault()}>Back to default</button>{/if}
				</div>
			</footer>
		</div>
	{/if}

	{#if preview.vision !== 'typical'}
		<div class="previewing" role="status" transition:fly={{ y: 8, duration: ui.ms(180) }}>
			<Eye size={15} />
			<span>Showing the page as seen with <b>{visionInfo(preview.vision).plain.toLowerCase()}</b></span>
			<button type="button" class="mg-link" onclick={() => (preview.vision = 'typical')}>Turn off</button>
		</div>
	{/if}

</div>

<style>
	/* Skeleton's app bar, as on Dane's pages; it stays put while the page scrolls under it.
	   Its left edge puts the menu button's icon in the sidebar icons' column (x = 29 px). */
	:global(.crisp .mg-appbar) {
		position: relative;
		z-index: 6;
		flex-shrink: 0;
		padding-left: 11px;
	}
	.mg-menu {
		width: 18px;
		height: 18px;
		padding: 9px;
	}
	.mg-home-sub {
		display: none;
		padding-left: 10px;
		margin-left: 4px;
		border-left: 1px solid var(--color-surface-300-700);
		font-size: 0.9rem;
		font-weight: 400;
		opacity: 0.7;
	}
	@media (min-width: 1100px) {
		.mg-home-sub {
			display: inline;
		}
	}
	/* The SSH connection: a dot and user@cluster, green when it answers. */
	.mg-conn {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		height: 30px;
		padding: 0 11px;
		border: 1px solid var(--mg-border);
		border-radius: 999px;
		background: var(--mg-surface);
		color: var(--mg-text-2);
		font-family: var(--mg-mono);
		font-size: 12px;
		white-space: nowrap;
	}
	.mg-conn:hover {
		border-color: var(--mg-border-strong);
		color: var(--mg-text);
	}
	.mg-conn .led {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--mg-text-3);
	}
	.mg-conn.on .led {
		background: var(--mg-ok);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--mg-ok) 22%, transparent);
	}
	.mg-conn.off {
		border-color: color-mix(in srgb, var(--mg-danger) 45%, var(--mg-border));
		color: var(--mg-danger);
	}
	.mg-conn.off .led {
		background: var(--mg-danger);
	}
	@media (max-width: 1100px) {
		.mg-conn span:last-child {
			display: none;
		}
	}
	/* The beta note: small, in the warning colour, so it is seen without taking room. */
	.mg-beta {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		margin-left: 12px;
		padding: 2px 9px;
		border-radius: 999px;
		background: color-mix(in oklab, var(--color-warning-500, #e0a100) 22%, transparent);
		color: color-mix(in oklab, var(--color-warning-900, #7a4a00) 85%, var(--mg-text));
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.02em;
		white-space: nowrap;
		vertical-align: middle;
	}
	.mg-beta:hover {
		text-decoration: underline;
	}
	/* Simple or Guided: two buttons in one outline, beside the account. */
	.mg-mode {
		display: flex;
		gap: 2px;
		padding: 2px;
		border: 1px solid var(--color-surface-300-700);
		border-radius: var(--radius-base);
	}
	.mg-mode .btn {
		padding-inline: 10px;
	}
	/* The running job: its ring and a line of where it has got to. */
	.mg-running {
		max-width: min(42vw, 420px);
		gap: 8px;
	}
	.mg-running span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	@media (max-width: 980px) {
		.mg-running span {
			display: none;
		}
	}
	/* Under the bar: the sidebar and the page. */
	.mg-body {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}
	.mg-page {
		display: flex;
		flex-direction: column;
		flex: 1 1 auto;
		min-width: 0;
		min-height: 0;
	}
	/* The sidebar: the bar's grey continued down the left, the pages in their groups. */
	.mg-side {
		display: flex;
		flex-direction: column;
		flex: none;
		gap: 2px;
		width: 196px;
		padding: 10px 10px 12px;
		overflow-y: auto;
		background: var(--color-surface-100-900);
		scrollbar-width: none;
		transition: width var(--mo-1, 160ms) ease;
	}
	.mg-side.shut {
		width: 60px;
	}
	.mg-side-h {
		margin: 12px 10px 4px;
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		white-space: nowrap;
		opacity: 0.55;
	}
	.mg-side.shut .mg-side-h {
		height: 1px;
		margin: 8px 0;
		overflow: hidden;
		color: transparent;
	}
	.mg-side :global(.mg-side-item) {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 32px;
		padding: 0 10px;
		border-radius: var(--radius-base);
		color: var(--mg-text-2);
		font-size: 0.875rem;
		white-space: nowrap;
		transition: background-color 120ms ease;
	}
	.mg-side :global(.mg-side-item svg) {
		flex: none;
	}
	.mg-side :global(.mg-side-item:hover) {
		background: color-mix(in oklab, var(--mg-text) 7%, transparent);
		color: var(--mg-text);
	}
	.mg-side :global(.mg-side-item[aria-current='page']) {
		background: var(--color-primary-500);
		color: var(--color-primary-contrast-500);
		font-weight: 600;
	}
	.mg-side :global(.mg-side-item.small) {
		height: 30px;
		font-size: 0.85rem;
	}
	.mg-side.shut :global(.mg-side-item) {
		justify-content: center;
		padding: 0;
	}
	.mg-side.shut :global(.mg-side-item span) {
		display: none;
	}
	@media (max-width: 820px) {
		.mg-side {
			display: none;
		}
		.mg-home-sub {
			display: none;
		}
	}
	/* The bar's own tools sit in it on a wide window; on a phone they are in the menu instead. */
	.mg-tools {
		display: contents;
	}
	.mg-drawer-you,
	.mg-beta-menu {
		display: none;
	}
	@media (max-width: 640px) {
		.mg-tools,
		.mg-beta:not(.mg-beta-menu) {
			display: none;
		}
		.mg-drawer-you {
			display: block;
		}
		.mg-beta-menu {
			display: inline-flex;
			font-size: 11px;
		}
		:global(.crisp .mg-appbar) {
			padding-right: 6px;
		}
	}
	.mg-you-who {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0;
		padding: 0 12px;
		font-size: 0.85rem;
		opacity: 0.8;
	}
	.mg-you-row {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		padding: 0 12px;
	}
	/* The drawer's pages: Dane's large rows, with a line on what each page is for. */
	.mg-drawer :global(.mg-drawer-item) {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		padding: 10px 12px;
		border-radius: var(--radius-container);
		transition: background-color 120ms ease;
	}
	.mg-drawer :global(.mg-drawer-item:hover) {
		background: var(--color-surface-200-800);
	}
	.mg-drawer :global(.mg-drawer-item[aria-current='page']) {
		background: var(--color-primary-100-900);
	}
	.mg-drawer :global(.mg-drawer-item svg) {
		flex-shrink: 0;
		margin-top: 2px;
	}
	.mg-drawer :global(.mg-drawer-item span) {
		display: flex;
		flex-direction: column;
	}
	.mg-drawer :global(.mg-drawer-item b) {
		font-size: 1.05rem;
		font-weight: 600;
	}
	.mg-drawer :global(.mg-drawer-item small) {
		font-size: 0.85rem;
		opacity: 0.7;
	}
	.grow {
		flex-grow: 1;
	}
	.content {
		view-transition-name: mo-main;
		flex-grow: 1;
		min-height: 0;
		overflow: auto;
		/* Backdrop "Glow" (Customize): a faint wash of the accent behind the page's head. */
		background:
			radial-gradient(900px 360px at 8% -120px, color-mix(in srgb, var(--cr-page, var(--mg-accent)) var(--cr-glow, 0%), transparent), transparent 72%),
			var(--mg-bg);
		background-attachment: local;
	}
	/* A palette in the menu: its page, panel and line colours side by side. */
	.mg-swatch {
		flex: none;
		width: 30px;
		height: 16px;
		border: 1px solid var(--mg-border);
		border-radius: 4px;
		background: linear-gradient(90deg, var(--a) 0 34%, var(--b) 34% 67%, var(--c) 67%);
	}

	/* ------------------------------------------------ Customize */
	.scrim {
		position: absolute;
		inset: 0;
		z-index: 30;
		border: none;
		background: var(--mg-scrim);
		cursor: default;
	}
	.drawer {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: 31;
		display: flex;
		flex-direction: column;
		background: var(--mg-bg);
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.16);
	}
	.drawer header {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 60px;
		flex-shrink: 0;
		padding: 0 12px 0 18px;
		background: var(--color-surface-100-900);
	}
	.drawer-icon {
		display: grid;
		place-items: center;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: var(--mg-accent-soft);
		color: var(--mg-accent-ink);
	}
	.drawer h2 {
		font-size: 1.25rem;
		font-weight: 700;
	}
	.tabs {
		position: relative;
		flex-shrink: 0;
		display: flex;
		gap: 2px;
		margin: 14px 18px 0;
		padding: 4px;
		border-radius: var(--radius-base);
		background: var(--color-surface-100-900);
	}
	.tabs button {
		position: relative;
		z-index: 1;
		flex: 1 1 auto;
		min-width: 0;
		height: 32px;
		padding: 0 12px;
		overflow: hidden;
		border: none;
		border-radius: var(--radius-base);
		background: transparent;
		color: var(--mg-text-2);
		font: inherit;
		font-size: var(--cr-fs-meta);
		font-weight: 500;
		text-overflow: ellipsis;
		white-space: nowrap;
		cursor: pointer;
	}
	.tabs button[aria-selected='true'] {
		background: var(--color-primary-500);
		color: var(--color-primary-contrast-500);
		font-weight: 600;
	}
	.tabs > :global(.mo-thumb) {
		border-radius: var(--radius-base);
		background: var(--color-primary-500);
	}
	.tabs:global(.mo-has-thumb) button[aria-selected='true'] {
		background: transparent;
	}
	.drawer-body {
		flex-grow: 1;
		min-height: 0;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 16px 18px 20px;
	}
	.drawer footer {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		align-items: stretch;
		gap: 10px;
		padding: 12px 18px;
		border-top: 1px solid var(--mg-border);
		background: var(--color-surface-100-900);
	}
	.set-default {
		width: 100%;
		justify-content: center;
	}
	.foot-line {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.foot-line .mg-link {
		margin-left: auto;
		flex-shrink: 0;
		font-size: var(--mg-fs-xs);
	}
	.saved-dot {
		flex-shrink: 0;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--mg-ok);
	}
	.note {
		font-size: var(--cr-fs-micro);
		color: var(--mg-text-3);
		line-height: 1.45;
	}
	.line-switch {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 14px;
	}

	/* ------------------------------------------------ notices */
	.previewing {
		position: absolute;
		left: 50%;
		bottom: 20px;
		z-index: 40;
		translate: -50% 0;
		display: flex;
		align-items: center;
		gap: 10px;
		height: 42px;
		padding: 0 8px 0 16px;
		border-radius: var(--radius-container);
		background: var(--mg-surface);
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.16);
		font-size: var(--cr-fs-meta);
		white-space: nowrap;
	}
</style>
