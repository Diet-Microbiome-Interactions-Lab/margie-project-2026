/**
 * Client calls for "Chat with the genome". In the app, the model call and keys stay on
 * this computer's server (lib/server/genome-chat), and a cluster genome's question also
 * carries how to read its results there (clusterParts.chat). On the website, the MARGIE
 * server answers instead (api/routers/chat.py), keeping keys in the cluster account,
 * encrypted and dated to expire.
 */

import { ApiError, api } from '$lib/api';
import { chatRemote } from '$lib/cluster/backend';
import { call, get } from '$lib/cluster/http';
import { backend } from './backend.svelte';
import { clusterParts } from './cluster-parts';

const onCluster = () => backend.cluster && !!clusterParts.chat;
/** The website: no app beside it, so the MARGIE server holds the chat. */
export const onServer = () => backend.cluster && !clusterParts.chat;

async function local<T>(method: string, query: string, body?: unknown): Promise<T> {
	const res = await fetch(`${clusterParts.chat!.url}${query}`, {
		method,
		headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) throw new ApiError(data.message ?? `Request failed (${res.status}).`, res.status);
	return data as T;
}

const g = (genome: string) => `?genome=${encodeURIComponent(genome)}`;

/** Whether chat can be used where MARGIE is working now (this computer, the app, or the website's server). */
export const chatAvailable = () => !backend.cluster || !!clusterParts.chat || onServer();

/** Returns the app's HPC connection for keys kept there, or null when not connected. */
const link = () => (onCluster() ? (clusterParts.chat!.link?.() ?? null) : null);
/** Whether keys can be kept in the HPC home (connected to one, in the app). */
export const hpcKeysAvailable = () => !!link();

export async function chatGet<T extends object>(genome: string): Promise<T> {
	if (onServer()) return get<T>(`/v1/chat${g(genome)}`);
	if (!onCluster()) return api<T>(`/genome-chat${g(genome)}`);
	const d = await local<T>('GET', `${g(genome)}&where=hpc`);
	// Keys in the HPC home are read once connected and held in server memory.
	const l = link();
	if (!l) return d;
	try {
		return { ...d, ...(await local<object>('PUT', '', { hpc: l, hpcPull: true })) } as T;
	} catch {
		return d;
	}
}

/** Saves (or, with null, removes) a key in the HPC home. */
export function chatHpcKey<T>(provider: string, key: string | null): Promise<T> {
	const l = link();
	if (!l) throw new ApiError('Not connected to the HPC.', 400);
	return local<T>('PUT', '', { hpc: l, hpcKey: key, keyFor: provider });
}

/** Reads the HPC home's keys again (after editing the file there by hand). */
export function chatHpcReload<T>(): Promise<T> {
	const l = link();
	if (!l) throw new ApiError('Not connected to the HPC.', 400);
	return local<T>('PUT', '', { hpc: l, hpcPull: true });
}

export function chatSettings<T>(body: unknown): Promise<T> {
	if (onServer()) return call<T>('PUT', '/v1/chat', body);
	return onCluster() ? local<T>('PUT', '', body) : api<T>('/genome-chat', { method: 'PUT', body: JSON.stringify(body) });
}

export async function chatAsk<T>(genome: string, question: string, context: string): Promise<T> {
	if (onServer()) {
		// The server reads the genome's folders over your own connection, and nothing outside them.
		const r = await chatRemote(genome);
		if (!r) throw new ApiError(`No results for ${genome} on the cluster yet.`, 404);
		return call<T>('POST', '/v1/chat', { genome, question, context, remote: { roots: r.roots, table: r.table ?? null } });
	}
	if (!onCluster()) return api<T>('/genome-chat', { method: 'POST', body: JSON.stringify({ genome, question, context }) });
	const remote = await clusterParts.chat!.remote(genome);
	if (!remote) throw new ApiError(`No results for ${genome} on the cluster yet.`, 404);
	return local<T>('POST', '', { genome, question, context, remote });
}

export function chatForget(genome: string): Promise<unknown> {
	if (onServer()) return call('DELETE', `/v1/chat${g(genome)}`);
	return onCluster() ? local('DELETE', `${g(genome)}&where=hpc`) : api(`/genome-chat${g(genome)}`, { method: 'DELETE' });
}
