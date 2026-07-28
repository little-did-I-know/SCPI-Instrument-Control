"""The host-only admin app.

This app has no authentication. Three independent things stand in for it, and
each one covers an attacker the others miss -- none is sufficient alone:

1. It is served on a listener bound to 127.0.0.1, so the operating system
   refuses every non-local *socket* before any of this code runs. Physical
   access to the gateway machine is the credential. This stops the LAN and
   nothing else: a browser on the gateway machine sails straight through it.
2. TrustedHostMiddleware, below, refuses every request whose Host header is
   not 127.0.0.1 or localhost. This is what stops DNS rebinding: a page open
   on the gateway machine can point its own hostname at 127.0.0.1 and become
   same-origin with this app despite never having a real loopback address of
   its own. The connection really does arrive on 127.0.0.1, so the bind waves
   it through -- but the request still carries the attacker's hostname, and
   this check refuses it.
3. _SameOriginOnlyMiddleware, below, refuses every request carrying an Origin
   header that is not this panel's own. This is what stops the *plain*
   cross-origin request, which needs no rebinding at all: a page on any site
   the admin visits can `fetch("http://127.0.0.1:8766/api/invitations", ...)`
   and satisfy both defences above -- the socket is genuinely local and the
   Host genuinely is 127.0.0.1:8766. Only the Origin gives it away. Without
   this, the sole thing refusing that request is the browser's own CORS
   preflight plus FastAPI's insistence on application/json, which is a real
   defence but an accidental one: it would evaporate the day someone accepts
   a form body, adds a mutating GET, or installs CORSMiddleware to quiet a
   dev proxy. Requests with no Origin at all (curl, same-origin fetches in
   browsers that omit it) are allowed -- an Origin is what a cross-origin
   request is obliged to carry.

Two rules follow from the bind, and breaking either one silently exposes the
whole surface to the LAN regardless of the checks above:

1. **Never mount this app under the main app**, and never share its router.
   The main app is reachable from the network; this one must not be.
2. **Never serve this app's static bundle from the main app's static
   directory.** The main app's SPA catch-all serves any real file it finds
   there, so a shared directory would hand the admin UI to every LAN browser.
   That is why the bundle lives in its own directory.
"""

from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from scpi_control.server.spa import resolve_spa_path

ADMIN_STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_ADMIN_PORT = 8766


def admin_origins(admin_port: int) -> List[str]:
    """The only Origins the panel may be called from -- itself, by either name.

    Both spellings appear in practice: the printed banner and the auto-opened
    browser use 127.0.0.1, while an SSH port-forward (documented in
    docs/gateway/admin-panel.md) reaches it as localhost. TrustedHostMiddleware
    allows exactly these two hostnames, so this list mirrors it.
    """
    return ["http://127.0.0.1:{0}".format(admin_port), "http://localhost:{0}".format(admin_port)]


class _SameOriginOnlyMiddleware:
    """Refuse any request whose Origin is not the panel's own.

    Pure ASGI rather than BaseHTTPMiddleware so the refusal is decided before
    any body is read, and so nothing downstream -- including the exception
    handlers, which sit inside the user middleware stack -- can turn it into
    something else. See the module docstring for the attacker this covers.
    """

    def __init__(self, app, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope, receive, send):
        # Only HTTP: this app serves no websockets, and a websocket to an
        # unknown path is refused by the router regardless.
        if scope["type"] == "http":
            origin = None
            for name, value in scope["headers"]:
                if name == b"origin":
                    origin = value.decode("latin-1")
                    break
            if origin is not None and origin not in self.allowed_origins:
                response = JSONResponse(status_code=403, content={"error": "HTTPException", "detail": "cross-origin request refused"})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_admin_app(token_store, invitation_store, base_url: Optional[str] = None, admin_port: int = DEFAULT_ADMIN_PORT) -> FastAPI:
    app = FastAPI(title="SCPI Gateway Admin", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.tokens = token_store
    app.state.invitations = invitation_store
    app.state.base_url = base_url

    from scpi_control.server.admin import api as admin_api

    app.include_router(admin_api.router, prefix="/api")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": "HTTPException", "detail": exc.detail}, headers=getattr(exc, "headers", None))

    if ADMIN_STATIC_DIR.is_dir():

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="unknown path /{0}".format(full_path))
            return FileResponse(str(resolve_spa_path(ADMIN_STATIC_DIR, full_path)))

    # The second and third independent defences described in the module
    # docstring -- see there for why the loopback bind alone is not enough.
    # Added last so they wrap everything above, including the SPA route.
    app.add_middleware(_SameOriginOnlyMiddleware, allowed_origins=admin_origins(admin_port))
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    return app
