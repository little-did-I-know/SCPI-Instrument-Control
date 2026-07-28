"""Admin routes. Unauthenticated by design -- see admin/app.py."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

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
