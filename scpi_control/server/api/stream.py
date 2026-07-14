# scpi_control/server/api/stream.py
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from scpi_control.server.sessions import read_state

router = APIRouter(tags=["stream"])


@router.websocket("/sessions/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: str):
    session = websocket.app.state.manager.get(session_id)
    if session is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()

    loop = asyncio.get_running_loop()
    outbox: "asyncio.Queue" = asyncio.Queue()

    def on_message(message):
        loop.call_soon_threadsafe(outbox.put_nowait, message)

    unsubscribe = session.subscribe(on_message)
    try:
        initial = await asyncio.wrap_future(session.submit(read_state))
        await websocket.send_json({"type": "state", "state": initial})
        while True:
            message = await outbox.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe()
