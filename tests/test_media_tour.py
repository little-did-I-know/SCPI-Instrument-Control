"""The demo GIF's tour must reference examples that exist and that CI executes.

Parsed from source rather than imported: importing the generator would require
Pillow, which is not installed in every CI job. Parsing uses `ast` rather than
regex so it is immune to quote style, tuple arity, and reformatting.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "media" / "make_demo_gif.py"
SMOKE = REPO_ROOT / "tests" / "test_examples_smoke.py"


def _table(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"no {name} table found in {path}")


def _tour_entries():
    return _table(GENERATOR, "TOUR")


def _execute_entries():
    return _table(SMOKE, "EXECUTE")


def _execute_names():
    return {n for n, _ in _execute_entries()}


def test_tour_is_not_empty():
    assert _tour_entries(), "parsed no TOUR entries -- the table shape changed"


def test_tour_examples_exist():
    for entry in _tour_entries():
        rel = entry[0]
        assert (REPO_ROOT / rel).is_file(), f"the demo GIF tour references a missing file: {rel}"


def test_tour_examples_are_covered_by_the_execution_guard():
    execute = dict(_execute_entries())
    assert execute, "parsed no EXECUTE entries -- the table shape changed"
    for entry in _tour_entries():
        rel = entry[0]
        # TOUR paths are repo-relative; EXECUTE entries are bare filenames.
        name = Path(rel).name
        assert name in execute, f"{rel} appears in the demo GIF tour but not in EXECUTE, so nothing proves it still runs"
        # A gated entry skips (rather than runs) in jobs lacking the optional
        # dependency, so it does not prove the example still works there.
        gate = execute[name]
        assert gate is None, f"{rel} is covered by an EXECUTE entry gated on {gate!r} -- a skipped test proves nothing, so this is not real coverage"
