"""FastAPI app factory (requires the [web] extra; Python >= 3.9)."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from scpi_control.exceptions import InvalidParameterError, SiglentError, SiglentTimeoutError
from scpi_control.server.api.join import FailureLimiter
from scpi_control.server.auth import AuthMiddleware, TokenStore
from scpi_control.server.invitations import InvitationStore
from scpi_control.server.adapters import DEFAULT_STREAM_MAX_FPS, DENSE_MAX_POINTS
from scpi_control.server.revocation import StreamRegistry
from scpi_control.server.sessions import SessionError, SessionManager
from scpi_control.server.spa import spa_response

STATIC_DIR = Path(__file__).parent / "static"


def _error_response(status: int, exc: BaseException) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": str(exc)})


def create_app(
    manager: Optional[SessionManager] = None,
    references_dir: Optional[str] = None,
    token_store: Optional[TokenStore] = None,
    invitation_store: Optional[InvitationStore] = None,
    stream_revocation_interval: float = 5.0,
    abandon_after: float = 300.0,
    allowed_ports: Optional[frozenset] = None,
    max_sessions: Optional[int] = None,
    stream_max_points: Optional[int] = None,
    stream_max_fps: Optional[float] = None,
) -> FastAPI:
    # allowed_ports and max_sessions only ever seed a manager create_app builds
    # itself: an explicitly-passed manager already carries its own policy (or
    # the class defaults). Silently overriding it here would surprise a caller
    # (e.g. a test) that constructed SessionManager(...) on purpose -- but
    # silently *dropping* a policy argument when both are given is just as
    # surprising to a caller who assumed they compose, and could leave the
    # gateway with no port policy or session cap at all. Refuse the ambiguous
    # combination instead of guessing.
    if manager is not None and (allowed_ports is not None or max_sessions is not None or stream_max_points is not None or stream_max_fps is not None):
        raise ValueError(
            "create_app() received both an explicit manager and allowed_ports/max_sessions/stream_max_points/stream_max_fps; configure those on the manager (SessionManager(...)) instead."
        )
    manager = (
        manager
        if manager is not None
        else SessionManager(
            allowed_ports=allowed_ports,
            max_sessions=max_sessions if max_sessions is not None else 8,
            stream_max_points=stream_max_points if stream_max_points is not None else DENSE_MAX_POINTS,
            stream_max_fps=stream_max_fps if stream_max_fps is not None else DEFAULT_STREAM_MAX_FPS,
        )
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # close_all() joins worker threads, so keep it off the event loop.
        await run_in_threadpool(app.state.manager.close_all)

    # docs_url/redoc_url off and openapi_url moved under /api/ so the schema and
    # HTML doc UIs sit behind AuthMiddleware like the rest of the instrument
    # surface, instead of being served to anyone who reaches the port.
    app = FastAPI(title="SCPI Instrument Control Gateway", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")
    app.state.manager = manager
    # A malformed token store must fail loudly (TokenStore.__init__ raises
    # ValueError) rather than be caught here and silently degrade to an empty
    # store, which would open the gateway to anonymous access.
    app.state.tokens = token_store if token_store is not None else TokenStore()
    # Like the token store, a malformed invitation file must fail loudly
    # rather than degrade to "no invitations" and leave the admin wondering
    # why a link they just sent does nothing.
    app.state.invitations = invitation_store if invitation_store is not None else InvitationStore()
    # One limiter per app, so the window is shared across all clients.
    app.state.join_limiter = FailureLimiter()
    # Reference store is created lazily on first use: ReferenceWaveform.__init__
    # mkdirs its storage directory, and most requests never need it.
    app.state.references_dir = references_dir
    app.state.references = None
    # Seconds of owner inactivity before another identity may claim a session
    # (scpi_control.server.ownership.claim); mutable at runtime so tests can
    # drive it to 0 instead of sleeping for a real timeout.
    app.state.abandon_after = abandon_after
    # Live streams grouped by identity, so revoking can signal them. Shared by
    # the admin app, which is why both listeners run in one process.
    app.state.stream_registry = StreamRegistry()
    # How often a stream re-checks that its identity still exists. Injectable
    # because a test that waits five real seconds is a test nobody runs, and
    # because the registry test has to set it high enough to prove the backstop
    # could not have been what tore the stream down.
    app.state.stream_revocation_interval = stream_revocation_interval

    from scpi_control.server.api import awg as awg_api
    from scpi_control.server.api import commands as commands_api
    from scpi_control.server.api import discovery as discovery_api
    from scpi_control.server.api import join as join_api
    from scpi_control.server.api import psu as psu_api
    from scpi_control.server.api import scope as scope_api
    from scpi_control.server.api import sessions as sessions_api
    from scpi_control.server.api import stream as stream_api

    app.include_router(sessions_api.router, prefix="/api")
    app.include_router(scope_api.router, prefix="/api")
    app.include_router(psu_api.router, prefix="/api")
    app.include_router(awg_api.router, prefix="/api")
    app.include_router(commands_api.router, prefix="/api")
    app.include_router(stream_api.router, prefix="/api")
    app.include_router(discovery_api.router, prefix="/api")
    app.include_router(join_api.router, prefix="/api")

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/whoami")
    async def whoami(request: Request):
        return {"identity": getattr(request.state, "identity", None)}

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
        # Catch-all GET, registered LAST so every API route wins. Serves a real
        # file when one exists (JS/CSS/assets), otherwise index.html so client
        # routes deep-link. /api/* keeps the JSON {error, detail} 404 shape.
        # The traversal-safe lookup itself lives in server/spa.py, shared with
        # the admin app -- see that module's docstring for why.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="unknown path /{0}".format(full_path))
            return spa_response(STATIC_DIR, full_path)

    # Added last so it wraps everything above, including the SPA catch-all: pure
    # ASGI middleware (not BaseHTTPMiddleware) so it also guards WebSocket scopes.
    app.add_middleware(AuthMiddleware, store=app.state.tokens)

    return app
