"""Ownership rules for live instrument sessions.

Reads are open to any authenticated identity; writes belong to the session's
owner. NotOwnerError subclasses SessionError so the app's existing handler maps
it to 409 -- the code already used for session-state conflicts.

Beyond the write boundary, this module also covers the escape hatch for a
session whose owner walked away: claim() lets another identity take over an
abandoned session, and the /owner route (api/sessions.py) lets the current
owner hand off explicitly.
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
        ("POST", "/sessions/{session_id}/owner"),
    }
)

# Note: POST /sessions/{session_id}/claim is deliberately NOT in this set.
# It is gated on ownership too, but a non-owner's request is its normal,
# successful path (claiming) rather than something require_owner rejects --
# it only 409s when the current owner is still active, a different kind of
# conflict than "you are not the owner". tests/test_server_ownership.py's
# bidirectional WRITE_ROUTES scan excludes it explicitly for that reason.


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


def abandon_after(request: Request) -> float:
    """Seconds of owner inactivity before another identity may claim a session."""
    return request.app.state.abandon_after


def claim(session: InstrumentSession, identity: str, threshold: float) -> bool:
    """Attempt to claim ``session`` for ``identity``. Returns True on success.

    An unowned session, or one already owned by ``identity``, claims
    immediately -- note this ignores owner_last_active entirely for an
    unowned session (owner == ""), since require_owner() touches that timer
    even when there is no owner to attribute the activity to.

    Otherwise the claim is refused while the owner is actively watching the
    live stream (owner_watching()), regardless of the idle threshold, and
    also refused if the owner has been active more recently than
    ``threshold`` seconds ago. owner_last_active is time.monotonic()-based;
    ``threshold`` must be compared against a monotonic delta, never wall time.

    On success, session.owner is now ``identity``. On failure the caller is
    expected to report the current owner and idle time itself (via
    NotOwnerError) rather than rely on a return value here.
    """
    if session.owner and session.owner != identity:
        if session.owner_watching():
            return False
        idle = time.monotonic() - session.owner_last_active
        if idle < threshold:
            return False
    session.owner = identity
    session.touch()
    return True
