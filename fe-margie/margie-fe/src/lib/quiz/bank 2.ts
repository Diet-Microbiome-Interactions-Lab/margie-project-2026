/** The quiz's questions: each JSON file in ./bank, in file order. */

import type { Question } from './types';

const files = import.meta.glob<Question[]>('./bank/*.json', { eager: true, import: 'default' });

export const QUESTIONS: Question[] = Object.keys(files)
	.sort()
	.flatMap((k) => files[k]);

/** A copy of `list` in random order. */
export function shuffled<T>(list: readonly T[]): T[] {
	const out = [...list];
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[out[i], out[j]] = [out[j], out[i]];
	}
	return out;
}
