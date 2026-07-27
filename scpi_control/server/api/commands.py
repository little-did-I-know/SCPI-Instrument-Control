# scpi_control/server/api/commands.py
"""The raw SCPI console, for any instrument kind.

A command is not a scope concept: `write` and `query` are on every driver
(Oscilloscope and PowerSupply both, and whatever comes next). This route used to
exist only as /sessions/{id}/scope/command, which meant that after per-kind
guards landed, a power supply session could not use the console at all.

/scope/command still exists and still refuses a non-scope session. It delegates
here so there is exactly one implementation of what a command does.
"""

from typing import Any, Dict

from fastapi import APIRouter, Request

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.api.sessions import run_job
from scpi_control.server.ownership import require_owner
from scpi_control.server.schemas import CommandIn

router = APIRouter(tags=["commands"])


async def send_command_for(session, raw_command: str) -> Dict[str, Any]:
    """Send one SCPI command to a session's instrument.

    A command ending in '?' is a query and returns the instrument's answer;
    anything else is a write and returns None -- never a fabricated response.
    """
    command = raw_command.strip()
    if not command:
        raise InvalidParameterError("empty command")

    def run(instrument):
        if command.endswith("?"):
            return instrument.query(command)
        instrument.write(command)
        return None

    response = await run_job(session, run)
    return {"command": command, "response": response}


@router.post("/sessions/{session_id}/command")
async def send_command(session_id: str, body: CommandIn, request: Request):
    session = require_owner(request, session_id)
    return await send_command_for(session, body.command)
