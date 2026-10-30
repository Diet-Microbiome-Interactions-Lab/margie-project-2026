/**
 * Features switched on or off in the code. A change here takes effect once the site is built and
 * restarted (and, for the desktop app, rebuilt).
 */

/** Home's logo breaks into a jigsaw on a click (LogoPuzzle.svelte); off, it turns under the pointer. */
export const LOGO_PUZZLE = false;

/** Home's films (OpeningFilm.svelte) and the dots that pick them: on the development server
 * (npm run dev); the built site and the desktop app open on the logo. */
export const HOME_FILMS = import.meta.env.DEV;
