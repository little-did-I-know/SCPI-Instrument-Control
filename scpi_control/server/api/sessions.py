# scpi_control/server/api/sessions.py
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["sessions"])


def get_manager(request: Request):
    return request.app.state.manager


@router.get("/sessions")
def list_sessions(request: Request):
    from scpi_control.server.schemas import session_out

    return [session_out(s) for s in get_manager(request).list()]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request):
    from scpi_control.server.schemas import session_out

    session = get_manager(request).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session {0}".format(session_id))
    return session_out(session)
