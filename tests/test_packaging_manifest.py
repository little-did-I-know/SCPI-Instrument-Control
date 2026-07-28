"""MANIFEST.in must cover every frontend bundle the server serves.

`include-package-data = true` means setuptools takes package data from
MANIFEST.in. A static directory that exists on disk but has no rule here is
dropped from the wheel and the sdist without any error: `make webapp-build`
succeeds, `python -m build` succeeds, and the installed package serves a JSON
404 where the UI should be. That is exactly what happened to the admin bundle,
so this guard is written against directories on disk rather than a hardcoded
list -- a future sub-project adding another surface fails here instead of
shipping an empty one.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "MANIFEST.in"
SERVER = REPO_ROOT / "scpi_control" / "server"


def _manifest_rules():
    lines = []
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def _static_dirs():
    """Every static directory under the server package, as posix paths."""
    found = [SERVER / "static"] if (SERVER / "static").is_dir() else []
    found += sorted(path for path in SERVER.rglob("static") if path.is_dir() and path.parent != SERVER)
    return [path.relative_to(REPO_ROOT).as_posix() for path in found]


def test_every_server_static_dir_is_in_the_manifest():
    rules = _manifest_rules()
    missing = [directory for directory in _static_dirs() if "recursive-include {0} *".format(directory) not in rules]
    assert not missing, "MANIFEST.in has no recursive-include for {0}; the bundle would be absent from the wheel".format(missing)


def test_the_admin_bundle_is_named_explicitly():
    # The regression this file exists for. _static_dirs() only sees directories
    # that were actually built, so on a checkout with no bundles the test above
    # passes vacuously; this one does not.
    assert "recursive-include scpi_control/server/admin/static *" in _manifest_rules()
    assert "recursive-include scpi_control/server/static *" in _manifest_rules()
