/**
 * Files being read from the cluster, with how much has arrived, for the pages that wait on them
 * (Results: the summary, the genome map, the table). The speed of the last reads is kept in this
 * browser, so a wait that reports no bytes (the server reading a table for its counts) still gets
 * an estimate.
 */

export interface Transfer {
	path: string;
	loaded: number;
	/** Bytes in the whole file, when the server says (Content-Length); else 0. */
	total: number;
	started: number;
}

const RATE_KEY = 'margie.load.rate';
/** A first guess, in bytes per second, before any read is measured. */
const FIRST_RATE = 2_000_000;

function savedRate(): number {
	try {
		return Number(localStorage.getItem(RATE_KEY)) || FIRST_RATE;
	} catch {
		return FIRST_RATE;
	}
}

class Transfers {
	list = $state<Transfer[]>([]);
	/** Bytes per second, an average of the reads measured so far. */
	rate = $state(savedRate());

	/** The read under way for `path` (the same file, however its path is written), if any. */
	find(path: string): Transfer | undefined {
		if (!path) return undefined;
		return this.list.find((t) => t.path === path || t.path.endsWith(path) || path.endsWith(t.path));
	}

	measured(bytes: number, seconds: number) {
		if (bytes < 500_000 || seconds < 0.3) return;
		this.rate = Math.round(this.rate * 0.5 + (bytes / seconds) * 0.5);
		try {
			localStorage.setItem(RATE_KEY, String(this.rate));
		} catch {
			// Storage blocked: the speed is kept for this visit.
		}
	}
}

export const transfers = new Transfers();

/** Reads a response body as a Blob, reporting its progress under `path`. */
export async function readWithProgress(res: Response, path: string): Promise<Blob> {
	const type = res.headers.get('content-type') ?? '';
	if (!res.body) return res.blob();
	const started = Date.now();
	transfers.list = [...transfers.list, { path, loaded: 0, total: Number(res.headers.get('content-length')) || 0, started }];
	const entry = transfers.list[transfers.list.length - 1];
	const reader = res.body.getReader();
	const parts: Uint8Array[] = [];
	let loaded = 0;
	let shown = 0;
	try {
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			parts.push(value);
			loaded += value.length;
			// The page redraws a few times a second, however small the chunks.
			if (Date.now() - shown > 120) {
				entry.loaded = loaded;
				shown = Date.now();
			}
		}
	} finally {
		transfers.list = transfers.list.filter((t) => t !== entry);
	}
	transfers.measured(loaded, (Date.now() - started) / 1000);
	return new Blob(parts as BlobPart[], { type });
}
