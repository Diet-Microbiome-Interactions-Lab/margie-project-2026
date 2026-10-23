/** Puts text on the system clipboard; false when the browser would not. */
export async function copyText(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		// Without the clipboard API (an older browser, or plain http): the old way.
		const t = document.createElement('textarea');
		t.value = text;
		t.style.position = 'fixed';
		t.style.opacity = '0';
		document.body.append(t);
		t.select();
		const ok = document.execCommand('copy');
		t.remove();
		return ok;
	}
}
