// Checks the quiz banks (src/lib/quiz/bank/*.json) against src/lib/quiz/types.ts: shapes, answer
// indexes, unique ids and unambiguous matches. Prints the counts; exits 1 on a problem.
//   node scripts/check-quiz.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'lib', 'quiz', 'bank');
const LEVELS = ['easy', 'intermediate', 'hard'];
const TOPICS = ['physiology', 'metabolism', 'bioinformatics', 'gut', 'margie'];
const WORDS = /\b(never|always|every|all)\b/i;
const problems = [];
const ids = new Set();
const count = (o, k) => (o[k] = (o[k] ?? 0) + 1);
const str = (v) => typeof v === 'string' && v.trim().length > 0;
const choice = (where, options, answer) => {
	if (!Array.isArray(options) || options.length !== 4 || !options.every(str)) problems.push(`${where}: needs 4 options`);
	else if (new Set(options).size !== 4) problems.push(`${where}: options repeat`);
	if (!Number.isInteger(answer) || answer < 0 || answer > 3) problems.push(`${where}: answer must be 0 to 3`);
};

for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort()) {
	const list = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
	const by = { level: {}, kind: {}, answerAt: {} };
	for (const q of list) {
		const w = `${file} ${q.id}`;
		if (!str(q.id) || ids.has(q.id)) problems.push(`${w}: missing or repeated id`);
		ids.add(q.id);
		if (!TOPICS.includes(q.topic)) problems.push(`${w}: topic`);
		if (!LEVELS.includes(q.level)) problems.push(`${w}: level`);
		if (!str(q.explain)) problems.push(`${w}: explain`);
		count(by.level, q.level);
		count(by.kind, q.kind);
		const text = JSON.stringify(q);
		if (WORDS.test(text)) problems.push(`${w}: uses never/always/every/all (${text.match(WORDS)[0]})`);
		if (q.kind === 'truefalse') {
			if (!str(q.statement) || typeof q.answer !== 'boolean') problems.push(`${w}: truefalse shape`);
		} else if (q.kind === 'choice') {
			if (!str(q.question)) problems.push(`${w}: question`);
			choice(w, q.options, q.answer);
			count(by.answerAt, q.answer);
		} else if (q.kind === 'match') {
			if (!str(q.question) || !Array.isArray(q.pairs) || q.pairs.length < 4 || q.pairs.length > 5) problems.push(`${w}: match needs 4 or 5 pairs`);
			else if (new Set(q.pairs.map((p) => p.left)).size !== q.pairs.length || new Set(q.pairs.map((p) => p.right)).size !== q.pairs.length)
				problems.push(`${w}: match items repeat`);
		} else if (q.kind === 'case') {
			if (!str(q.scenario) || !Array.isArray(q.parts) || q.parts.length < 2 || q.parts.length > 3) problems.push(`${w}: case needs 2 or 3 parts`);
			else q.parts.forEach((p, k) => (str(p.question) && str(p.explain) ? choice(`${w} part ${k + 1}`, p.options, p.answer) : problems.push(`${w} part ${k + 1}: shape`)));
		} else problems.push(`${w}: unknown kind ${q.kind}`);
	}
	console.log(`${file}: ${list.length} | levels ${JSON.stringify(by.level)} | kinds ${JSON.stringify(by.kind)} | choice answers at ${JSON.stringify(by.answerAt)}`);
}
console.log(`${ids.size} questions`);
if (problems.length) {
	console.log(problems.join('\n'));
	process.exit(1);
}
