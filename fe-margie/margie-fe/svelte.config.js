import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// A single-page app: every path serves index.html and the client renders it (see routes/+layout.ts).
		adapter: adapter({ fallback: 'index.html', strict: false }),
		// An open tab asks for the deployed version every two minutes (routes/+layout.svelte loads a newer one).
		version: { pollInterval: 120_000 }
	}
};

export default config;
