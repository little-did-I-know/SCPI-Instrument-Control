"""The two hand-maintained version strings must agree.

`pyproject.toml`'s `[project] version` and `scpi_control.__version__` are bumped by
hand in the release commit (see the `chore(release):` commits). Nothing checked that
they matched, so a missed edit would ship a package whose `__version__` lies: the
wheel installs as one version while the module reports another, which quietly
corrupts anything that reports the running version -- bug reports, provenance
stamps written into saved waveforms, and report metadata.

Deliberately parses `pyproject.toml` rather than reading installed distribution
metadata: `importlib.metadata` reflects whenever the package was last installed, so
in an editable checkout it happily returns a stale version and the check would pass
against the wrong source of truth.

No `hasattr`/`try` guards here on purpose. If this file cannot find the version it
must FAIL, not skip -- a guard that turns "I could not check" into a green run is
exactly the blindness this suite has been purging.
"""

import re
from pathlib import Path

import scpi_control

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _pyproject_version():
    """Return `[project] version` from pyproject.toml.

    Hand-parsed instead of using tomllib: the Python floor is 3.9, tomllib only
    landed in 3.11, and tomli is not a dependency. The match is scoped to the
    `[project]` table so a `version =` in some other tool's section cannot be
    picked up by mistake.
    """
    assert PYPROJECT.is_file(), "pyproject.toml not found at {0}".format(PYPROJECT)
    text = PYPROJECT.read_text(encoding="utf-8")
    table = re.search(r"^\[project\]\s*$(.*?)^\[", text, re.S | re.M)
    assert table, "could not locate the [project] table in pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', table.group(1), re.M)
    assert match, "could not locate `version` inside the [project] table"
    return match.group(1)


def test_pyproject_and_module_version_agree():
    pyproject_version = _pyproject_version()
    assert pyproject_version == scpi_control.__version__, "pyproject.toml says {0!r} but scpi_control.__version__ says {1!r} -- both must be bumped in the release commit".format(pyproject_version, scpi_control.__version__)


def test_version_is_well_formed():
    """A malformed version breaks the sdist/wheel filenames and PyPI ordering."""
    version = scpi_control.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+([.\-+]?\w+)*", version), "{0!r} is not a PEP 440-style version".format(version)
