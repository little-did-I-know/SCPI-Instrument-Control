"""The demo GIF's tour must reference examples that exist and that CI executes.

Parsed from source rather than imported: importing the generator would require
Pillow, which is not installed in every CI job.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "media" / "make_demo_gif.py"
SMOKE = REPO_ROOT / "tests" / "test_examples_smoke.py"


def _tour_entries():
    block = re.search(r"^TOUR\s*=\s*\[(.*?)^\]", GENERATOR.read_text(encoding="utf-8"), re.S | re.M)
    assert block, f"no TOUR table found in {GENERATOR}"
    return re.findall(r'\(\s*"([^"]+\.py)"\s*,\s*(\d+)\s*\)', block.group(1))


def _execute_names():
    block = re.search(r"^EXECUTE\s*=\s*\[(.*?)^\]", SMOKE.read_text(encoding="utf-8"), re.S | re.M)
    assert block, f"no EXECUTE list found in {SMOKE}"
    return {name for name in re.findall(r'\(\s*"([^"]+\.py)"', block.group(1))}


def test_tour_is_not_empty():
    assert _tour_entries(), "parsed no TOUR entries -- the regex or the table shape changed"


def test_tour_examples_exist():
    for rel, _ in _tour_entries():
        assert (REPO_ROOT / rel).is_file(), f"the demo GIF tour references a missing file: {rel}"


def test_tour_examples_are_covered_by_the_execution_guard():
    execute = _execute_names()
    assert execute, "parsed no EXECUTE entries -- the regex or the list shape changed"
    for rel, _ in _tour_entries():
        # TOUR paths are repo-relative; EXECUTE entries are bare filenames.
        name = Path(rel).name
        assert name in execute, f"{rel} appears in the demo GIF tour but not in EXECUTE, so nothing proves it still runs"
