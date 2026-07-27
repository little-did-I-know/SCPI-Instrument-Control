# scpi_control/server/api/awg.py
from typing import Callable

from fastapi import APIRouter, Request

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.adapters import read_awg_channels
from scpi_control.server.api.sessions import require_kind, require_session, run_job
from scpi_control.server.ownership import require_owner
from scpi_control.server.schemas import ALLOWED_FUNCTIONS, AwgChannelPatch, AwgEnablePatch
from scpi_control.server.sessions import InstrumentSession

router = APIRouter(tags=["awg"])


async def mutate(session: InstrumentSession, fn: Callable) -> dict:
    """Run a mutation, then read + broadcast + return the fresh channels."""
    await run_job(session, fn)
    channels = await run_job(session, read_awg_channels)
    session.publish({"type": "state", "kind": "awg", "channels": channels})
    return {"channels": channels}


@router.get("/sessions/{session_id}/awg/state")
async def get_state(session_id: str, request: Request):
    session = require_session(request, session_id)
    require_kind(session, "awg")
    channels = await run_job(session, read_awg_channels)
    return {"channels": channels}


@router.patch("/sessions/{session_id}/awg/channels/{n}")
async def patch_channel(session_id: str, n: int, body: AwgChannelPatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "awg")

    function = None
    if body.function is not None:
        # Validated here rather than inside the job so a typo is a named 400
        # instead of a driver error surfacing from the worker thread.
        function = body.function.strip().upper()
        if function not in ALLOWED_FUNCTIONS:
            raise InvalidParameterError("unsupported function {0!r}".format(body.function))

    def apply(awg):
        channel = awg.get_channel(n)
        if channel is None:
            raise InvalidParameterError("channel {0} not available".format(n))
        # Function first: duty cycle belongs to PULSE and symmetry to RAMP, so a
        # request that sets both a function and its shape parameter must land the
        # function before the parameter that only makes sense under it.
        if function is not None:
            channel.function = function
        if body.frequency is not None:
            channel.frequency = body.frequency
        if body.amplitude is not None:
            channel.amplitude = body.amplitude
        if body.offset is not None:
            channel.offset = body.offset
        if body.phase is not None:
            channel.phase = body.phase
        if body.duty_cycle is not None:
            channel.pulse_duty_cycle = body.duty_cycle
        if body.symmetry is not None:
            channel.ramp_symmetry = body.symmetry

    return await mutate(session, apply)


@router.patch("/sessions/{session_id}/awg/channels/{n}/enable")
async def patch_enable(session_id: str, n: int, body: AwgEnablePatch, request: Request):
    session = require_owner(request, session_id)
    require_kind(session, "awg")

    def apply(awg):
        channel = awg.get_channel(n)
        if channel is None:
            raise InvalidParameterError("channel {0} not available".format(n))
        channel.enabled = body.enabled

    return await mutate(session, apply)


@router.post("/sessions/{session_id}/awg/outputs/off")
async def all_outputs_off(session_id: str, request: Request):
    """Kill every output in one action.

    A generator drives a real circuit, and turning outputs off one PATCH at a
    time races: the second request can be rejected, or arrive late, while the
    first output is already driving.
    """
    session = require_owner(request, session_id)
    require_kind(session, "awg")

    def apply(awg):
        awg.all_outputs_off()

    return await mutate(session, apply)
