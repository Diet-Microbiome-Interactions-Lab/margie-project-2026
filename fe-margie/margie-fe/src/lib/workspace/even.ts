/**
 * Even grids: a list of choices (tools, licences, install items, settings) laid out so
 * every row is full, instead of a short last row. The column count is the widest that
 * fits and leaves no gap; when none does, the one with the fewest empty cells.
 *
 *   <ul class="mg-even" use:even={190}>   (190: the narrowest a cell may be, in px)
 *
 * The grid reads --cols; .mg-even (lib/crisp/skeleton-look.css) sets the columns from it.
 */

/** Columns for `n` items when at most `fit` fit across: 12 in 6 -> 6, 10 in 6 -> 5, 21 in 6 -> 3. */
export function evenColumns(n: number, fit: number): number {
	const most = Math.max(1, Math.min(fit, n));
	if (n <= most) return n || 1;
	let best = most;
	let bestEmpty = Infinity;
	// No narrower than half of what fits: past that, a gap beats a tall thin list.
	for (let c = most; c >= Math.max(1, Math.ceil(most / 2)); c--) {
		const empty = Math.ceil(n / c) * c - n;
		if (empty < bestEmpty) {
			best = c;
			bestEmpty = empty;
			if (!empty) break;
		}
	}
	return best;
}

/** Svelte action: keeps --cols on a grid right for its children and its width; `[min, most]` caps the columns too. */
export function even(node: HTMLElement, min: number | [number, number] = 180) {
	let [narrowest, most] = Array.isArray(min) ? min : [min, Infinity];
	const update = () => {
		const n = node.children.length;
		const width = node.clientWidth;
		if (!n || !width) return;
		const gap = parseFloat(getComputedStyle(node).columnGap) || 0;
		const fit = Math.max(1, Math.min(most, Math.floor((width + gap) / (narrowest + gap))));
		node.style.setProperty('--cols', String(evenColumns(n, fit)));
	};
	const ro = new ResizeObserver(update);
	ro.observe(node);
	const mo = new MutationObserver(update);
	mo.observe(node, { childList: true });
	update();
	return {
		update(next: number | [number, number]) {
			[narrowest, most] = Array.isArray(next) ? next : [next, Infinity];
			update();
		},
		destroy() {
			ro.disconnect();
			mo.disconnect();
		}
	};
}

/**
 * One column count for several lists stacked under one another (groups of tools), so their
 * columns line up: the count, of those that fit, with the fewest empty cells over all of them.
 */
export function sharedColumns(sizes: number[], fit: number): number {
	const most = Math.max(1, Math.min(fit, Math.max(1, ...sizes)));
	let best = most;
	let bestEmpty = Infinity;
	for (let c = most; c >= Math.max(1, Math.ceil(most / 2)); c--) {
		const empty = sizes.reduce((a, n) => a + (Math.ceil(n / c) * c - n), 0);
		if (empty < bestEmpty) {
			best = c;
			bestEmpty = empty;
			if (!empty) break;
		}
	}
	return best;
}
