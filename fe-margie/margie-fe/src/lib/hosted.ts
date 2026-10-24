/**
 * This is MARGIE's website unless built with VITE_HOSTED=0: the interface served as static
 * files, working only with a cluster through MARGIE's API (same origin, or VITE_PUBLIC_API_URL),
 * with no local pipeline, no start page and no server routes. The desktop app builds with
 * VITE_HOSTED=0 (desktop/scripts/stage.mjs): a node server with both modes, this computer
 * (routes/api/local) and the HPC (routes/api/connect, scripts/hpc-connect.sh).
 */
export const HOSTED = import.meta.env.VITE_HOSTED !== '0';
