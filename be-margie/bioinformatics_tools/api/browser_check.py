"""
A browser MARGIE does not know confirms a sign-in with a code. After the password, MARGIE emails a
six-digit code to the account's Purdue address (the profile's email, for an account on another
cluster), sent by the cluster with its mail command over the account's own key, as run emails are
(services/run_mail.py). Reading it takes that mailbox's own sign-in: at Purdue, Purdue Login with
Duo. A confirmed browser may be remembered for 7, 15, 20 or 30 days; the browser an account is made
in is remembered for 15. Each new browser that signs in is told to the same address. The desktop
app (local mode) has no check.

Codes and remembered browsers are kept as keyed hashes (BSP_SECRET_KEY).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

from bioinformatics_tools.api import access
from bioinformatics_tools.api.database import get_db
from bioinformatics_tools.api.services import run_mail

LOGGER = logging.getLogger(__name__)

# How long a confirmed browser may be remembered (the sign-in page's choice), and the browser an
# account is made in.
REMEMBER_DAYS = (7, 15, 20, 30)
SIGNUP_DAYS = 15
# A code works for ten minutes and five tries; five codes an hour per username.
CODE_MINUTES = 10
CODE_TRIES = 5
CODES_BY_NAME = access.Guard(limit=5, window=60 * 60, lock=60 * 60)

_KEY = (os.getenv('BSP_SECRET_KEY') or '').encode()


class CheckError(Exception):
    """A code that cannot be sent or is not right; the message goes to the sign-in page."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(text: str) -> str:
    return hmac.new(_KEY, text.encode(), hashlib.sha256).hexdigest()


# ---- which browser ----

_BROWSERS = ((r'Edg/', 'Edge'), (r'OPR/|Opera', 'Opera'), (r'Firefox/', 'Firefox'), (r'Chrome/', 'Chrome'), (r'Safari/', 'Safari'))
_SYSTEMS = ((r'iPhone|iPad', 'iOS'), (r'Android', 'Android'), (r'Macintosh|Mac OS X', 'macOS'), (r'Windows', 'Windows'),
            (r'CrOS', 'ChromeOS'), (r'Linux', 'Linux'))


def label(request) -> str:
    """'Chrome on macOS, from 203.0.113.5': the browser, its system and the address it came from."""
    agent = request.headers.get('user-agent') or ''
    browser = next((name for pat, name in _BROWSERS if re.search(pat, agent)), 'A browser')
    system = next((name for pat, name in _SYSTEMS if re.search(pat, agent)), '')
    where = access.raw_address(request)
    return f"{browser}{f' on {system}' if system else ''}{f', from {where}' if where else ''}"[:160]


# ---- remembered browsers ----

def known(user_id: int, token: str | None) -> bool:
    """Whether this browser was confirmed for the account and is still remembered."""
    if not token:
        return False
    now = _now().isoformat()
    with get_db() as db:
        row = db.execute('SELECT id, expires_at FROM trusted_browsers WHERE user_id = ? AND token_hash = ?',
                         (user_id, _digest(f'b:{token}'))).fetchone()
        if row is None:
            return False
        if row['expires_at'] <= now:
            db.execute('DELETE FROM trusted_browsers WHERE id = ?', (row['id'],))
            return False
        db.execute('UPDATE trusted_browsers SET last_used_at = ? WHERE id = ?', (now, row['id']))
    return True


def remember(user_id: int, days: int, where: str) -> str:
    """Remembers a browser for `days`; returns the token it keeps (sent with its next sign-in)."""
    token = secrets.token_urlsafe(32)
    now = _now()
    with get_db() as db:
        db.execute('DELETE FROM trusted_browsers WHERE user_id = ? AND expires_at <= ?', (user_id, now.isoformat()))
        db.execute('INSERT INTO trusted_browsers (user_id, token_hash, label, created_at, expires_at, last_used_at) '
                   'VALUES (?, ?, ?, ?, ?, ?)',
                   (user_id, _digest(f'b:{token}'), where, now.isoformat(), (now + timedelta(days=days)).isoformat(), now.isoformat()))
    return token


def browsers(user_id: int) -> list[dict]:
    """The account's remembered browsers, newest first."""
    with get_db() as db:
        rows = db.execute('SELECT id, label, created_at, expires_at, last_used_at FROM trusted_browsers '
                          'WHERE user_id = ? AND expires_at > ? ORDER BY created_at DESC', (user_id, _now().isoformat())).fetchall()
    return [dict(r) for r in rows]


def forget(user_id: int, browser_id: int | None = None) -> int:
    """Forgets one remembered browser, or all of the account's; returns how many."""
    with get_db() as db:
        if browser_id is None:
            cur = db.execute('DELETE FROM trusted_browsers WHERE user_id = ?', (user_id,))
        else:
            cur = db.execute('DELETE FROM trusted_browsers WHERE user_id = ? AND id = ?', (user_id, browser_id))
    return cur.rowcount


