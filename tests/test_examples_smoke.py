"""Smoke-tests for the examples/ tree.

Guards three things: (1) no known-stale tokens survive (verifies the fixes and
blocks their reintroduction), (2) every .py example at least compiles, (3) the
notebook is valid JSON. Task 2 adds a fourth guard: executing the no-hardware
examples as subprocesses.

Limitation: hardware-bound examples (e.g. simple_capture.py, advanced_analysis.py)
cannot be executed headless, so their fixes are covered by the token scan and the
compile check, not by running them.

The execution guard is the expensive one -- each example is a real subprocess, and
report_ai_qa.py additionally does live inference wherever a local Ollama is running.
It is marked `slow` so tight edit loops can deselect it with `-m "not slow"`; the
scan/compile guards stay cheap and always run. Do not deselect it by default in
pyproject `addopts`: CI invokes a bare `pytest` and reads the same config, so that
would silently strip example coverage from CI. Execution is what catches API drift
that a compile check cannot -- a call to a method that no longer exists compiles
perfectly and fails only at runtime.
"""

import importlib.util
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

# Strings that must never appear under examples/ again.
# Note: a bare "SDS1104X-E" token would also hit dialect_override_example.py,
# synthetic_signals.py, and waveform_provenance_and_extract.py, which legitimately
# use that model number inside a mock *IDN? string (idn="Siglent Technologies,
# SDS1104X-E,...") to exercise dialect detection -- not the M1 defect (stamping a
# real instrument identity onto synthetic report/waveform provenance). The
# narrower `="SDS1104X-E"` matches only the kwarg-assignment shape the M1 fixes
# actually removed (model="SDS1104X-E", equipment_model="SDS1104X-E").
# NOTE: 'format="NPZ"' used to live here, banning the one spelling someone had
# been bitten by. The ban was a case-fold away from useless -- lowercase
# format="npz" failed identically and sailed through -- and NPZ is now a valid
# alias for NPY anyway. tests/test_save_format_aliases.py covers the real
# regression instead.
FORBIDDEN = ["Siglent-Oscilloscope", ".time_interval", '="SDS1104X-E"']

# (filename, module-that-must-import-or-skip). Only examples that run to
# completion headless with no instrument belong here. report_generation_example.py's
# synthetic waveform was reduced to ~1000 samples so analysis runs in ~1.8s. Note:
# a pre-existing O(n^2) autocorrelation in scpi_control/report_generator/utils/
# waveform_analyzer.py makes very large captures slow; this library issue is out of scope.
EXECUTE = [
    ("dialect_override_example.py", None),
    ("trend_logging_walkthrough.py", None),
    ("psu_advanced_features.py", None),
    ("probe_calibration_analysis.py", "reportlab"),
    ("report_generation_example.py", "requests"),
    ("report_computed_analysis.py", None),
    ("report_branding.py", None),
    ("network_discovery.py", None),
    ("report_ai_qa.py", "requests"),
    ("waveform_provenance_and_extract.py", None),
    ("synthetic_signals.py", None),
    ("comparison_report.py", None),
    ("batch_report.py", None),
]

_TIMEOUTS = {"report_ai_qa.py": 240}
_DEFAULT_TIMEOUT = 90


def _available(module):
    return module is None or importlib.util.find_spec(module) is not None


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


@pytest.mark.slow
@pytest.mark.parametrize("filename, module", EXECUTE, ids=[f for f, _ in EXECUTE])
def test_no_hardware_example_runs(filename, module, tmp_path):
    if not _available(module):
        pytest.skip(f"optional dependency {module!r} not installed")
    path = EXAMPLES_DIR / filename
    assert path.exists(), f"missing example: {filename}"
    # PYTHONIOENCODING: some examples print unicode (checkmarks, etc.) and
    # Windows defaults a captured child's stdout/stderr to the cp1252
    # console codepage, which raises UnicodeEncodeError. utf-8 matches what
    # a real terminal on any platform would accept.
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=tmp_path,
        env=env,
        # input="" (rather than stdin=subprocess.DEVNULL) closes stdin after
        # writing nothing. On Windows, stdin=DEVNULL wires stdin to the NUL
        # device, and sys.stdin.isatty() reports True for NUL -- so an
        # example's "am I interactive?" check is fooled into calling input()
        # and hanging until the timeout. An empty piped stdin reports
        # isatty() False (as DEVNULL correctly does on POSIX) while still
        # never blocking: any input() call gets an immediate EOFError.
        input="",
        capture_output=True,
        text=True,
        timeout=_TIMEOUTS.get(filename, _DEFAULT_TIMEOUT),
    )
    assert result.returncode == 0, f"{filename} exited {result.returncode}\n--- stderr ---\n{result.stderr[-3000:]}"
