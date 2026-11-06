/**
 * Features switched on or off in the code. A change here takes effect once the site is built and
 * restarted (and, for the desktop app, rebuilt).
 */

/** Home's logo breaks into a jigsaw on a click (LogoPuzzle.svelte) for everyone; off, it does so for
 * accounts that unlocked the logo animations (Customize → Motion), and turns under the pointer for others. */
export const LOGO_PUZZLE = false;

/** Home's films (OpeningFilm.svelte) and the dots that pick them for everyone: on the development
 * server (npm run dev); on the built site and the desktop app, for accounts that unlocked the logo
 * animations (Customize → Motion). */
export const HOME_FILMS = import.meta.env.DEV;
