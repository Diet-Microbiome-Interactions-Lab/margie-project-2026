/**
 * Auth token storage and header utilities.
 *
 * All pages import authHeaders() to inject Authorization: Bearer <token>
 * into fetch calls. No page should read localStorage directly.
 *
 * NOTE: all functions read/write localStorage which is only available in the
 * browser. Do not call them at module level — only inside onMount or event
 * handlers.
 */

const TOKEN_KEY = 'bsp_token';

export function getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
}

export function isLoggedIn(): boolean {
    return getToken() !== null;
}

/**
 * Returns headers for an authenticated JSON request.
 * Includes Content-Type and, if a token is stored, Authorization: Bearer <token>.
 */
export function authHeaders(): Record<string, string> {
    const token = getToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

/**
 * A remembered browser's token for an account (api/browser_check.py): sent with the next sign-in
 * there, so no code is asked for while it is remembered. One per account in this browser.
 */
const BROWSER_KEY = (username: string) => `margie.browser.${username.trim().toLowerCase()}`;

export function browserToken(username: string): string | null {
    try {
        return localStorage.getItem(BROWSER_KEY(username));
    } catch {
        return null;
    }
}

export function rememberBrowser(username: string, token: string): void {
    try {
        if (token) localStorage.setItem(BROWSER_KEY(username), token);
    } catch {
        // Not kept: the next sign-in here asks for a code again.
    }
}