def forget_account(user_id: int) -> None:
    """Removes an account's remembered browsers and pending codes (the account is deleted)."""
    with get_db() as db:
        db.execute('DELETE FROM trusted_browsers WHERE user_id = ?', (user_id,))
        db.execute('DELETE FROM signin_codes WHERE user_id = ?', (user_id,))


# ---- the code ----

def address(user: dict) -> str:
    """Where codes and notices go: the account's Purdue address on a Purdue cluster, else the profile's email."""
    to = run_mail.recipients(user)
    return to[0] if to else ''


def masked(addr: str) -> str:
    """b…3@purdue.edu: enough to know which address, not the whole of it."""
    name, _, domain = addr.partition('@')
    return f'{name[:1]}…{name[-1:] if len(name) > 1 else ""}@{domain}' if domain else addr


def start(user: dict, where: str, connect) -> dict:
    """Emails a new code for the account and returns {challenge, to}; an earlier code stops working.
    connect() gives the account's cluster connection. Raises CheckError when it cannot be sent."""
    to = address(user)
    if not to:
        raise CheckError('This account has no email address for a sign-in code. Sign in from a browser you have used '
                         'before and add one on your User profile.')
    code = f'{secrets.randbelow(10 ** 6):06d}'
    challenge = secrets.token_urlsafe(18)
    subject = f'MARGIE sign-in code: {code}'
    body = (f'Someone is signing in to MARGIE as {user["username"]} from a browser MARGIE does not know yet:\n'
            f'{where}, at {_now().strftime("%Y-%m-%d %H:%M UTC")}.\n\n'
            f'To finish signing in, enter this code: {code}\nIt works for {CODE_MINUTES} minutes.\n\n'
            'If this was not you, someone has your MARGIE password: change it, and forget your remembered browsers '
            'on your User profile.\n\nThis is an automatic message from MARGIE.')
    try:
        sent = run_mail.send(connect(), [to], subject, body)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning('Sign-in code for %s not sent: %s', user['username'], exc)
        sent = False
    if not sent:
        raise CheckError('MARGIE could not send a sign-in code to your email: your cluster account could not be reached. '
                         'Sign in from a browser you have used before, or try again later.')
    now = _now()
    with get_db() as db:
        db.execute('DELETE FROM signin_codes WHERE user_id = ? OR expires_at <= ?', (user['id'], now.isoformat()))
        db.execute('INSERT INTO signin_codes (id, user_id, code_hash, label, created_at, expires_at, attempts) '
                   'VALUES (?, ?, ?, ?, ?, ?, 0)',
                   (challenge, user['id'], _digest(f'c:{challenge}:{code}'), where, now.isoformat(),
                    (now + timedelta(minutes=CODE_MINUTES)).isoformat()))
    return {'challenge': challenge, 'to': masked(to)}


def check(challenge: str, code: str) -> tuple[int, str]:
    """Returns (user id, the browser's label) for the right code; a code works once. Raises CheckError."""
    code = re.sub(r'\s', '', str(code or ''))
    problem = ''
    # The count and the deletions are kept before the error is raised (get_db rolls back on one).
    with get_db() as db:
        row = db.execute('SELECT * FROM signin_codes WHERE id = ?', (str(challenge or ''),)).fetchone()
        if row is None or row['expires_at'] <= _now().isoformat() or row['attempts'] >= CODE_TRIES:
            if row is not None:
                db.execute('DELETE FROM signin_codes WHERE id = ?', (row['id'],))
            problem = 'That code has expired or was tried too often. Sign in again for a new one.'
        elif not hmac.compare_digest(row['code_hash'], _digest(f'c:{row["id"]}:{code}')):
            db.execute('UPDATE signin_codes SET attempts = attempts + 1 WHERE id = ?', (row['id'],))
            left = CODE_TRIES - row['attempts'] - 1
            problem = (f'That code is not right. {left} tr{"y" if left == 1 else "ies"} left.' if left else
                       'That code is not right. Sign in again for a new one.')
        else:
            db.execute('DELETE FROM signin_codes WHERE id = ?', (row['id'],))
    if problem:
        raise CheckError(problem)
    return row['user_id'], row['label'] or ''


def notify(user: dict, where: str, days: int, connect) -> None:
    """Tells the account's address that a new browser signed in; in the background, and a failure
    leaves the sign-in as it is."""
    to = address(user)
    if not to:
        return
    kept = f'It is remembered for {days} days.' if days else 'It is not remembered: the next sign-in there asks for a code again.'
    body = (f'MARGIE: your account {user["username"]} signed in from a new browser:\n{where}, at '
            f'{_now().strftime("%Y-%m-%d %H:%M UTC")}.\n{kept}\n\n'
            'If this was not you, change your MARGIE password and forget your remembered browsers on your User profile.\n\n'
            'This is an automatic message from MARGIE.')

    def send() -> None:
        try:
            run_mail.send(connect(), [to], 'MARGIE: a new browser signed in', body)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning('New-browser notice for %s not sent: %s', user['username'], exc)

    threading.Thread(target=send, daemon=True).start()
