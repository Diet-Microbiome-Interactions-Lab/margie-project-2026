/**
 * Cluster parts of the interface. The website has no start page, tunnel or local chat
 * server, so only the cluster Setup block is here; the Install lock lives in the browser.
 */

import type { Component } from 'svelte';
import ClusterSetup from '$lib/cluster/ClusterSetup.svelte';

/** A genome's cluster results as genome chat reads them (lib/server/genome-chat's Remote). */
export interface ChatRemote {
	api: string;
	token: string;
	roots: string[];
	table?: string | null;
	jobs?: { id: string; dir: string }[];
}

export const clusterParts: {
	Setup?: Component;
	/** Where to choose between this computer and the cluster (the start page). */
	switchHref?: string;
	/** Disconnects from the cluster. */
	disconnect?: () => Promise<boolean>;
	/** Endpoint that keeps and checks the Install page's lock, in both modes. */
	lockApi: string;
	/** Genome chat for cluster results: served locally (the key stays here), reading results through the tunnel. */
	chat?: { url: string; remote: (genome: string) => Promise<ChatRemote | null>; link?: () => { api: string; token: string } | null };
	/** Header control in HPC mode choosing where the server runs (login or compute node). */
	Compute?: Component;
} = { Setup: ClusterSetup, lockApi: '' };
