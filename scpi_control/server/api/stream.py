# scpi_control/server/api/stream.py
import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from scpi_control.server.auth import WS_ACCEPT_SUBPROTOCOL
from scpi_control.server.sessions import read_state

router = APIRouter(tags=["stream"])

# Cap the per-connection outbox so a slow/paused client cannot make the event
# loop buffer waveform frames without bound. 256 frames ~= a minute at 4 Hz.
OUTBOX_MAXSIZE = 256


def _enqueue(outbox: "asyncio.Queue", message) -> None:
    """Put ``message`` on ``outbox``, dropping the oldest waveform under backpressure.

    Runs on the event-loop thread (scheduled via ``call_soon_threadsafe``), so no
    other producer touches the queue concurrently and this stays race-free. When the
    queue is full we evict the oldest ``waveform`` frame to make room; ``state`` /
    ``error`` / ``closed`` control frames are never dropped. If a single scan finds no
    waveform to evict, we drop the incoming frame instead of a control frame.
    """
    if not outbox.full():
        outbox.put_nowait(message)
        return
    dropped_waveform = False
    for _ in range(outbox.qsize()):
        try:
            item = outbox.get_nowait()
        except asyncio.QueueEmpty:
            break
        if not dropped_waveform and isinstance(item, dict) and item.get("type") == "waveform":
            dropped_waveform = True
            continue  # evict this oldest waveform frame
        outbox.put_nowait(item)  # rotate everything else back in order
    if dropped_waveform:
        outbox.put_nowait(message)
    # else: only control frames present -> drop the incoming frame, keep controls


async def _receive_until_disconnect(websocket: WebSocket) -> None:
    """Park on the receive side so a client disconnect is noticed even when idle."""
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
    except Exception:
        return


async def _send_from_outbox(websocket: WebSocket, outbox: "asyncio.Queue") -> None:
    """Forward queued messages until the session closes or the socket errors."""
    try:
        while True:
            message = await outbox.get()
            await websocket.send_json(message)
            if isinstance(message, dict) and message.get("type") == "closed":
                await websocket.close(code=4410)
                return
    except Exception:
        return


@router.websocket("/sessions/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: str):
    session = websocket.app.state.manager.get(session_id)
    if session is None:
        await websocket.close(code=4404)
        return
    # Echo the accept subprotocol back only when the client actually offered
    # it: echoing an unoffered subprotocol is invalid per RFC 6455 and browsers
    # fail the handshake either way -- offered-and-unechoed, or echoed-unoffered.
    subprotocol = WS_ACCEPT_SUBPROTOCOL if WS_ACCEPT_SUBPROTOCOL in websocket.scope.get("subprotocols", []) else None
    await websocket.accept(subprotocol=subprotocol)

    loop = asyncio.get_running_loop()
    outbox: "asyncio.Queue" = asyncio.Queue(maxsize=OUTBOX_MAXSIZE)

    def on_message(message):
        loop.call_soon_threadsafe(_enqueue, outbox, message)

    unsubscribe = session.subscribe(on_message)
    # A live stream is one long-lived connection, so require_session's
    # per-request touch() never fires here -- an owner who is watching a
    # capture would otherwise look idle to the claim rule. Mark the owner as
    # watching for the lifetime of the connection instead (no-op if this
    # identity isn't the owner); unmark unconditionally in finally so an
    # abnormal disconnect releases it just like a clean close does.
    identity = getattr(websocket.state, "identity", "")
    unmark_owner_watching = session.mark_owner_watching(identity)
    receiver = None
    sender = None
    try:
        initial = await asyncio.wrap_future(session.submit(read_state))
        await websocket.send_json({"type": "state", "state": initial})
        # Run the receiver (disconnect detection) and sender concurrently; whichever
        # finishes first tears the connection down.
        receiver = asyncio.ensure_future(_receive_until_disconnect(websocket))
        sender = asyncio.ensure_future(_send_from_outbox(websocket, outbox))
        await asyncio.wait({receiver, sender}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    except Exception:
        # Any failure on the send/receive path tears down quietly (no ASGI noise).
        pass
    finally:
        unmark_owner_watching()
        unsubscribe()
        for task in (receiver, sender):
            if task is not None:
                task.cancel()
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await task
