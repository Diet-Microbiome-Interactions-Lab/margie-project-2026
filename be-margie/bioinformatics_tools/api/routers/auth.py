"""
Authentication endpoints for the BSP API.

POST /v1/auth/register  — create a new user account
POST /v1/auth/login     — exchange credentials for a JWT
GET  /v1/auth/me        — return the current user's profile (requires token)
GET  /v1/auth/policy    — which clusters accounts may be on (public)
"""
import io
import json
import logging
import re
from datetime import datetime, timezone

import paramiko
from fastapi import APIRouter, Depends, HTTPException, Request, status

from bioinformatics_tools.api import access

from bioinformatics_tools.api.auth import (
    create_access_token,
    decrypt_private_key,
    encrypt_private_key,
    get_current_user,
    hash_password,
    verify_password,
)
from bioinformatics_tools.api.database import PROFILE_FIELDS, get_db
from bioinformatics_tools.api.services import read_cache
from bioinformatics_tools.api.services.job_store import job_store
from bioinformatics_tools.api.local_mode import is_local_mode, local_account
from bioinformatics_tools.api.models import (
    DeleteAccount,
    TokenResponse,
    UpdateClusterCredentials,
    UserLogin,
    UserProfile,
    UserRegister,
    UpdateProfile,
)
from bioinformatics_tools.utilities.ssh_connection import (
    close_user_connections,
    ensure_remote_dane_wf,
    make_user_connection,
    remove_margie_files,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/auth', tags=['auth'])

_KEY_CLASSES = (
    paramiko.RSAKey,
    paramiko.Ed25519Key,
    paramiko.ECDSAKey,
)


def _validate_private_key(key_str: str) -> None:
    """
    Attempt to parse the private key with paramiko. Raises HTTP 400 if it
    cannot be loaded as any supported key type (RSA, Ed25519, ECDSA, DSS).
    This catches bad pastes before anything is encrypted or stored.
    """
    for key_class in _KEY_CLASSES:
        try:
            key_class.from_private_key(io.StringIO(key_str.strip()))
            return   # successfully parsed
        except (paramiko.SSHException, Exception):
            continue
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Could not parse the provided SSH private key. '
               'Supported types: RSA, Ed25519, ECDSA, DSS.'
    )


@router.get('/policy')
def policy():
    """Which clusters accounts may be on (MARGIE_ALLOWED_CLUSTERS); empty: any. Public, for the sign-in page."""
    return {'clusters': access.allowed_clusters()}


@router.post('/register', status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, request: Request):
    """
    Create a new BSP user account.

    Validates the private key, encrypts it, then stores the user. Returns the
    new user_id and username. Does not issue a token — requires a separate login.

    In local mode there is no cluster: the account is tied to this computer's
    user and home directory, and no SSH key is stored.
    """
    if is_local_mode():
        return _store_user(body, **local_account(), private_key_encrypted='')

    if not (body.cluster_host and body.cluster_username and body.private_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cluster host, cluster username, and SSH private key are required.'
        )
    # Only the clusters this MARGIE serves; and not too many tries from one address, since
    # each makes the server log in to a cluster.
    access.check_cluster(body.cluster_host)
    address = access.client_address(request)
    if address:
        wait = access.SIGNUP_BY_ADDRESS.wait(address)
        if wait:
            raise access.too_many(wait, 'new accounts from here')
        access.SIGNUP_BY_ADDRESS.count(address)

    _validate_private_key(body.private_key)

    # SSH in before writing anything to DB — proves the credentials work and
    # auto-detects the user's home directory on their cluster.
    try:
        conn = make_user_connection(body.cluster_host, body.cluster_username, body.private_key)
        ssh = conn.connect()
        _, stdout, _ = ssh.exec_command('echo $HOME')
        home_dir = stdout.read().decode().strip()
        pass  # pooled client: closing it would break concurrent requests (see SSHConnection pool)
        if not home_dir:
            raise ValueError('Remote returned empty $HOME')
    except Exception as exc:
        LOGGER.warning(
            'SSH verification failed for %s@%s during registration: %s',
            body.cluster_username, body.cluster_host, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Could not connect to {body.cluster_host} as {body.cluster_username}. '
                'Check your host, username, and private key, and make sure you have added '
                'the BSP public key to your ~/.ssh/authorized_keys on the cluster.'
            )
        )

    try:
        ensure_remote_dane_wf(conn)
    except Exception as exc:
        LOGGER.warning(
            'dane_wf provisioning failed for %s@%s during registration: %s',
            body.cluster_username, body.cluster_host, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Connected, but could not set up the workflow environment on the cluster: {exc}'
        )

    return _store_user(
        body,
        cluster_host=body.cluster_host,
        cluster_username=body.cluster_username,
        home_dir=home_dir,
        private_key_encrypted=encrypt_private_key(body.private_key),
    )


