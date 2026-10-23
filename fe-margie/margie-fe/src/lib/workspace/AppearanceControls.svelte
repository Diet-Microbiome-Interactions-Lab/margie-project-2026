<script lang="ts">
	import SpeedControl from './motion/SpeedControl.svelte';
	import Field from './Field.svelte';
	import FontPicker from './FontPicker.svelte';
	import Seg from './Seg.svelte';
	import SizeSliders from './SizeSliders.svelte';
	import Switch from './Switch.svelte';
	import { ACCENTS, accentColor } from './prefs';
	import { SHADE_NAMES, SHADE_ORDER } from './shades';
	import { ui } from './ui.svelte';

	/**
	 * Customize's settings, in two parts: `colours` (the accent and how much colour the page
	 * wears, shown under the presets) and `layout` (type, shape and spacing, motion).
	 */
	let { part }: { part: 'colours' | 'layout' } = $props();
	const HEX = /^#?[0-9a-fA-F]{6}$/;
	const custom = $derived(ui.prefs.accent.startsWith('#'));
	let hex = $state('');
	$effect(() => {
		hex = accentColor(ui.prefs, ui.dark);
	});

	function setHex(v: string) {
		const t = v.trim();
		if (HEX.test(t)) ui.update({ accent: ('#' + t.replace('#', '')).toUpperCase() });
	}
</script>

{#if part === 'colours'}
	<section class="cr-group">
		<h3 class="cr-group-title">Accent</h3>
		<div class="swatches" role="radiogroup" aria-label="Accent colour">
			{#each ACCENTS as a (a.id)}
				<button
					type="button"
					role="radio"
					class="swatch mg-t"
					aria-checked={ui.prefs.accent === a.id}
					aria-label={a.name}
					title={a.name}
					style="--c: {ui.dark ? a.dark : a.light}"
					onclick={() => ui.update({ accent: a.id })}
				></button>
			{/each}
			<label class="swatch picker mg-t" class:selected={custom} title="Custom colour" style="--c: {custom ? ui.prefs.accent : 'transparent'}">
				<span class="mg-sr">Custom colour</span>
				<input type="color" value={accentColor(ui.prefs, ui.dark)} oninput={(e) => setHex(e.currentTarget.value)} />
			</label>
			<input
				class="mg-input mono hex"
				aria-label="Accent colour as hex"
				spellcheck="false"
				bind:value={hex}
				onchange={() => setHex(hex)}
				onkeydown={(e) => e.key === 'Enter' && setHex(hex)}
			/>
		</div>
		<span class="note">Buttons, links, titles and the page you are on.</span>
	</section>

	<section class="cr-group">
		<h3 class="cr-group-title">How much colour</h3>
		<Field title="Section colours">
			<Seg label="Section colours" value={ui.prefs.shades} onpick={(shades) => ui.update({ shades })} options={SHADE_ORDER.map((v) => ({ value: v, label: SHADE_NAMES[v] }))} />
		</Field>
		<Field title="Box heads and tags">
			<Seg label="Box heads and tags" value={ui.prefs.tint} onpick={(tint) => ui.update({ tint })} options={[{ value: 'plain', label: 'Plain' }, { value: 'soft', label: 'Soft' }, { value: 'strong', label: 'Strong' }]} />
		</Field>
		<Field title="Glow behind the title">
			<Seg label="Glow behind the title" value={ui.prefs.backdrop} onpick={(backdrop) => ui.update({ backdrop })} options={[{ value: 'glow', label: 'Glow' }, { value: 'plain', label: 'Plain' }]} />
		</Field>
		<Field title="Contrast">
			<Seg label="Contrast" value={ui.prefs.contrast} onpick={(contrast) => ui.update({ contrast })} options={[{ value: 'normal', label: 'Normal' }, { value: 'more', label: 'More' }, { value: 'high', label: 'High' }]} />
		</Field>
	</section>
{:else}
	<section class="cr-group">
		<h3 class="cr-group-title">Type</h3>
		<Field title="Size">
			<SizeSliders />
		</Field>

		<Field title="Font">
			<FontPicker value={ui.prefs.typeface} onchange={(typeface) => ui.update({ typeface })} />
		</Field>

		<Field title="Monospace">
			<!-- Separate from the interface font: used for logs, paths and sequences. -->
			<FontPicker only="mono" value={ui.prefs.monoface} onchange={(monoface) => ui.update({ monoface })} />
		</Field>
	</section>

	<section class="cr-group">
		<h3 class="cr-group-title">Layout</h3>
		<Field title="Corners">
			<Seg
				label="Corners"
				value={ui.prefs.radius}
				onpick={(radius) => ui.update({ radius })}
				options={[
					{ value: 0, label: 'Sharp' },
					{ value: 6, label: 'Soft' },
					{ value: 10, label: 'Round' }
				]}
			/>
		</Field>

		<Field title="Density">
			<Seg
				label="Density"
				value={ui.prefs.density}
				onpick={(density) => ui.update({ density })}
				options={[
					{ value: 'compact', label: 'Compact' },
					{ value: 'comfortable', label: 'Comfortable' }
				]}
			/>
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

	<section class="cr-group">
		<h3 class="cr-group-title">Motion</h3>
		<Field title="Motion">
			<Seg
				label="Motion"
				value={ui.prefs.motion}
				onpick={(motion) => ui.update({ motion })}
				options={[
					{ value: 'full', label: 'Full' },
					{ value: 'subtle', label: 'Subtle' },
					{ value: 'off', label: 'Off' }
				]}
			/>
			{#if ui.reducedMotion}
				<span class="note">Your computer asks for reduced motion, so animations stay off.</span>
			{/if}
		</Field>

		<Field title="Speed">
			<SpeedControl />
		</Field>
	</section>
{/if}

<style>
	.swatches {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}
	.swatch {
		position: relative;
		width: 26px;
		height: 26px;
		padding: 0;
		border: none;
		border-radius: var(--mg-r-sm);
		background: var(--c);
		box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--mg-text) 12%, transparent);
		cursor: pointer;
		transition: transform var(--mo-1) var(--mo-ease);
	}
	.swatch:hover {
		transform: scale(1.1);
	}
	.swatch[aria-checked='true'],
	.swatch.selected {
		box-shadow: 0 0 0 2px var(--mg-surface), 0 0 0 4px var(--c);
	}
	.picker {
		display: inline-block;
		border: 1.5px dashed var(--mg-border-strong);
		background: transparent;
	}
	.picker.selected {
		border: none;
		background: var(--c);
	}
	.picker input {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		opacity: 0;
		cursor: pointer;
	}
	.hex {
		width: 104px;
		height: 34px;
		margin-left: auto;
		text-transform: uppercase;
	}
	.note {
		font-size: var(--mg-fs-xs);
		color: var(--mg-text-3);
	}
	.line-switch {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 14px;
	}
</style>
