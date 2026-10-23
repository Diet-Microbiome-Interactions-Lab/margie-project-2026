import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** Genomes is part of Analyze now: its section there. */
export function load() {
	redirect(308, currentPath('genomes'));
}
