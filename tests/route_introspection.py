"""Version-robust enumeration of the gateway's ``/api`` route surface.

FastAPI/Starlette changed how ``include_router`` structures the route table.
Starlette <= 0.46 flattens each included router's sub-routes directly into
``app.routes``; Starlette >= 1.0 instead wraps every include in an
``_IncludedRouter`` whose ``original_router`` holds the sub-routes with
router-relative paths. Walking only the top level of ``app.routes`` and
filtering on ``isinstance(route, APIRoute)`` therefore finds almost nothing on
the newer Starlette -- which is exactly what broke CI (fresh ``fastapi``,
Starlette 1.x) while a locally-pinned Starlette 0.46 passed.

Enumerate through surfaces that are stable across both layouts instead: the
OpenAPI schema for HTTP routes (it yields full paths and methods regardless of
how the routers are nested), and a recursive walk for the WebSocket routes the
schema omits.
"""

from fastapi.routing import APIWebSocketRoute

from scpi_control.server.auth import EXEMPT_PATHS


def iter_http_routes(app):
    """Yield ``(METHOD, full_path)`` for each ``/api/`` HTTP route, minus exempt.

    Sourced from ``app.openapi()`` so it reports full paths independent of
    router nesting. ``HEAD``/``OPTIONS`` (which OpenAPI does not list anyway) and
    the exempt paths (e.g. ``/api/health``) are excluded, matching what the auth
    guard actually protects.
    """
    for path, operations in app.openapi().get("paths", {}).items():
        if not path.startswith("/api/") or path in EXEMPT_PATHS:
            continue
        for method in operations:
            upper = method.upper()
            if upper in ("HEAD", "OPTIONS"):
                continue
            yield upper, path


def _walk(routes):
    """Yield every leaf route, descending includes on either Starlette layout."""
    for route in routes:
        included = getattr(route, "original_router", None)  # Starlette >= 1.0 _IncludedRouter
        subroutes = getattr(route, "routes", None)  # Mount / sub-router
        if included is not None:
            yield from _walk(included.routes)
        elif subroutes:
            yield from _walk(subroutes)
        else:
            yield route


def iter_ws_routes(app):
    """Yield the full path of every ``/api/`` WebSocket route.

    OpenAPI omits WebSocket endpoints, so these come from a recursive walk. On
    the newer Starlette the leaf path is router-relative; this app mounts every
    router under ``/api``, so a relative leaf is prefixed accordingly.
    """
    for route in _walk(app.routes):
        if not isinstance(route, APIWebSocketRoute):
            continue
        path = route.path if route.path.startswith("/api/") else "/api" + route.path
        if path.startswith("/api/"):
            yield path
