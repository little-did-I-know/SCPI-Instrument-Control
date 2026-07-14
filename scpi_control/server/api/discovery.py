from typing import Optional

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from scpi_control.server import discovery

router = APIRouter(tags=["discovery"])


@router.get("/discover")
async def discover_instruments(request: Request, cidr: Optional[str] = None):
    manager = request.app.state.manager
    sessions = [s for s in manager.list() if s.address and s.state == "connected"]
    skip = frozenset(s.address for s in sessions)
    found = await run_in_threadpool(discovery.discover, cidr=cidr, port=discovery.SCPI_PORT, skip=skip)
    for entry in found:
        entry["connected"] = False
    connected = [
        {
            "address": s.address,
            "idn": s.idn,
            "manufacturer": s.idn.split(",")[0].strip() if s.idn else "",
            "model": s.model,
            "dialect": s.dialect,
            "kind": "scope",
            "connected": True,
            "session_id": s.id,
            "viewers": s.viewers,
        }
        for s in sessions
    ]
    results = connected + found
    results.sort(key=discovery._sort_key)
    return results
