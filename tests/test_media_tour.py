"""The demo GIFs must reference examples that exist and that CI executes.

Parsed from source rather than imported: importing a generator would require
Pillow, which is not installed in every CI job. Parsing uses `ast` rather than
regex so it is immune to quote style, tuple arity, and reformatting.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "media" / "make_demo_gif.py"
ANNOTATION_GENERATOR = REPO_ROOT / "scripts" / "media" / "make_annotation_gif.py"
GALLERY_GENERATOR = REPO_ROOT / "scripts" / "media" / "make_signal_gallery_gifs.py"
SUPERPOSITION_GALLERY_GENERATOR = REPO_ROOT / "scripts" / "media" / "make_superposition_gallery_gifs.py"
CLIPPING_GALLERY_GENERATOR = REPO_ROOT / "scripts" / "media" / "make_clipping_gallery_gifs.py"
DISTORTION_GALLERY_GENERATOR = REPO_ROOT / "scripts" / "media" / "make_distortion_gallery_gifs.py"
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


def test_annotation_gif_points_at_a_real_covered_example():
    """The annotation GIF's closing line sends viewers to a worked example.

    Unlike the tour above, this entry is allowed to be gated on reportlab: the
    annotation feature renders reports, so there is no ungated example that could
    cover it. The generator's own guards carry the rest of the weight -- it
    executes the code it renders and refuses to write a GIF if that raises.
    """
    example = _table(ANNOTATION_GENERATOR, "EXAMPLE")
    assert (REPO_ROOT / example).is_file(), f"the annotation GIF points at a missing file: {example}"

    name = Path(example).name
    assert name in _execute_names(), f"{example} is referenced by the annotation GIF but is not in EXECUTE, so nothing proves it still runs"


def _annotation_snippet():
    """The exact source the annotation GIF renders and executes.

    SNIPPET is a triple-quoted string with .splitlines() called on it, so the
    Assign's value is a Call, not a literal -- literal_eval the string the method
    is called on rather than the call itself.
    """
    tree = ast.parse(ANNOTATION_GENERATOR.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SNIPPET" for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call):  # ....splitlines()
                value = value.func.value
            return ast.literal_eval(value).strip("\n")
    raise AssertionError(f"no SNIPPET found in {ANNOTATION_GENERATOR}")


def test_readme_snippet_matches_the_gif_exactly():
    """The README's annotation block is the code the GIF actually runs.

    A pasted copy is a drift risk the moment the generator's snippet changes: the
    README would then teach an API the GIF does not demonstrate, and neither would
    look wrong on its own. Compared byte-for-byte rather than loosely, since the
    whole point is that a reader can copy one and see the other happen.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    marker = "<!-- annotation-snippet:"
    assert marker in readme, "the README's annotation snippet marker is gone -- was the block removed or renamed?"

    after_marker = readme.split(marker, 1)[1]
    fence = "```python\n"
    assert fence in after_marker, "no python code fence follows the annotation-snippet marker"
    block = after_marker.split(fence, 1)[1].split("```", 1)[0].strip("\n")

    assert block == _annotation_snippet(), "README annotation snippet has drifted from SNIPPET in scripts/media/make_annotation_gif.py -- edit the generator, re-run it, and paste the result"


def test_annotation_gif_snippet_names_that_example():
    """The rendered code ends with a pointer to the example; keep them in sync.

    The generator checks this too, but only when someone regenerates the GIF --
    this fails in CI the moment a rename breaks the pointer.
    """
    example = _table(ANNOTATION_GENERATOR, "EXAMPLE")
    snippet = ANNOTATION_GENERATOR.read_text(encoding="utf-8")
    assert Path(example).name in snippet, f"the annotation GIF's snippet no longer names {example}"


def _gallery_kinds():
    return _table(GALLERY_GENERATOR, "KINDS")


def _gallery_kind_names():
    return {entry["kind"] for entry in _gallery_kinds()}


def test_gallery_kinds_cover_every_signal_synth_generator():
    """The signal gallery must show every kind signal_synth actually has.

    Imports scpi_control.signal_synth directly rather than parsing it -- that
    module has no Pillow dependency, so unlike the gallery generator itself,
    a real import is both safe and the more faithful source of truth for
    "what kinds exist".
    """
    from scpi_control.signal_synth import _GENERATORS

    names = _gallery_kind_names()
    assert names == set(_GENERATORS), f"the signal gallery's KINDS table covers {sorted(names)} but signal_synth._GENERATORS has {sorted(_GENERATORS)} -- add or remove a gallery entry to match"


def test_gallery_kinds_table_is_not_empty():
    assert _gallery_kinds(), "parsed no KINDS entries -- the table shape changed"


def test_gallery_kinds_have_no_duplicate_or_missing_names():
    entries = _gallery_kinds()
    names = [entry["kind"] for entry in entries]
    assert len(names) == len(set(names)), f"KINDS has duplicate kind names: {names}"
    assert all(names), "KINDS has an entry with an empty/falsy kind name"


