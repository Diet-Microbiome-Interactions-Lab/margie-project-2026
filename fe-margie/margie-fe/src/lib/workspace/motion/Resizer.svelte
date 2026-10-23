<script lang="ts">
	import { ui } from '../ui.svelte';

	/**
	 * Drag handle on a side pane's edge (the pane needs position: relative and `ui.size(id, fallback)`).
	 * On the bottom edge it sets the pane's height instead of its width.
	 * Supports dragging, arrow keys (Shift for bigger steps) and double-click to reset.
	 */
	let {
		id,
		fallback,
		min = 160,
		max = 560,
		edge = 'right',
		label
	}: { id: string; fallback: number; min?: number; max?: number; edge?: 'left' | 'right' | 'bottom'; label: string } = $props();

	const width = $derived(ui.size(id, fallback));
	let dragging = $state(false);
	const tall = $derived(edge === 'bottom');

	const clamp = (v: number) => Math.round(Math.max(min, Math.min(max, tall ? innerHeight * 1.5 : innerWidth * 0.75, v)));

	function down(e: PointerEvent) {
		if (e.button !== 0) return;
		e.preventDefault();
		const handle = e.currentTarget as HTMLElement;
		handle.setPointerCapture(e.pointerId);
		const x0 = tall ? e.clientY : e.clientX;
		const w0 = width;
		let next = w0;
		let frame = 0;
		dragging = true;
		document.documentElement.classList.add('mo-resizing', tall ? 'mo-rows' : 'mo-cols');
		const move = (ev: PointerEvent) => {
			next = clamp(w0 + (tall ? ev.clientY - x0 : edge === 'right' ? ev.clientX - x0 : x0 - ev.clientX));
			frame ||= requestAnimationFrame(() => {
				frame = 0;
				ui.setSize(id, next);
			});
		};
		const up = () => {
			cancelAnimationFrame(frame);
			ui.setSize(id, next);
			dragging = false;
			document.documentElement.classList.remove('mo-resizing', 'mo-rows', 'mo-cols');
			handle.removeEventListener('pointermove', move);
			handle.removeEventListener('pointerup', up);
			handle.removeEventListener('pointercancel', up);
		};
		handle.addEventListener('pointermove', move);
		handle.addEventListener('pointerup', up);
		handle.addEventListener('pointercancel', up);
	}

	function key(e: KeyboardEvent) {
		const step = (e.shiftKey ? 64 : 16) * (edge === 'left' ? -1 : 1);
		const [more, less] = tall ? ['ArrowDown', 'ArrowUp'] : ['ArrowRight', 'ArrowLeft'];
		const to = e.key === more ? width + step : e.key === less ? width - step : e.key === 'Home' ? min : e.key === 'End' ? max : null;
		if (to === null) return;
		e.preventDefault();
		ui.setSize(id, clamp(to));
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<div
	class="mo-resizer {edge}"
	class:dragging
	role="separator"
	tabindex="0"
	aria-orientation={tall ? 'horizontal' : 'vertical'}
	aria-label={label}
	aria-valuenow={width}
	aria-valuemin={min}
	aria-valuemax={max}
	title="Drag to resize. Double-click to reset."
	onpointerdown={down}
	onkeydown={key}
	ondblclick={() => ui.setSize(id, null)}
></div>

<style>
	.mo-resizer {
		position: absolute;
		top: 0;
		bottom: 0;
		z-index: 6;
		width: 12px;
		cursor: col-resize;
		touch-action: none;
	}
	.right {
		right: -6px;
	}
	.left {
		left: -6px;
	}
	.bottom {
		top: auto;
		right: 0;
		bottom: -6px;
		left: 0;
		width: auto;
		height: 12px;
		cursor: row-resize;
	}
	.bottom::after {
		top: 5px;
		bottom: auto;
		left: 50%;
		width: 48px;
		height: 2px;
		margin-left: -24px;
		transform: scaleX(0.6);
	}
	.mo-resizer::after {
		content: '';
		position: absolute;
		top: 8px;
		bottom: 8px;
		left: 5px;
		width: 2px;
		border-radius: 2px;
		background: var(--at-teal, var(--mg-accent));
		opacity: 0;
		transform: scaleY(0.6);
		transition:
			opacity var(--mo-1) ease,
			transform var(--mo-2) var(--mo-ease);
	}
	.mo-resizer:hover::after,
	.mo-resizer:focus-visible::after,
	.dragging::after {
		opacity: 1;
		transform: none;
	}
	.mo-resizer:focus-visible {
		outline: none;
	}
</style>
