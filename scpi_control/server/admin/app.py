"""The host-only admin app.

This app has no authentication, and that is the design rather than an
oversight. It is served on a listener bound to 127.0.0.1, so the operating
system refuses every non-local connection before any of this code runs.
Physical access to the gateway machine is the credential.

Two rules follow, and breaking either one silently exposes the whole surface
to the LAN:

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
        index_file = ADMIN_STATIC_DIR / "index.html"
        static_root = ADMIN_STATIC_DIR.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="unknown path /{0}".format(full_path))
            candidate = (ADMIN_STATIC_DIR / full_path).resolve()
            # Same traversal guard as the main app: only serve the resolved
            # candidate if it is still inside the static root.
            if full_path and candidate.is_file() and candidate.is_relative_to(static_root):
                return FileResponse(str(candidate))
            return FileResponse(str(index_file))

    return app
