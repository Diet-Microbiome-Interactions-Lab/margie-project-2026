/**
 * The FAQ page's questions and answers, with the papers each rests on and the code blocks that do
 * what it says (read from the server's pipeline when opened: routers/code.py, /v1/code/snippet).
 * A question marked `thesis` has a further panel drawn from the thesis, which is under embargo; it
 * opens with the password (locked page "faq", by question id).
 */

export interface FaqCode {
	/** Path under workflow_tools. */
	path: string;
	/** A top-level function, class or constant, or "rule:<name>" in margie_sb.smk. */
	symbol: string;
	why: string;
}

export interface Faq {
	id: string;
	group: string;
	q: string;
	/** Paragraphs of HTML. */
	a: string[];
	refs: string[];
	code: FaqCode[];
	thesis: boolean;
}

export interface Ref {
	id: string;
	/** APA 7th. */
	apa: string;
	url: string;
}

export const GROUPS: string[] = [];

export const FAQS: Faq[] = [];

export const REFS: Record<string, Ref> = {};
