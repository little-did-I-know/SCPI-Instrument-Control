# scpi_control/server/api/psu.py
import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Request

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.adapters import read_psu_outputs
from scpi_control.server.api.sessions import require_kind, require_session
from scpi_control.server.ownership import require_owner
from scpi_control.server.schemas import PsuEnablePatch, PsuOutputPatch
from scpi_control.server.sessions import InstrumentSession

router = APIRouter(tags=["psu"])


async def run_job(session: InstrumentSession, fn: Callable) -> Any:
    return await asyncio.wrap_future(session.submit(fn))


async def mutate(session: InstrumentSession, fn: Callable) -> dict:
    """Run a mutation, then read + broadcast + return the fresh outputs."""
    await run_job(session, fn)
    outputs = await run_job(session, read_psu_outputs)
    session.publish({"type": "state", "kind": "psu", "outputs": outputs})
    return {"outputs": outputs}


@router.get("/sessions/{session_id}/psu/state")
async def get_state(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "psu")
    outputs = await run_job(session, read_psu_outputs)
    return {"outputs": outputs}


@router.patch("/sessions/{session_id}/psu/outputs/{n}")
async def patch_output(session_id: str, n: int, body: PsuOutputPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "psu")

    def apply(psu):
        output = psu.get_output(n)
        if output is None:
            raise InvalidParameterError("output {0} not available".format(n))
        if body.voltage is not None:
            output.voltage = body.voltage
        if body.current is not None:
            output.current = body.current

    return await mutate(session, apply)


@router.patch("/sessions/{session_id}/psu/outputs/{n}/enable")
async def patch_enable(session_id: str, n: int, body: PsuEnablePatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "psu")

    def apply(psu):
        output = psu.get_output(n)
        if output is None:
            raise InvalidParameterError("output {0} not available".format(n))
        output.enabled = body.enabled

    return await mutate(session, apply)
