"""FastAPI app factory (requires the [web] extra; Python >= 3.9)."""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from scpi_control.exceptions import InvalidParameterError, SiglentError, SiglentTimeoutError
from scpi_control.server.sessions import SessionError, SessionManager

STATIC_DIR = Path(__file__).parent / "static"


def _error_response(status: int, exc: BaseException) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": str(exc)})


def create_app(manager: Optional[SessionManager] = None) -> FastAPI:
    app = FastAPI(title="SCPI Instrument Control Gateway")
    app.state.manager = manager if manager is not None else SessionManager()

    from scpi_control.server.api import scope as scope_api
    from scpi_control.server.api import sessions as sessions_api
    from scpi_control.server.api import stream as stream_api

    app.include_router(sessions_api.router, prefix="/api")
    app.include_router(scope_api.router, prefix="/api")
    app.include_router(stream_api.router, prefix="/api")

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

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": "HTTPException", "detail": exc.detail})

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")

    return app
