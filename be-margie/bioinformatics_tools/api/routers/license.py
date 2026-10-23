"""License-gate endpoints under /v1/license (auth required).

A user accepts the current terms once per terms version before running a workflow;
acceptance goes to the app database plus a copy with the client IP in the depot.
Routes: GET /terms, GET /status, POST /accept, POST /revoke.

The copy is written on the user's cluster, as the user, over SSH: in LICENSE_RECORDS_DIR
(the group's records folder) when it can be written there, else in the user's own
~/.local/share/bioinformatics-tools/licensing-records. The API itself need not see that
folder (it may run elsewhere, as on a hosting platform).
"""
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from bioinformatics_tools.api.auth import get_current_user
from bioinformatics_tools.api import licensing
from bioinformatics_tools.api.licensing.catalog import record_subdir
from bioinformatics_tools.api.local_mode import is_local_mode

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/license", tags=["license"])


class LicenseAccept(BaseModel):
    accepted_items: list[str]          # acknowledgment ids the user checked
    terms_version: str                 # version the user was shown (must match current)
    terms_sha256: str | None = None    # optional integrity check of the shown terms
    usage_type: str                    # "academic" | "commercial"
    licensed_tools: list[str] = []     # tool ids the user holds their own license for


def _client_ip(request: Request) -> str | None:
    """Returns the client IP, preferring X-Forwarded-For (first hop) behind a proxy."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else None


@router.get("/terms")
def get_terms(current_user: dict = Depends(get_current_user)):
    """Returns the terms, version, tool catalog and acknowledgments for the license gate."""
    return licensing.build_terms_payload()


@router.get("/status")
def get_status(current_user: dict = Depends(get_current_user)):
    """Returns whether the user accepted the current terms, plus the entitlement
    that decides which tools the analyze page disables."""
    terms = licensing.load_terms()
    accepted = licensing.has_accepted_current_terms(current_user["username"])
    entitlement = licensing.get_entitlement(current_user["username"])
    disabled = sorted(
        licensing.disabled_tool_ids(
            entitlement.get("usage_type"), entitlement.get("licensed_tools")
        )
    )
    return {
        "accepted": accepted,
        "current_terms_version": terms["version"],
        "usage_type": entitlement.get("usage_type"),
        "licensed_tools": entitlement.get("licensed_tools", []),
        "disabled_tools": disabled,
    }


@router.post("/revoke")
def revoke_terms(current_user: dict = Depends(get_current_user)):
    """Revokes the user's acceptance of the current terms so the gate prompts again.

    Clears only the app-side state; the depot record of the acceptance is kept."""
    removed = licensing.revoke_current_acceptance(current_user["username"])
    terms = licensing.load_terms()
    LOGGER.info(
        "License revoked: user=%s version=%s rows_removed=%d",
        current_user["username"], terms["version"], removed,
    )
    return {"revoked": True, "rows_removed": removed, "current_terms_version": terms["version"]}


def _save_on_cluster(current_user: dict):
    """Returns a record saver (see licensing.record_acceptance) that writes on the user's cluster."""
    from bioinformatics_tools.api.routers.ssh import _build_connection
    from bioinformatics_tools.utilities import ssh_sftp

    def save(*, username: str, record: dict, terms_text: str, timestamp: str) -> str:
        conn = _build_connection(current_user)
        home = current_user["home_dir"].rstrip("/")
        roots = [r for r in (os.getenv("LICENSE_RECORDS_DIR", "").rstrip("/"),
                             f"{home}/.local/share/bioinformatics-tools/licensing-records") if r]
        last: Exception | None = None
        for root in roots:
            dest = f"{root}/{record_subdir(username, timestamp)}"
            try:
                ssh_sftp.write_remote_text_file(f"{dest}/terms.txt", terms_text, connection=conn)
                ssh_sftp.write_remote_text_file(f"{dest}/record.json", json.dumps(record, indent=2, ensure_ascii=False), connection=conn)
                return dest
            except Exception as exc:  # noqa: BLE001 — the next folder is tried
                LOGGER.warning("Could not write the licence record in %s: %s", root, exc)
                last = exc
        raise last or RuntimeError("no folder for licence records")

    return save


@router.post("/accept")
def accept_terms(
    body: LicenseAccept,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Records the user's acceptance after checking the shown terms version and hash."""
    terms = licensing.load_terms()

    if body.terms_version != terms["version"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The licensing terms have changed since this page loaded. "
                "Please reload and review the current terms before accepting."
            ),
        )
    if body.terms_sha256 and body.terms_sha256 != terms["sha256"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Terms integrity check failed. Please reload and try again.",
        )

    ip_address = _client_ip(request)
    user_agent = request.headers.get("user-agent")

    try:
        result = licensing.record_acceptance(
            username=current_user["username"],
            accepted_items=body.accepted_items,
            ip_address=ip_address,
            user_agent=user_agent,
            usage_type=body.usage_type,
            licensed_tools=body.licensed_tools,
            save=None if is_local_mode() else _save_on_cluster(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    LOGGER.info(
        "License accepted: user=%s version=%s ip=%s depot=%s",
        current_user["username"], result["terms_version"], ip_address,
        result.get("depot_record_path"),
    )
    if result.get("depot_record_error"):
        # Acceptance is still valid; only the depot copy failed.
        LOGGER.error(
            "License depot record write FAILED for user=%s: %s",
            current_user["username"], result["depot_record_error"],
        )

    return {"accepted": True, **result}
