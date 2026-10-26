/**
 * The quiz's questions (routes/(app)/quiz): bacterial and archaeal physiology, metabolism, energetics,
 * applied bioinformatics, the gut microbiome with dietary polysaccharides, and how MARGIE works, at three levels, in four kinds. The banks are JSON files in ./bank, one array each.
 */

export type Level = 'easy' | 'intermediate' | 'hard';
export type Topic = 'physiology' | 'metabolism' | 'energetics' | 'bioinformatics' | 'gut' | 'margie';

interface Common {
	/** Unique across the banks, e.g. "phys1-042". */
	id: string;
	topic: Topic;
	level: Level;
	/** Shown once answered: why the answer is right, in one to three sentences. */
	explain: string;
}

/** A statement to judge. */
export interface TrueFalse extends Common {
	kind: 'truefalse';
	statement: string;
	answer: boolean;
}

/** One right option among four. `answer` is its index. */
export interface Choice extends Common {
	kind: 'choice';
	question: string;
	options: string[];
	answer: number;
}

/** Four or five pairs to match; the right-hand items are shown shuffled. */
export interface Match extends Common {
	kind: 'match';
	question: string;
	pairs: { left: string; right: string }[];
}

/** A short scenario with two or three questions about it. */
export interface CaseStudy extends Common {
	kind: 'case';
	scenario: string;
	parts: { question: string; options: string[]; answer: number; explain: string }[];
}

export type Question = TrueFalse | Choice | Match | CaseStudy;

/** One of the questions that open the quiz. */
export interface Unlock {
	id: string;
	question: string;
	options: string[];
	answer: number;
	explain: string;
	/** Just for fun rather than for the science. */
	fun?: boolean;
}

export const LEVELS: Level[] = ['easy', 'intermediate', 'hard'];
export const TOPICS: { id: Topic; label: string }[] = [
	{ id: 'physiology', label: 'Physiology' },
	{ id: 'metabolism', label: 'Metabolism' },
	{ id: 'energetics', label: 'Energetics' },
	{ id: 'bioinformatics', label: 'Bioinformatics' },
	{ id: 'gut', label: 'Gut microbiome' },
	{ id: 'margie', label: 'MARGIE' }
];
export const KINDS: { id: Question['kind']; label: string }[] = [
	{ id: 'choice', label: 'Multiple choice' },
	{ id: 'truefalse', label: 'True or false' },
	{ id: 'match', label: 'Drag and match' },
	{ id: 'case', label: 'Case study' }
];
