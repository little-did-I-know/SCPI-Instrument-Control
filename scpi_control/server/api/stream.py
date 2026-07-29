# scpi_control/server/api/stream.py
import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from scpi_control.server.auth import WS_ACCEPT_SUBPROTOCOL
from scpi_control.server.revocation import identity_is_live

router = APIRouter(tags=["stream"])

# Cap the per-connection outbox so a slow/paused client cannot make the event
# loop buffer waveform frames without bound. 256 frames ~= a minute at 4 Hz.
OUTBOX_MAXSIZE = 256

# Distinct from 4404 (unknown session) and 4410 (session ended): the socket was
# accepted but this session's adapter could not produce its opening frame.
CLOSE_INITIAL_FRAME_FAILED = 4500

# The identity that opened this socket was revoked. Distinct from 4410 (the
# session ended) because nothing happened to the session -- the viewer lost
# their credential.
CLOSE_IDENTITY_REVOKED = 4403


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


async def _watch_for_revocation(token_store, identity: str, revoked: "asyncio.Event", interval: float) -> None:
    """Set ``revoked`` once ``identity`` stops existing.

    The backstop for a revocation made in another process -- `scpi-web token
    revoke` -- where nothing in this process receives an event. Sets the same
    event the registry does, so there is one teardown path rather than two that
    have to agree. A store read can raise (TokenStore._load() surfaces a
    corrupt file or a transient OSError as ValueError) -- that costs this tick,
    not the whole backstop, so we retry on the next one instead of letting the
    task die silently and leaving a revoked identity streaming forever.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            live = identity_is_live(token_store, identity)
        except Exception:
            continue  # an unreadable store is transient; re-check next tick
        if not live:
            revoked.set()
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
    revoked = asyncio.Event()
    unregister_stream = None
    watcher = None
    receiver = None
    sender = None
    revocation = None
    try:
        # Inside the try, not above it. mark_owner_watching() has already run,
        # so anything that raises between there and the finally leaves the
        # owner marked as watching forever and the session permanently
        # unclaimable -- the exact bug this whole sub-project exists to kill,
        # arriving through a different door. Only create_app mounts this
        # router, so today both lookups are guaranteed to be there; an app
        # assembled some other way (an embedder, a future second mount) would
        # raise AttributeError here, and that must cost the connection, not the
        # bench. The names are bound to None above so the finally can tell
        # "never registered" from "registered", and skip what was never set up.
        unregister_stream = websocket.app.state.stream_registry.add(identity, revoked)
        watcher = asyncio.ensure_future(_watch_for_revocation(websocket.app.state.tokens, identity, revoked, websocket.app.state.stream_revocation_interval))
        # The initial frame must match whatever shape this session's adapter
        # publishes on every subsequent tick, so the adapter -- not a `kind`
        # branch here -- decides it. A kind that forgets the hook raises
        # NotImplementedError and gets the loud path below.
        try:
            initial = await asyncio.wrap_future(session.submit(session.adapter.initial_frame))
        except Exception as exc:
            # NOT a bare `except: pass`. Swallowing this used to leave the
            # socket open but silent forever: no initial frame, and polling
            # never starts either because _poll_tick() requires a subscriber
            # that has seen a first message. A client that gets nothing cannot
            # tell a broken adapter from an idle instrument, so say so and
            # close with a code that names the failure.
            with contextlib.suppress(Exception):
                await websocket.send_json({"type": "error", "detail": "initial frame failed: {0}".format(exc)})
                await websocket.close(code=CLOSE_INITIAL_FRAME_FAILED)
            return
        await websocket.send_json(initial)
        # Run the receiver (disconnect detection) and sender concurrently; whichever
        # finishes first tears the connection down.
        receiver = asyncio.ensure_future(_receive_until_disconnect(websocket))
        sender = asyncio.ensure_future(_send_from_outbox(websocket, outbox))
        revocation = asyncio.ensure_future(revoked.wait())
        await asyncio.wait({receiver, sender, revocation}, return_when=asyncio.FIRST_COMPLETED)
        if revoked.is_set():
            # Say why. A client that just sees the socket vanish cannot tell a
            # revocation from a network blip, and this one should send the user
            # back to the sign-in screen rather than retrying forever.
            with contextlib.suppress(Exception):
                await websocket.close(code=CLOSE_IDENTITY_REVOKED)
    except WebSocketDisconnect:
        pass
    except Exception:
        # Any failure on the send/receive path tears down quietly (no ASGI noise).
        pass
    finally:
        unmark_owner_watching()
        unsubscribe()
        if unregister_stream is not None:
            unregister_stream()
        for task in (receiver, sender, watcher, revocation):
            if task is not None:
                task.cancel()
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await task
