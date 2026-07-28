"""The host-only admin app.

This app has no authentication. Two independent things stand in for it, and
they defend against two different attackers -- neither one is sufficient
alone:

1. It is served on a listener bound to 127.0.0.1, so the operating system
   refuses every non-local *socket* before any of this code runs. Physical
   access to the gateway machine is the credential.
2. TrustedHostMiddleware, below, refuses every request whose Host header is
   not 127.0.0.1 or localhost. This is what stops a *browser*: a page open
   on the gateway machine can rebind its own hostname to 127.0.0.1 (DNS
   rebinding) and become same-origin with this app despite never having a
   real loopback address of its own. The loopback bind does nothing against
   that -- the connection really does arrive on 127.0.0.1 -- so without this
   middleware that page could mint or revoke access with no credential at
   all. CORS preflight does not help either: rebinding defeats it by
   construction.

Two rules follow from the bind, and breaking either one silently exposes the
whole surface to the LAN regardless of the Host check above:

1. **Never mount this app under the main app**, and never share its router.
   The main app is reachable from the network; this one must not be.
2. **Never serve this app's static bundle from the main app's static
   directory.** The main app's SPA catch-all serves any real file it finds
   there, so a shared directory would hand the admin UI to every LAN browser.
   That is why the bundle lives in its own directory.
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from scpi_control.server.spa import resolve_spa_path

ADMIN_STATIC_DIR = Path(__file__).parent / "static"


def create_admin_app(token_store, invitation_store, base_url: Optional[str] = None) -> FastAPI:
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

    # The second, independent defence described in the module docstring --
    # see there for why the loopback bind alone is not enough. Added last so
    # it wraps everything above, including the SPA route.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    return app
