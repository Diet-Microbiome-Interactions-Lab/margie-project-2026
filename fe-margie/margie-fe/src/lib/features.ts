/**
 * Features switched on or off in the code. A change here takes effect once the site is built and
 * restarted (and, for the desktop app, rebuilt).
 */

/** Home's films (OpeningFilm.svelte) and the dots that pick them for everyone: on the development
 * server (npm run dev); on the built site and the desktop app, for accounts that unlocked the logo
 * animations (Customize → Motion). */
export const HOME_FILMS = import.meta.env.DEV;
