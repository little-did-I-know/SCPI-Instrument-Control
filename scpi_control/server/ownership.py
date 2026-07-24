"""Ownership rules for live instrument sessions.

Reads are open to any authenticated identity; writes belong to the session's
owner. NotOwnerError subclasses SessionError so the app's existing handler maps
it to 409 -- the code already used for session-state conflicts.

Claim/handoff for abandoned sessions is a later feature; this module only
enforces the boundary between the current owner and everyone else.
"""

import time

from scpi_control.server.api.sessions import require_session
from scpi_control.server.sessions import InstrumentSession, SessionError

# Router-relative paths (no /api prefix) that mutate instrument or session
# state and are therefore gated on ownership rather than plain authentication.
# Kept here as the single documented source of truth for the read/write split.
WRITE_ROUTES = frozenset(
    {
        "/sessions/{session_id}",
        "/sessions/{session_id}/scope/channels/{channel}",
        "/sessions/{session_id}/scope/timebase",
        "/sessions/{session_id}/scope/trigger",
        "/sessions/{session_id}/scope/command",
        "/sessions/{session_id}/scope/measurements",
        "/sessions/{session_id}/scope/math/{n}",
        "/sessions/{session_id}/scope/spectrum",
        "/sessions/{session_id}/scope/filters/{n}",
        "/sessions/{session_id}/scope/references",
        "/sessions/{session_id}/scope/references/{name}",
        "/sessions/{session_id}/scope/reference",
        "/sessions/{session_id}/scope/log/start",
        "/sessions/{session_id}/scope/log/stop",
        "/sessions/{session_id}/scope/{op}",
    }
)


class NotOwnerError(SessionError):
    def __init__(self, owner: str, idle_seconds: float) -> None:
        super().__init__("session is owned by {0!r} (idle {1:.0f}s); claim it or ask for a handoff".format(owner, idle_seconds))
        self.owner = owner
        self.since = idle_seconds


def require_owner(request, session_id: str) -> InstrumentSession:
    session = require_session(request, session_id)
    identity = getattr(request.state, "identity", "")
    if session.owner and session.owner != identity:
        raise NotOwnerError(session.owner, time.monotonic() - session.owner_last_active)
    session.touch()
    return session