def _store_user(body: UserRegister, *, cluster_host: str, cluster_username: str,
                home_dir: str, private_key_encrypted: str) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    password_hash = hash_password(body.password)

    try:
        with get_db() as db:
            cursor = db.execute(
                '''INSERT INTO users
                       (username, password_hash, cluster_host, cluster_username,
                        home_dir, private_key_encrypted, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (body.username, password_hash, cluster_host,
                 cluster_username, home_dir, private_key_encrypted, created_at)
            )
            user_id = cursor.lastrowid
    except Exception as exc:
        if 'UNIQUE' in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Username already taken'
            )
        LOGGER.exception('Unexpected error during registration')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Registration failed')

    LOGGER.info('New user registered: %s (id=%s)', body.username, user_id)
    return {'user_id': user_id, 'username': body.username}


@router.post('/login', response_model=TokenResponse)
def login(body: UserLogin, request: Request):
    """
    Exchange username + password for a JWT access token.

    Returns a generic error on any failure — never reveals whether the
    username exists. Too many failures lock the username, and the address,
    for a while (api/access.py); an account on a cluster this MARGIE no
    longer accepts cannot sign in.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid credentials'
    )
    name = body.username.strip().lower()
    address = access.client_address(request)
    wait = max(access.SIGNIN_BY_NAME.wait(name), access.SIGNIN_BY_ADDRESS.wait(address) if address else 0)
    if wait:
        raise access.too_many(wait, 'failed sign-ins')

    with get_db() as db:
        row = db.execute(
            'SELECT id, username, password_hash, cluster_host FROM users WHERE username = ?',
            (body.username,)
        ).fetchone()

    if row is None or not verify_password(body.password, row['password_hash']):
        access.SIGNIN_BY_NAME.count(name)
        if address:
            access.SIGNIN_BY_ADDRESS.count(address)
        LOGGER.warning('Failed sign-in for %r from %s (connection from %s)', name, access.raw_address(request) or '?',
                       request.client.host if request.client else '?')
        raise _invalid
    if not is_local_mode():
        access.check_cluster(row['cluster_host'])
    access.SIGNIN_BY_NAME.clear(name)

    token = create_access_token(user_id=row['id'], username=row['username'])
    LOGGER.info('User logged in: %s', body.username)
    return TokenResponse(access_token=token, token_type='bearer')


@router.get('/me', response_model=UserProfile)
def me(current_user: dict = Depends(get_current_user)):
    """
    Return the profile of the currently authenticated user.

    Used by the frontend to hydrate state after a page refresh using a
    stored token. Never returns the password hash or encrypted private key.
    """
    return _profile(current_user['user_id'])


def _profile(user_id: int) -> UserProfile:
    """Returns a user's profile, with their own details; never the password or the key."""
    with get_db() as db:
        row = db.execute(
            'SELECT id, username, cluster_host, cluster_username, home_dir, created_at, notify_runs, '
            + ', '.join(PROFILE_FIELDS) + ' FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    return UserProfile(
        user_id=row['id'],
        username=row['username'],
        cluster_host=row['cluster_host'],
        cluster_username=row['cluster_username'],
        home_dir=row['home_dir'],
        created_at=row['created_at'],
        notify_runs=bool(row['notify_runs']),
        **{f: row[f] or '' for f in PROFILE_FIELDS},
    )


_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_ORCID = re.compile(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')


@router.put('/profile', response_model=UserProfile)
def update_profile(body: UpdateProfile, current_user: dict = Depends(get_current_user)):
    """
    Saves the details a user keeps about themselves (name, email, institution,
    department or lab, ORCID). Fields left out are kept; an empty one is cleared.
    """
    fields = body.model_dump(exclude_none=True)
    notify = fields.pop('notify_runs', None)
    given = {k: v.strip() for k, v in fields.items()}
    if given.get('email') and not _EMAIL.match(given['email']):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='That email address does not look right.')
    if given.get('orcid'):
        given['orcid'] = given['orcid'].removeprefix('https://orcid.org/').upper()
        if not _ORCID.match(given['orcid']):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='An ORCID iD looks like 0000-0002-1825-0097.')
    if notify is not None:
        given['notify_runs'] = int(notify)
    if given:
        with get_db() as db:
            db.execute(
                'UPDATE users SET ' + ', '.join(f'{k} = ?' for k in given) + ' WHERE id = ?',
                (*given.values(), current_user['user_id']),
            )
            db.commit()
    return _profile(current_user['user_id'])


# The look's parts: the website's settings (prefs) and the look it opens with (default).
LOOK_PARTS = ('prefs', 'default')
LOOK_MAX = 64 * 1024


def _look(user_id: int) -> dict:
    with get_db() as db:
        row = db.execute('SELECT ui_look FROM users WHERE id = ?', (user_id,)).fetchone()
    try:
        look = json.loads(row['ui_look']) if row and row['ui_look'] else {}
    except ValueError:
        look = {}
    return {k: v for k, v in look.items() if k in LOOK_PARTS and isinstance(v, dict)} if isinstance(look, dict) else {}


@router.get('/look')
def get_look(current_user: dict = Depends(get_current_user)):
    """Returns the website's look kept with the account ({prefs, default}); {} before one is kept."""
    return _look(current_user['user_id'])


@router.put('/look')
def save_look(body: dict, current_user: dict = Depends(get_current_user)):
    """
    Keeps the website's look with the account, so each browser signed in to it shows the same one.
    The parts sent (prefs, default) replace the kept ones; the website checks them as it reads them.
    """
    given = {k: v for k, v in body.items() if k in LOOK_PARTS}
    if not given or not all(isinstance(v, dict) for v in given.values()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Send prefs or default, as objects.')
    look = {**_look(current_user['user_id']), **given}
    text = json.dumps(look, separators=(',', ':'))
    if len(text) > LOOK_MAX:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail='The look is too large to keep.')
    with get_db() as db:
        db.execute('UPDATE users SET ui_look = ? WHERE id = ?', (text, current_user['user_id']))
        db.commit()
    return {'saved': True}


@router.post('/delete-account')
def delete_account(body: DeleteAccount, current_user: dict = Depends(get_current_user)):
    """
    Deletes the MARGIE account: its sign-in, profile and stored cluster key, and in the cluster
    account's home the stored language-model keys and the copy of MARGIE (remove_margie_files);
    config.yaml, databases and results stay. Those files stay too while another MARGIE account
    uses the same cluster account, and in local mode. Asks for the password again, waits while
    a run is going, and deletes nothing when the files cannot be removed.
    """
    with get_db() as db:
        row = db.execute('SELECT password_hash FROM users WHERE id = ?', (current_user['user_id'],)).fetchone()
    if row is None or not verify_password(body.password, row['password_hash']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='That password does not match this account.')
    going = job_store.going_for(current_user['user_id'])
    if going:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f'A run is going ({going[0]}): stop it, or wait for it to finish, before deleting the account.')
    host, cluster_user = current_user['cluster_host'], current_user['cluster_username']
    with get_db() as db:
        shared = db.execute('SELECT count(*) FROM users WHERE cluster_host = ? AND cluster_username = ? AND id != ?',
                            (host, cluster_user, current_user['user_id'])).fetchone()[0]
    removed = False
    if not shared and not is_local_mode():
        conn = make_user_connection(host, cluster_user, decrypt_private_key(current_user['private_key_encrypted']))
        problem = remove_margie_files(conn)
        if problem:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"Could not remove MARGIE's files from your home on the cluster ({problem}). Nothing was deleted; try again.")
        removed = True
    with get_db() as db:
        db.execute('DELETE FROM users WHERE id = ?', (current_user['user_id'],))
        db.commit()
    read_cache.drop(current_user['user_id'])
    close_user_connections(host, cluster_user)
    LOGGER.info('Deleted the account %r (files in the cluster home %s)', current_user['username'], 'removed' if removed else 'kept')
    return {'deleted': True, 'cluster_files_removed': removed}


@router.put('/update-credentials')
def update_credentials(body: UpdateClusterCredentials, current_user: dict = Depends(get_current_user)):
    """
    Update the user's cluster credentials (host, username, and/or private key).

    Validates any new private key and tests the SSH connection before updating.
    At least one field must be provided.
    """
    # Another cluster or account: what was read from the old one no longer holds.
    read_cache.drop(current_user['user_id'])
    if not any([body.cluster_host, body.cluster_username, body.private_key]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='At least one field (cluster_host, cluster_username, or private_key) must be provided'
        )

    # Get current credentials from DB
    with get_db() as db:
        row = db.execute(
            'SELECT cluster_host, cluster_username, private_key_encrypted, home_dir FROM users WHERE id = ?',
            (current_user['user_id'],)
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    # Build the effective credentials (new values override old)
    from bioinformatics_tools.api.auth import decrypt_private_key

    if body.cluster_host:
        access.check_cluster(body.cluster_host)
    new_host = body.cluster_host or row['cluster_host']
    new_username = body.cluster_username or row['cluster_username']
    new_key = body.private_key if body.private_key else decrypt_private_key(row['private_key_encrypted'])

    # Validate private key if provided
    if body.private_key:
        _validate_private_key(body.private_key)

    # Test SSH connection with the new credentials
    try:
        conn = make_user_connection(new_host, new_username, new_key)
        ssh = conn.connect()
        _, stdout, _ = ssh.exec_command('echo $HOME')
        home_dir = stdout.read().decode().strip()
        pass  # pooled client: closing it would break concurrent requests (see SSHConnection pool)
        if not home_dir:
            raise ValueError('Remote returned empty $HOME')
    except Exception as exc:
        LOGGER.warning(
            'SSH verification failed for %s@%s during credential update: %s',
            new_username, new_host, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Could not connect to {new_host} as {new_username}. '
                'Check your host, username, and private key.'
            )
        )

    # The new account may never have run a job here, so dane_wf is provisioned too.
    try:
        ensure_remote_dane_wf(conn)
    except Exception as exc:
        LOGGER.warning(
            'dane_wf provisioning failed for %s@%s during credential update: %s',
            new_username, new_host, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Connected, but could not set up the workflow environment on the cluster: {exc}'
        )

    # Update database
    updates = {}
    if body.cluster_host:
        updates['cluster_host'] = body.cluster_host
    if body.cluster_username:
        updates['cluster_username'] = body.cluster_username
    if body.private_key:
        updates['private_key_encrypted'] = encrypt_private_key(body.private_key)

    # Always update home_dir in case it changed
    updates['home_dir'] = home_dir

    if updates:
        set_clause = ', '.join(f'{key} = ?' for key in updates.keys())
        values = list(updates.values()) + [current_user['user_id']]

        with get_db() as db:
            db.execute(
                f'UPDATE users SET {set_clause} WHERE id = ?',
                values
            )

    LOGGER.info('User %s updated cluster credentials', current_user['username'])
    return {'success': True, 'message': 'Cluster credentials updated successfully'}
