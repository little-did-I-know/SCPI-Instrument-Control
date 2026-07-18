"""Smoke-tests for the examples/ tree.

Guards three things: (1) no known-stale tokens survive (verifies the fixes and
blocks their reintroduction), (2) every .py example at least compiles, (3) the
notebook is valid JSON. Task 2 adds a fourth guard: executing the no-hardware
examples as subprocesses.

Limitation: hardware-bound examples (e.g. simple_capture.py, advanced_analysis.py)
cannot be executed headless, so their fixes are covered by the token scan and the
compile check, not by running them.
"""

import json
import py_compile
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

# Strings that must never appear under examples/ again.
FORBIDDEN = ["Siglent-Oscilloscope", ".time_interval", 'format="NPZ"']


def _example_text(path):
    """Scannable text for an example. For a notebook, return the concatenated
    cell SOURCE (unescaped Python), not the raw JSON -- otherwise a token like
    format="NPZ" is stored escaped (format=\\"NPZ\\") and a raw scan misses it."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        parts = []
        for cell in nb.get("cells", []):
            src = cell.get("source", [])
            parts.append(src if isinstance(src, str) else "".join(src))
        return "\n".join(parts)
    return path.read_text(encoding="utf-8")


def test_no_stale_tokens():
    hits = []
    for path in sorted(EXAMPLES_DIR.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".ipynb"}:
            text = _example_text(path)
            for token in FORBIDDEN:
                if token in text:
                    hits.append(f"{path.name}: {token!r}")
    assert not hits, "stale tokens found:\n" + "\n".join(hits)


@pytest.mark.parametrize("path", sorted(EXAMPLES_DIR.glob("*.py")), ids=lambda p: p.name)
def test_example_compiles(path):
    py_compile.compile(str(path), doraise=True)


def test_notebook_is_valid_json():
    nb = EXAMPLES_DIR / "interactive_tutorial.ipynb"
    json.loads(nb.read_text(encoding="utf-8"))