def test_readme_signal_gallery_matches_the_generator_exactly():
    """The README's gallery must embed exactly the GIFs the script writes.

    Regex over the README rather than a fixed count: this fails the moment
    someone adds a kind to KINDS without adding its <img> (or vice versa), or
    typos a filename, rather than silently shipping a stale gallery.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    referenced = re.findall(r"docs/images/signal-([a-z0-9]+)\.gif", readme)

    kind_names = _gallery_kind_names()
    assert referenced, "README has no docs/images/signal-*.gif references -- was the gallery section removed?"
    assert len(referenced) == len(kind_names), f"README references {len(referenced)} signal-*.gif images but KINDS has {len(kind_names)} entries"
    assert set(referenced) == kind_names, f"README's signal gallery images {sorted(set(referenced))} don't match KINDS {sorted(kind_names)}"
    assert len(referenced) == len(set(referenced)), f"README references a signal-*.gif image more than once: {referenced}"


def _superposition_combos():
    return _table(SUPERPOSITION_GALLERY_GENERATOR, "COMBOS")


def _superposition_combo_names():
    return {entry["name"] for entry in _superposition_combos()}


def test_superposition_combos_table_is_not_empty():
    assert _superposition_combos(), "parsed no COMBOS entries -- the table shape changed"


def test_superposition_combos_have_no_duplicate_or_missing_names():
    entries = _superposition_combos()
    names = [entry["name"] for entry in entries]
    assert len(names) == len(set(names)), f"COMBOS has duplicate combo names: {names}"
    assert all(names), "COMBOS has an entry with an empty/falsy name"


def test_readme_superposition_gallery_matches_the_generator_exactly():
    """The README's superposition gallery must embed exactly the GIFs the script writes.

    Regex over the README rather than a fixed count, mirroring
    test_readme_signal_gallery_matches_the_generator_exactly: this fails the
    moment someone adds a combo to COMBOS without adding its <img> (or vice
    versa), or typos a filename, rather than silently shipping a stale gallery.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    referenced = re.findall(r"docs/images/superposition-([a-z0-9_]+)\.gif", readme)

    combo_names = _superposition_combo_names()
    assert referenced, "README has no docs/images/superposition-*.gif references -- was the gallery section removed?"
    assert len(referenced) == len(combo_names), f"README references {len(referenced)} superposition-*.gif images but COMBOS has {len(combo_names)} entries"
    assert set(referenced) == combo_names, f"README's superposition gallery images {sorted(set(referenced))} don't match COMBOS {sorted(combo_names)}"
    assert len(referenced) == len(set(referenced)), f"README references a superposition-*.gif image more than once: {referenced}"


def _clipping_demos():
    return _table(CLIPPING_GALLERY_GENERATOR, "DEMOS")


def _clipping_demo_names():
    return {entry["name"] for entry in _clipping_demos()}


def test_clipping_demos_table_is_not_empty():
    assert _clipping_demos(), "parsed no DEMOS entries -- the table shape changed"


def test_clipping_demos_have_no_duplicate_or_missing_names():
    entries = _clipping_demos()
    names = [entry["name"] for entry in entries]
    assert len(names) == len(set(names)), f"DEMOS has duplicate demo names: {names}"
    assert all(names), "DEMOS has an entry with an empty/falsy name"


def test_readme_clipping_gallery_matches_the_generator_exactly():
    """The README's clipping gallery must embed exactly the GIFs the script writes.

    Regex over the README rather than a fixed count, mirroring
    test_readme_signal_gallery_matches_the_generator_exactly and
    test_readme_superposition_gallery_matches_the_generator_exactly: this fails
    the moment someone adds a demo to DEMOS without adding its <img> (or vice
    versa), or typos a filename, rather than silently shipping a stale gallery.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    referenced = re.findall(r"docs/images/clipping-([a-z0-9_]+)\.gif", readme)

    demo_names = _clipping_demo_names()
    assert referenced, "README has no docs/images/clipping-*.gif references -- was the gallery section removed?"
    assert len(referenced) == len(demo_names), f"README references {len(referenced)} clipping-*.gif images but DEMOS has {len(demo_names)} entries"
    assert set(referenced) == demo_names, f"README's clipping gallery images {sorted(set(referenced))} don't match DEMOS {sorted(demo_names)}"
    assert len(referenced) == len(set(referenced)), f"README references a clipping-*.gif image more than once: {referenced}"


def _distortion_demos():
    return _table(DISTORTION_GALLERY_GENERATOR, "DEMOS")


def _distortion_demo_names():
    return {entry["name"] for entry in _distortion_demos()}


def test_distortion_demos_table_is_not_empty():
    assert _distortion_demos(), "parsed no DEMOS entries -- the table shape changed"


def test_distortion_demos_have_no_duplicate_or_missing_names():
    entries = _distortion_demos()
    names = [entry["name"] for entry in entries]
    assert len(names) == len(set(names)), f"DEMOS has duplicate demo names: {names}"
    assert all(names), "DEMOS has an entry with an empty/falsy name"


def test_readme_distortion_gallery_matches_the_generator_exactly():
    """The README's distortion gallery must embed exactly the GIFs the script writes.

    Regex over the README rather than a fixed count, mirroring
    test_readme_signal_gallery_matches_the_generator_exactly,
    test_readme_superposition_gallery_matches_the_generator_exactly, and
    test_readme_clipping_gallery_matches_the_generator_exactly: this fails the
    moment someone adds a demo to DEMOS without adding its <img> (or vice
    versa), or typos a filename, rather than silently shipping a stale gallery.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    referenced = re.findall(r"docs/images/distortion-([a-z0-9_]+)\.gif", readme)

    demo_names = _distortion_demo_names()
    assert referenced, "README has no docs/images/distortion-*.gif references -- was the gallery section removed?"
    assert len(referenced) == len(demo_names), f"README references {len(referenced)} distortion-*.gif images but DEMOS has {len(demo_names)} entries"
    assert set(referenced) == demo_names, f"README's distortion gallery images {sorted(set(referenced))} don't match DEMOS {sorted(demo_names)}"
    assert len(referenced) == len(set(referenced)), f"README references a distortion-*.gif image more than once: {referenced}"
