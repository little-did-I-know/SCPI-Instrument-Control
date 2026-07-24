"""Ownership rules for live instrument sessions.

Reads are open to any authenticated identity; writes belong to the session's
owner. NotOwnerError subclasses SessionError so the app's existing handler maps
it to 409 -- the code already used for session-state conflicts.

Claim/handoff for abandoned sessions is a later feature; this module only
enforces the boundary between the current owner and everyone else.
"""

import time

from fastapi import Request

from scpi_control.server.api.sessions import require_session
from scpi_control.server.sessions import InstrumentSession, SessionError

# (method, router-relative path) pairs -- no /api prefix -- that mutate
# instrument or session state and are therefore gated on ownership rather
# than plain authentication. Method-qualified because several paths here are
# also GET routes that must stay open to any authenticated identity (e.g.
# GET /sessions/{session_id} reads, DELETE .../{session_id} writes).
#
# Kept here as the documented read/write split, and made load-bearing by
# tests/test_server_ownership.py, which parametrizes over this set to assert
# each entry 409s for a non-owner, and separately walks the app's live route
# table to assert every (method, path) NOT in this set stays open to a
# non-owner -- so a route added to one side without the other fails a test.
WRITE_ROUTES = frozenset(
    {
        ("DELETE", "/sessions/{session_id}"),
        ("PATCH", "/sessions/{session_id}/scope/channels/{channel}"),
        ("PATCH", "/sessions/{session_id}/scope/timebase"),
        ("PATCH", "/sessions/{session_id}/scope/trigger"),
        ("POST", "/sessions/{session_id}/scope/command"),
        ("PUT", "/sessions/{session_id}/scope/measurements"),
        ("PATCH", "/sessions/{session_id}/scope/math/{n}"),
        ("PATCH", "/sessions/{session_id}/scope/spectrum"),
        ("PATCH", "/sessions/{session_id}/scope/filters/{n}"),
        ("POST", "/sessions/{session_id}/scope/references"),
        ("DELETE", "/sessions/{session_id}/scope/references/{name}"),
        ("PUT", "/sessions/{session_id}/scope/reference"),
        ("POST", "/sessions/{session_id}/scope/log/start"),
        ("POST", "/sessions/{session_id}/scope/log/stop"),
        ("POST", "/sessions/{session_id}/scope/{op}"),
    }
)


class NotOwnerError(SessionError):
    def __init__(self, owner: str, idle_seconds: float) -> None:
        super().__init__("session is owned by {0!r} (idle {1:.0f}s); claim it or ask for a handoff".format(owner, idle_seconds))
        self.owner = owner
        self.since = idle_seconds


def require_owner(request: Request, session_id: str) -> InstrumentSession:
    session = require_session(request, session_id)
    identity = getattr(request.state, "identity", "")
    if session.owner and session.owner != identity:
        raise NotOwnerError(session.owner, time.monotonic() - session.owner_last_active)
    session.touch()
    return session
