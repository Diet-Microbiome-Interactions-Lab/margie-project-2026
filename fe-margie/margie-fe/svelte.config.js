import adapterNode from '@sveltejs/adapter-node';
import adapterStatic from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// The website unless VITE_HOSTED=0 (see src/lib/hosted.ts): the desktop app builds the node server.
const hosted = process.env.VITE_HOSTED !== '0';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// The website: a single-page app, every path serving index.html (see routes/+layout.ts).
		adapter: hosted ? adapterStatic({ fallback: 'index.html', strict: false }) : adapterNode(),
		// An open tab asks for the deployed version every two minutes (routes/+layout.svelte loads a newer one).
		version: { pollInterval: 120_000 }
	}
};

export default config;
