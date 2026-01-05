# Version Bumping Guide

This guide explains how to bump the package version for new releases.

## Quick Start

The project includes an automated version bumping script that handles all version updates across the codebase.

### Interactive Mode

For an interactive prompt that guides you through the process:

```bash
make version-bump
```

The script will ask you:
1. Is this a major release? (X.0.0)
2. Is this a minor release? (0.X.0)
3. Is this a patch release? (0.0.X)
4. If you say no to all, you can enter a custom version

### Shortcut Commands

For quick bumps without prompts:

```bash
# Bump patch version (0.5.1 -> 0.5.2)
make bump-patch

# Bump minor version (0.5.1 -> 0.6.0)
make bump-minor

# Bump major version (0.5.1 -> 1.0.0)
make bump-major
```

## What the Script Does

The version bump script performs the following steps:

### 1. Version Consistency Check ✓

Verifies that all version numbers in the codebase match:
- `pyproject.toml`
- `siglent/__init__.py`

If versions don't match, the script will error and show you the mismatch.

### 2. Test Suite Execution ✓

Runs the full test suite (excluding codecov) to ensure code quality:

```bash
python -m pytest tests/ -v
```

If tests fail, you'll be prompted to either:
- Fix the tests and try again
- Skip tests and continue anyway (not recommended)

### 3. Version Determination ✓

Determines the new version based on:
- Command-line argument (`--major`, `--minor`, `--patch`)
- Interactive user input
- Manual version entry (if all prompts answered "no")

### 4. Version Validation ✓

Validates the version bump according to semantic versioning rules:

**Required:**
- Only ONE version number can change at a time
- Version numbers must increase (no downgrades)
- Format must be `MAJOR.MINOR.PATCH`

**Warnings:**
- Skipping versions (e.g., 0.5.1 → 0.7.0)
- Major bump without resetting minor/patch to 0
- Minor bump without resetting patch to 0

### 5. File Updates ✓

Updates the following files:

**pyproject.toml**
```toml
version = "0.5.2"
```

**siglent/__init__.py**
```python
__version__ = "0.5.2"
```

**CHANGELOG.md**
```markdown
## [Unreleased]

## [0.5.2] - 2026-01-05

### Added

### Changed

### Fixed

## [0.5.1] - 2026-01-05
...
```

## Semantic Versioning

