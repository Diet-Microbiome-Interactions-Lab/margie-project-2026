/**
 * Prints the settings saved in the app (<pipeline>/gui/settings.local.json) as shell `export` lines,
 * for margie-cli, which runs it with the app's own binary (ELECTRON_RUN_AS_NODE). Each value is in
 * single quotes. Prints nothing for a missing or unreadable file.
 */
const fs = require('node:fs');

try {
	const saved = JSON.parse(fs.readFileSync(process.argv[process.argv.length - 1], 'utf8'));
	for (const [key, value] of Object.entries(saved)) {
		if (/^[A-Z_][A-Z0-9_]*$/.test(key) && typeof value === 'string') {
			console.log(`export ${key}='${value.replaceAll("'", `'\\''`)}'`);
		}
	}
} catch {
	// No settings saved yet.
}
