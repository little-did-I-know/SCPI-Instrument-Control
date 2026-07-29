"""Shared "serve a static bundle with an SPA fallback" logic.

Both the main app (server/app.py) and the admin app (server/admin/app.py)
register a catch-all GET route that serves a real static file when one
exists, and falls back to index.html otherwise so client-side routes
deep-link. Both need the same guard against path traversal (e.g.
"%2e%2e/secret.txt" escaping the static directory).

That guard is defined exactly once, here, specifically so the two call
sites cannot quietly diverge. tests/test_server_spa.py exercises it through
the main app's HTTP route; the admin app's route calls the same function, so
the same containment logic is proven for both. Keep it that way -- copying
this back into either app.py is how the next divergence goes unnoticed, on
whichever app has no auth in front of it.
"""

from pathlib import Path

from fastapi.responses import FileResponse


def resolve_spa_path(static_dir: Path, full_path: str) -> Path:
    """Return the file to serve at ``full_path`` under ``static_dir``.

    Returns the resolved candidate if it exists as a file and stays inside
    ``static_dir``; otherwise returns ``static_dir / "index.html"``. The
    caller is responsible for rejecting ``/api/*`` before calling this.
    Wrapping the result in a response is `spa_response`'s job below -- it is
    the only caller of this function.
    """
    static_root = static_dir.resolve()
    candidate = (static_dir / full_path).resolve()
    if full_path and candidate.is_file() and candidate.is_relative_to(static_root):
        return candidate
    return static_dir / "index.html"


def spa_response(static_dir: Path, full_path: str) -> FileResponse:
    """Serve the SPA file for ``full_path``, with index.html made uncacheable.

    The asset filenames are content-hashed, so they invalidate themselves.
    index.html is the file that *names* those hashes, and nothing invalidates
    it -- so a browser holding a cached copy keeps requesting a bundle the last
    build deleted, and the page silently stays at the previous version until
    somebody clears their cache by hand. That cost two debugging sessions.

    Keyed on the resolved path, not on full_path: an unknown path falls back to
    index.html, and that response needs the same treatment or a deep-linked
    client route caches a stale document under its own URL.
    """
    path = resolve_spa_path(static_dir, full_path)
    if path.name == "index.html":
        return FileResponse(str(path), headers={"Cache-Control": "no-store"})
    return FileResponse(str(path))
