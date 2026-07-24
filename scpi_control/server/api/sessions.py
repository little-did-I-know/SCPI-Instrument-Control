# scpi_control/server/api/sessions.py
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from scpi_control.models import MODEL_REGISTRY
from scpi_control.server.schemas import ModelOut, OwnerPut, SessionCreate, session_out

router = APIRouter(tags=["sessions"])


def get_manager(request: Request):
    return request.app.state.manager


def require_session(request: Request, session_id: str):
    session = get_manager(request).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session {0}".format(session_id))
    identity = getattr(request.state, "identity", "")
    # A read from the owner is still owner activity: require_owner only fires
    # on writes, so without this an owner who is watching state/reads during a
    # capture (the normal case) would look idle and be claimable out from
    # under them. Only refresh for the owner themselves -- a non-owner's read
    # must never extend someone else's claim-protection window.
    if session.owner and identity == session.owner:
        session.touch()
    return session


@router.get("/models")
def list_models():
    caps = sorted(MODEL_REGISTRY.values(), key=lambda c: c.model_name)
    return [ModelOut(model_name=c.model_name, series=c.series, num_channels=c.num_channels, bandwidth_mhz=c.bandwidth_mhz, dialect=c.dialect) for c in caps]


@router.get("/sessions")
def list_sessions(request: Request):
    return [session_out(s) for s in get_manager(request).list()]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request):
    return session_out(require_session(request, session_id))


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, request: Request):
    label = body.label or (body.model or ("Mock scope" if body.mock else body.address or ""))
    # InstrumentSession.open blocks on connect; keep the event loop free.
    session = await run_in_threadpool(get_manager(request).create, label, address=body.address, port=body.port, mock=body.mock, model=body.model, owner=getattr(request.state, "identity", ""))
    return session_out(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request):
    from scpi_control.server.ownership import require_owner

    require_owner(request, session_id)
    await run_in_threadpool(get_manager(request).delete, session_id)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/claim")
async def claim_session(session_id: str, request: Request):
    from scpi_control.server.ownership import NotOwnerError, abandon_after, claim

    session = require_session(request, session_id)
    identity = getattr(request.state, "identity", "")
    retry_after = claim(session, identity, abandon_after(request))
    if retry_after is not None:
        raise NotOwnerError(session.owner, time.monotonic() - session.owner_last_active)
    return session_out(session)


@router.post("/sessions/{session_id}/owner")
async def set_owner(session_id: str, body: OwnerPut, request: Request):
    from scpi_control.server.ownership import require_owner

    session = require_owner(request, session_id)
    session.owner = body.name
    session.touch()
    return session_out(session)
