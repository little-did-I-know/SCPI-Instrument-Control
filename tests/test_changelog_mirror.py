"""`docs/about/changelog.md` is a byte-for-byte copy of `CHANGELOG.md`.

The repo keeps two changelogs: `CHANGELOG.md` at the root, and a copy under
`docs/` that mkdocs publishes (`mkdocs.yml` maps it to `about/changelog.md`).
Nothing generated the copy and nothing checked it, so keeping them identical was
a step someone had to remember in every change that touched a changelog -- and
in one release it was forgotten, shipping a docs site whose changelog was
missing the entry the release existed to describe.

This is the same class of defect as tests/test_version_consistency.py: two
hand-maintained files that must agree, with no mechanism enforcing it.

No `skip` and no tolerance for "close enough". A drift of one line is exactly
the drift that happens, and it is invisible until someone reads the published
site.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_CHANGELOG = REPO_ROOT / "CHANGELOG.md"
DOCS_CHANGELOG = REPO_ROOT / "docs" / "about" / "changelog.md"


def test_both_changelogs_exist():
    """Fail loudly rather than vacuously passing if either file is moved."""
    assert ROOT_CHANGELOG.is_file(), f"missing {ROOT_CHANGELOG}"
    assert DOCS_CHANGELOG.is_file(), f"missing {DOCS_CHANGELOG}"


def test_the_docs_changelog_matches_the_root_changelog():
    """Read as text so the comparison is about CONTENT, not line endings.

    Git may check the two files out with different EOLs depending on
    `core.autocrlf` and `.gitattributes`; that is not drift worth failing on.
    A missing or reworded entry is.
    """
    root = ROOT_CHANGELOG.read_text(encoding="utf-8")
    docs = DOCS_CHANGELOG.read_text(encoding="utf-8")
    if root == docs:
        return

    root_lines = root.splitlines()
    docs_lines = docs.splitlines()
    first_difference = next(
        (i for i, (a, b) in enumerate(zip(root_lines, docs_lines)) if a != b),
        min(len(root_lines), len(docs_lines)),
    )
    raise AssertionError(
        "docs/about/changelog.md has drifted from CHANGELOG.md.\n"
        f"First difference at line {first_difference + 1} "
        f"(root has {len(root_lines)} lines, docs has {len(docs_lines)}).\n"
        f"  CHANGELOG.md:            {root_lines[first_difference:first_difference + 1] or ['<end of file>']}\n"
        f"  docs/about/changelog.md: {docs_lines[first_difference:first_difference + 1] or ['<end of file>']}\n"
        "Fix by copying the root file over the docs one:\n"
        "  cp CHANGELOG.md docs/about/changelog.md"
    )
