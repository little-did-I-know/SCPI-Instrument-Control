"""What revocation means, in one place.

Two things tear a live stream down: the admin panel walking a registry, and
each stream's own periodic liveness check. They must not disagree about what a
revoked identity is or what happens to one, so both converge on the same
asyncio.Event per connection -- there is exactly one exit path, and it is the
one the stream's existing `finally` already cleans up after.

The CLI is why the second trigger exists at all: `scpi-web token revoke` runs
in a different process, so nothing in the serving process receives an event.
The liveness check notices because TokenStore reloads when the file changes.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set


class StreamRegistry:
    """Live streams, grouped by the identity that opened them.

    Holds events rather than sockets on purpose. Closing a WebSocket from
    another task while its send loop is mid-write is a race whose failure mode
    is a traceback in a lab log; setting an event the owning task already waits
    on keeps teardown on the task that owns the socket.
    """

    def __init__(self) -> None:
        self._events: Dict[str, Set[asyncio.Event]] = {}

    def add(self, identity: str, event: asyncio.Event) -> Callable[[], None]:
        """Register ``event``; returns an idempotent unregister callable.

        Mirrors InstrumentSession.mark_owner_watching, which hands back an
        unmark callable for the same reason: the caller's `finally` should not
        have to know how the bookkeeping works.
        """
        self._events.setdefault(identity, set()).add(event)

        def unregister() -> None:
            events = self._events.get(identity)
            if events is None:
                return
            events.discard(event)
            if not events:
                self._events.pop(identity, None)

        return unregister

    def revoke(self, identity: str) -> int:
        """Signal every stream this identity holds. Returns how many."""
        events = self._events.get(identity, set())
        for event in events:
            event.set()
        return len(events)

    def count(self, identity: str) -> int:
        return len(self._events.get(identity, set()))


def identity_is_live(token_store: Any, identity: str) -> bool:
    """True if ``identity`` still exists in the store.

    names() reloads, so this sees a revocation made by any process. An empty
    identity is never live: it would mean a stream that never passed through
    AuthMiddleware, which cannot happen today and must not be trusted if it
    ever does.
    """
    if not identity:
        return False
    return identity in token_store.names()


def revoke_identity(token_store: Any, manager: Any, registry: StreamRegistry, name: str) -> Optional[Dict[str, int]]:
    """Revoke ``name`` completely: tokens, live streams, owned sessions.

    Returns what it did, so the caller can report it rather than guess, or
    None if there was no such identity. The order matters: tokens go first, so
    that a stream whose liveness check fires between the two steps reaches the
    same conclusion this function is about to enforce.
    """
    devices = {row["name"]: row["devices"] for row in token_store.summary()}.get(name)
    if devices is None:
        return None
    token_store.revoke(name)
    streams = registry.revoke(name)
    sessions = 0
    for session in manager.list():
        if session.owner == name:
            # Leaving an owner that no longer exists creates a state the rest
            # of the API reports as a normal owner, and the session stays
            # unclaimable until the idle threshold passes.
            session.owner = ""
            sessions += 1
    return {"devices": devices, "streams": streams, "sessions": sessions}
