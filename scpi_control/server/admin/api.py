"""Admin routes. Unauthenticated by design -- see admin/app.py."""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from scpi_control.server.schemas import session_out

router = APIRouter()


class InvitationCreate(BaseModel):
    name: str


def _row(entry, link: Optional[str] = None) -> dict:
    row = {"id": entry["id"], "name": entry["name"], "code": entry["code"], "expires": entry["expires"]}
    if link is not None:
        row["link"] = link
    return row


@router.get("/identities")
async def list_identities(request: Request):
    return request.app.state.tokens.summary()


@router.delete("/identities/{name}", status_code=204)
async def revoke_identity(name: str, request: Request):
    if not request.app.state.tokens.revoke(name):
        raise HTTPException(status_code=404, detail="no identity named {0!r}".format(name))
    return None


@router.get("/invitations")
async def list_invitations(request: Request):
    """Live invitations. No link: only the nonce's hash is stored, so a link
    cannot be reconstructed after creation -- by design. The code is enough to
    read down a phone, which is what this listing is for."""
    return [_row(entry) for entry in request.app.state.invitations.pending_list()]


@router.post("/invitations")
async def create_invitation(body: InvitationCreate, request: Request):
    invitations = request.app.state.invitations
    # Identify the new row by which id appeared, not by matching on the code.
    # create() returns (link, code) and not the id, and codes are not checked
    # for collisions -- two live invitations can share one, in which case
    # matching by code would attach this link to somebody else's invitation and
    # hand the caller a credential for the wrong identity. Ids are unique.
    before = {row["id"] for row in invitations.pending_list()}
    try:
        link_nonce, _code = invitations.create(body.name)
    except ValueError as exc:
        # An empty or whitespace-only name; mirrors TokenStore.mint's guard.
        raise HTTPException(status_code=400, detail=str(exc))
    entry = next(row for row in invitations.pending_list() if row["id"] not in before)
    base = request.app.state.base_url or "http://127.0.0.1:8765/"
    return _row(entry, link="{0}?invite={1}".format(base, link_nonce))


@router.delete("/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(invitation_id: str, request: Request):
    if not request.app.state.invitations.cancel(invitation_id):
        raise HTTPException(status_code=404, detail="no invitation with that id")
    return None


@router.get("/sessions")
async def list_sessions(request: Request):
    """Every open session. Reuses the gateway's own serializer plus idle time.

    NOTE: this is a *different* /api/sessions from the gateway's authenticated
    one -- same path, different app, different port. Do not "share" the router:
    tests/test_server_admin_api.py::test_the_main_app_serves_no_admin_routes
    exists because doing so would hand every LAN token-holder admin powers.
    """
    now = time.monotonic()
    return [dict(session_out(session), idle_seconds=round(now - session.owner_last_active, 1)) for session in request.app.state.manager.list()]


@router.post("/sessions/{session_id}/release", status_code=204)
async def release_session(session_id: str, request: Request):
    session = request.app.state.manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="no session with that id")
    session.owner = ""
    return None


@router.delete("/sessions/{session_id}", status_code=204)
async def close_session(session_id: str, request: Request):
    if not request.app.state.manager.delete(session_id):
        raise HTTPException(status_code=404, detail="no session with that id")
    return None
