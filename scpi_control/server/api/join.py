"""Redeem an invitation into a token. The one unauthenticated write route.

Everything else under /api is fail-closed (see AuthMiddleware). This route
exists so someone holding no credential can obtain one, which makes it the
most security-sensitive surface in the gateway. Two rules follow from that and
must not be relaxed:

1. Every failure returns one identical response. Distinguishing "wrong" from
   "expired" from "already used" would let an attacker probe for the existence
   and timing of invitations without ever guessing one.
2. Failed attempts are rate limited across all clients, not per IP. A per-IP
   budget is close to meaningless against someone on the same lab network who
   can pick source addresses.

There is deliberately no per-invitation attempt cap: a wrong code cannot be
attributed to any particular invitation, and charging every live invitation
for it would hand an attacker the power to invalidate everyone's access at
once.
"""

import logging
import time
from collections import deque
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Ten failures a minute against a six-digit code, over an invitation's
# ten-minute life, is about 100 guesses into a space of 1,000,000 -- roughly a
# 1-in-10,000 chance per invitation. Raising either number weakens that
# directly; do the arithmetic before you touch them.
#
# The limiter itself lives in app.state (see create_app), so the budget is
# per-process, not per-deployment. Rule 2 above -- "across all clients" --
# therefore holds only for the single-uvicorn-process server __main__.py
# starts. Adding a --workers N would silently hand an attacker N times this
# budget without changing either number here, so size the limit against the
# worker count if you ever add one.
FAILURE_LIMIT = 10
FAILURE_WINDOW_SECONDS = 60.0

# One message for every non-rate-limited failure. Keep it literal and shared:
# two call sites with "the same" wording that drift apart reintroduce the
# oracle this constant exists to prevent.
REJECTED = "That code or link is not valid, or it has expired. Ask for a new one."
THROTTLED = "Too many attempts. Wait a minute and try again."


class JoinRequest(BaseModel):
    code: Optional[str] = None
    invite: Optional[str] = None


class FailureLimiter:
    """Sliding window over recent *failures*, shared by all clients.

    Successes are not recorded: a successful join consumes its invitation, so
    it cannot be repeated, and counting successes would let a lab full of
    people arriving at 9am lock each other out.
    """

    def __init__(self, limit: int = FAILURE_LIMIT, window: float = FAILURE_WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window = window
        self._failures: deque = deque()

    def _expire(self, now: float) -> None:
        while self._failures and now - self._failures[0] > self.window:
            self._failures.popleft()

    def blocked(self) -> bool:
        now = time.monotonic()
        self._expire(now)
        return len(self._failures) >= self.limit

    def record_failure(self) -> None:
        self._failures.append(time.monotonic())


@router.post("/join")
async def join(body: JoinRequest, request: Request):
    """Exchange an invitation for a token. Requires no credential by design."""
    limiter = request.app.state.join_limiter
    if limiter.blocked():
        raise HTTPException(status_code=429, detail=THROTTLED)
    try:
        name = request.app.state.invitations.redeem(code=body.code, link=body.invite)
    except ValueError as exc:
        # A corrupt invitations.json makes redeem() raise, and the app-wide
        # ValueError handler would render it as a 400 carrying the store's
        # absolute path -- leaking the admin's username and directory layout
        # to an anonymous caller, and giving this route a third distinguishable
        # status. Rule 1 does not get an exception for our own bugs: answer
        # with the shared rejection and tell the operator server-side.
        # __main__.py refuses to start on a corrupt store, but the file can
        # still be damaged while the gateway runs, so this stays needed.
        logger.error("join rejected: invitation store unusable: %s", exc)
        name = None
    if name is None:
        limiter.record_failure()
        raise HTTPException(status_code=401, detail=REJECTED)
    return {"token": request.app.state.tokens.mint(name), "identity": name}
