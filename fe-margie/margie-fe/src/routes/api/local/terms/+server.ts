import { json } from '@sveltejs/kit';
import crypto from 'node:crypto';
import terms from '../../../../../../../be-margie/bioinformatics_tools/api/licensing/terms.md?raw';
import catalog from '../../../../../../../be-margie/bioinformatics_tools/api/licensing/licensing_catalog.json';
import type { RequestHandler } from './$types';

/** MARGIE's terms and the tools' licences, as the cluster's GET /v1/license/terms gives them, for the Install page. */
export const GET: RequestHandler = async () => {
	const tools = catalog.tools;
	return json({
		terms_version: /terms_version:\s*([\w.-]+)/.exec(terms.split('\n')[0])?.[1] ?? 'unknown',
		terms_sha256: crypto.createHash('sha256').update(terms).digest('hex'),
		terms_markdown: terms,
		acknowledgments: [],
		usage_types: [],
		catalog_version: catalog.catalog_version,
		gated_tools: tools.filter((t) => t.tier === 'blocked' || t.tier === 'commercial_restricted'),
		tools,
		tier_definitions: catalog.tier_definitions
	});
};
