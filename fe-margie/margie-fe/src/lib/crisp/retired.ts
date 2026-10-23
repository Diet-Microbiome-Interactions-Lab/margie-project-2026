/**
 * Maps retired addresses onto today's pages, so old links and bookmarks keep working:
 * the Modern interface's /crisp/..., the older Workspace (/app) and Atlas (/atlas), and
 * the platform pages the new ones replaced (/filesearch, /run_ssh, /results/historical, ...).
 */

/** Pages that kept their name. */
const SAME = new Set(['results', 'files', 'terminal', 'settings', 'view', 'analyze', 'install']);

/** Today's address for a retired path (`rest` without the /crisp, /app or /atlas in front). */
export function currentPath(rest: string, search = ''): string {
	const [first = '', ...more] = rest.split('/').filter(Boolean);
	const q = new URLSearchParams(search);
	switch (first) {
		case '':
			return `/analyze${search}`;
		case 'home':
			return '/';
		case 'runs':
		case 'jobs':
			return `/jobs${more[0] ? `/${more[0]}` : ''}${more[0] ? '' : search}`;
		case 'setup':
			return `/install${search}`;
		case 'genome':
			return more[0] ? `/results?g=${encodeURIComponent(more[0])}` : '/results';
		case 'map': {
			const organism = q.get('organism') ?? q.get('path')?.split('/').filter(Boolean).at(-2) ?? '';
			return organism ? `/results?g=${encodeURIComponent(organism)}&tab=map` : '/results';
		}
		case 'genomes':
			return '/analyze#genomes';
		case 'filesearch':
			return '/files';
		case 'run_ssh':
		case 'run_script':
			return '/terminal';
		default:
			return SAME.has(first) ? `/${[first, ...more].join('/')}${search}` : `/analyze${search}`;
	}
}
