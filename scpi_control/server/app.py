"""FastAPI app factory (requires the [web] extra; Python >= 3.9)."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from scpi_control.exceptions import InvalidParameterError, SiglentError, SiglentTimeoutError
from scpi_control.server.sessions import SessionError, SessionManager

STATIC_DIR = Path(__file__).parent / "static"


def _error_response(status: int, exc: BaseException) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": str(exc)})


def create_app(manager: Optional[SessionManager] = None) -> FastAPI:
    manager = manager if manager is not None else SessionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # close_all() joins worker threads, so keep it off the event loop.
        await run_in_threadpool(app.state.manager.close_all)

    app = FastAPI(title="SCPI Instrument Control Gateway", lifespan=lifespan)
    app.state.manager = manager

    from scpi_control.server.api import discovery as discovery_api
    from scpi_control.server.api import scope as scope_api
    from scpi_control.server.api import sessions as sessions_api
    from scpi_control.server.api import stream as stream_api

    app.include_router(sessions_api.router, prefix="/api")
    app.include_router(scope_api.router, prefix="/api")
    app.include_router(stream_api.router, prefix="/api")
    app.include_router(discovery_api.router, prefix="/api")

    @app.exception_handler(InvalidParameterError)
    async def _invalid_parameter(request: Request, exc: InvalidParameterError):
        return _error_response(400, exc)

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError):
        return _error_response(400, exc)

    @app.exception_handler(SessionError)
    async def _session_error(request: Request, exc: SessionError):
        return _error_response(409, exc)

    @app.exception_handler(SiglentTimeoutError)
    async def _timeout(request: Request, exc: SiglentTimeoutError):
        return _error_response(504, exc)

    @app.exception_handler(SiglentError)
    async def _siglent(request: Request, exc: SiglentError):
        return _error_response(500, exc)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        # Preserve headers Starlette attaches (e.g. Allow on a 405).
        return JSONResponse(status_code=exc.status_code, content={"error": "HTTPException", "detail": exc.detail}, headers=getattr(exc, "headers", None))

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")

    return app
