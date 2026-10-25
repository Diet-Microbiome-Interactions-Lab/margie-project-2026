/**
 * The statement a user types once per computer or cluster account, before the first installation,
 * database download or database setup: it confirms the upstream licences and MARGIE's terms.
 */
export const INSTALL_STATEMENT =
	'I understand the licenses of the upstream tools, I have the licenses they require, and I accept the license terms agreement of MARGIE.';

/** The text as compared: exactly as typed, apart from spaces at either end. */
export const normaliseStatement = (s: unknown) => String(s ?? '').trim();
