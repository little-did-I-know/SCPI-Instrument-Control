# scpi_control/server/api/sessions.py
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from scpi_control.models import MODEL_REGISTRY
from scpi_control.server.schemas import ModelOut, SessionCreate, session_out

router = APIRouter(tags=["sessions"])


def get_manager(request: Request):
    return request.app.state.manager


def require_session(request: Request, session_id: str):
    session = get_manager(request).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session {0}".format(session_id))
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
