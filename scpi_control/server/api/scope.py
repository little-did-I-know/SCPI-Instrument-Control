# scpi_control/server/api/scope.py
import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Request

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.api.sessions import require_session
from scpi_control.server.schemas import ALLOWED_COUPLING, ChannelPatch, TimebasePatch, TriggerPatch
from scpi_control.server.sessions import InstrumentSession, read_state

router = APIRouter(tags=["scope"])


async def run_job(session: InstrumentSession, fn: Callable) -> Any:
    return await asyncio.wrap_future(session.submit(fn))


async def mutate(session: InstrumentSession, fn: Callable) -> dict:
    """Run a mutation, then read + broadcast + return the fresh state."""
    await run_job(session, fn)
    state = await run_job(session, read_state)
    session.publish({"type": "state", "state": state})
    return state


@router.get("/sessions/{session_id}/scope/state")
async def get_state(session_id: str, request: Request):
    session = require_session(request, session_id)
    return await run_job(session, read_state)


@router.patch("/sessions/{session_id}/scope/channels/{channel}")
async def patch_channel(session_id: str, channel: int, body: ChannelPatch, request: Request):
    session = require_session(request, session_id)
    if body.coupling is not None and body.coupling.upper() not in ALLOWED_COUPLING:
        raise InvalidParameterError("invalid coupling: {0}".format(body.coupling))

    def apply(scope):
        ch = scope.get_channel(channel)
        if ch is None:
            raise InvalidParameterError("channel {0} not available".format(channel))
        if body.enabled is not None:
            ch.enabled = body.enabled
        if body.voltage_scale is not None:
            ch.voltage_scale = body.voltage_scale
        if body.voltage_offset is not None:
            ch.voltage_offset = body.voltage_offset
        if body.coupling is not None:
            ch.coupling = body.coupling.upper()
        if body.probe_ratio is not None:
            ch.probe_ratio = body.probe_ratio

    return await mutate(session, apply)


@router.patch("/sessions/{session_id}/scope/timebase")
async def patch_timebase(session_id: str, body: TimebasePatch, request: Request):
    session = require_session(request, session_id)

    def apply(scope):
        scope.timebase = body.timebase

    return await mutate(session, apply)


@router.patch("/sessions/{session_id}/scope/trigger")
async def patch_trigger(session_id: str, body: TriggerPatch, request: Request):
    session = require_session(request, session_id)

    def apply(scope):
        trig = scope.trigger
        if body.mode is not None:
            trig.mode = body.mode.upper()
        if body.source is not None:
            trig.source = body.source
        if body.level is not None:
            trig.level = body.level
        if body.slope is not None:
            trig.slope = body.slope.upper()
        if body.coupling is not None:
            trig.coupling = body.coupling.upper()

    return await mutate(session, apply)


_RUN_OPS = {
    "run": lambda scope: scope.run(),
    "stop": lambda scope: scope.stop(),
    "single": lambda scope: scope.trigger_single(),
    "auto": lambda scope: scope.auto_setup(),
}


@router.post("/sessions/{session_id}/scope/{op}")
async def run_op(session_id: str, op: str, request: Request):
    session = require_session(request, session_id)
    fn = _RUN_OPS.get(op)
    if fn is None:
        raise InvalidParameterError("unknown operation: {0}".format(op))
    return await mutate(session, fn)
