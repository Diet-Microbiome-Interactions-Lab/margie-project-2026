/**
 * The code password for this visit, which the server checks before it sends a script's text
 * (routers/code.py); kept in sessionStorage, so it goes when the tab closes. '' until given.
 */
const KEY = 'margie.code-password';

export function codeKey(): string {
	try {
		return sessionStorage.getItem(KEY) ?? '';
	} catch {
		return '';
	}
}

export function keepCodeKey(password: string) {
	try {
		sessionStorage.setItem(KEY, password);
	} catch {
		// Storage blocked: the password is asked again next time.
	}
}

/** Whether an error is the server asking for the code password. */
export const isCodeLocked = (e: unknown) => String((e as Error)?.message ?? e).startsWith('code-locked');
