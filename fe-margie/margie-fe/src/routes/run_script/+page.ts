import { redirect } from '@sveltejs/kit';
import { currentPath } from '$lib/crisp/retired';

/** Run SLURM is the Terminal now (sbatch). */
export function load({ url }) {
	redirect(308, currentPath('run_script', url.search));
}