The project follows [Semantic Versioning 2.0.0](https://semver.org/):

### MAJOR version (X.0.0)

**When to bump:**
- Breaking changes to the public API
- Incompatible API changes
- Removal of deprecated features

**Examples:**
- Renaming public classes or methods
- Changing function signatures
- Removing backward compatibility

**Best practices:**
- Reset minor and patch to 0 (e.g., 0.5.1 → 1.0.0)
- Document migration guide in CHANGELOG
- Provide deprecation warnings in previous version

### MINOR version (0.X.0)

**When to bump:**
- New features added
- Backward-compatible functionality
- Deprecating features (without removal)

**Examples:**
- New API methods
- New GUI features
- New optional parameters with defaults

**Best practices:**
- Reset patch to 0 (e.g., 0.5.1 → 0.6.0)
- Document new features in CHANGELOG
- Maintain backward compatibility

### PATCH version (0.0.X)

**When to bump:**
- Bug fixes
- Performance improvements
- Documentation updates
- Internal refactoring

**Examples:**
- Fixing broken functionality
- Correcting typos
- Improving error messages
- Optimizing algorithms

**Best practices:**
- No API changes
- Only increment patch (e.g., 0.5.1 → 0.5.2)
- Document fixes in CHANGELOG

## Complete Workflow Example

Here's a typical workflow for releasing a new version:

### Step 1: Prepare Changes

Make your changes, commit them, and ensure tests pass:

```bash
# Make changes
git add .
git commit -m "Fix GUI freeze issue"

# Run tests
make test
```

### Step 2: Bump Version

Run the version bump script:

```bash
make version-bump
```

Output:
```
============================================================
Siglent-Oscilloscope Version Bump Script
============================================================

[1/5] Checking version consistency...
✓ All version numbers match: 0.5.1

[2/5] Running test suite...
✓ All tests passed

[3/5] Determining new version...

Current version: 0.5.1

Is this a MAJOR release (0.X.X -> 1.0.0)?
  (Breaking changes, incompatible API changes)
Bump major version? (y/N): n

Is this a MINOR release (0.5.X -> 0.6.0)?
  (New features, backward compatible)
Bump minor version? (y/N): n

Is this a PATCH release (0.5.1 -> 0.5.2)?
  (Bug fixes, backward compatible)
Bump patch version? (y/N): y

[4/5] Validating version bump...
✓ Version bump validated: 0.5.1 -> 0.5.2

[5/5] Updating files...

Ready to bump version from 0.5.1 to 0.5.2
This will update:
  - pyproject.toml
  - siglent/__init__.py
  - CHANGELOG.md

Proceed with version bump? (y/N): y

✓ Updated pyproject.toml
✓ Updated siglent/__init__.py
✓ Updated CHANGELOG.md with version 0.5.2

============================================================
✓ Successfully bumped version to 0.5.2
============================================================

Next steps:
  1. Edit CHANGELOG.md to document changes for v0.5.2
  2. Review the changes: git diff
  3. Commit: git add -A && git commit -m 'Bump version to v0.5.2'
  4. Tag: git tag v0.5.2
  5. Push: git push origin <branch> --tags
```

### Step 3: Update CHANGELOG

Edit `CHANGELOG.md` to document your changes:

```markdown
## [0.5.2] - 2026-01-05

### Fixed

**GUI Improvements**
- Fixed GUI freeze during waveform capture
- Improved responsiveness during long SCPI queries
- Enhanced error handling for connection timeouts
```

### Step 4: Review Changes

```bash
git diff
```

Verify that:
- Version numbers are correct in all files
- CHANGELOG has your changes documented
- No unexpected modifications

### Step 5: Commit and Tag

```bash
# Commit version bump
git add -A
git commit -m "Bump version to v0.5.2"

# Create git tag
git tag v0.5.2

# Push to remote
git push origin docs/fixing-autodocs
git push origin v0.5.2
```

### Step 6: Create Release

After merging to main:

1. Go to GitHub → Releases → "Draft a new release"
2. Choose tag `v0.5.2`
3. Title: `v0.5.2`
4. Description: Copy from CHANGELOG.md
5. Publish release

The CI/CD workflow will automatically:
- Build the package
- Run tests
- Publish to PyPI
- Deploy documentation

## Troubleshooting

### Version Mismatch Error

```
ERROR: Version mismatch detected!
  pyproject.toml: 0.5.1
  siglent/__init__.py: 0.5.0
```

**Solution:** Manually fix the version mismatch in one of the files, then run again.

### Test Failures

```
✗ Tests failed:
FAILED tests/test_oscilloscope.py::test_connection
```

**Solution:** Fix the failing tests before bumping version, or skip with caution:
```
Skip tests and continue anyway? (y/N): y
```

### Invalid Version Format

```
Invalid version format: 0.5.a
Version must be in format: MAJOR.MINOR.PATCH (e.g., 0.5.2)
```

**Solution:** Use numeric values only in format `X.Y.Z`.

### Validation Warnings

```
WARNING: When bumping major version, minor and patch should be 0
  Suggested: 1.0.0
Continue anyway? (y/N):
```

**Solution:** Follow semantic versioning conventions or confirm if you have a specific reason.

## Advanced Usage

### Skip Interactive Prompts

Use command-line flags for automated workflows:

```bash
# Direct patch bump
python scripts/bump_version.py --patch

# Direct minor bump
python scripts/bump_version.py --minor

# Direct major bump
python scripts/bump_version.py --major
```

### Custom Version Number

If you need a specific version that doesn't follow the increment pattern:

```bash
make version-bump
# Answer 'n' to all prompts
# Enter custom version: 0.7.0
```

The script will still validate:
- Format (must be MAJOR.MINOR.PATCH)
- Only one number changed
- No version downgrade

## Best Practices

1. **Always run tests** before bumping version
2. **Document changes** in CHANGELOG.md immediately after bump
3. **Use semantic versioning** conventions strictly
4. **Review changes** with `git diff` before committing
5. **Tag releases** with `git tag vX.Y.Z`
6. **Keep CHANGELOG updated** with meaningful descriptions
7. **Use commit message**: `Bump version to vX.Y.Z`

## Version Bump Checklist

- [ ] All changes committed
- [ ] Tests passing (`make test`)
- [ ] Version consistency verified
- [ ] Correct bump type selected (major/minor/patch)
- [ ] CHANGELOG.md updated with changes
- [ ] Changes reviewed (`git diff`)
- [ ] Version bump committed
- [ ] Git tag created
- [ ] Changes pushed to remote with tags
- [ ] Release created on GitHub (after merge to main)

## See Also

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Contributing Guide](../CONTRIBUTING.md)
- [Release Workflow](PYPI_DEPLOYMENT.md)
