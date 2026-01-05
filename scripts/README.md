# Scripts Directory

This directory contains utility scripts for development and testing.

## Pre-PR Validation Scripts

### `pre_pr_check.py` (Recommended)

**Cross-platform Python script** for comprehensive pre-PR validation.

**Usage:**

```bash
# Run all checks
python scripts/pre_pr_check.py

# Quick checks (skip slow tests/coverage)
python scripts/pre_pr_check.py --fast

# Auto-fix formatting issues
python scripts/pre_pr_check.py --fix

# Combined: fast mode with auto-fix
python scripts/pre_pr_check.py --fast --fix

# Skip tests entirely (formatting/linting only)
python scripts/pre_pr_check.py --skip-tests --fix
```

**Or use Makefile shortcuts:**

```bash
make pre-pr          # Full validation
make pre-pr-fast     # Quick validation
make pre-pr-fix      # With auto-fix
```

**What it checks:**

- ✅ Git status (warns about uncommitted changes)
- ✅ Code formatting (Black)
- ✅ Import sorting (isort)
- ✅ Linting (flake8)
- ✅ Security scanning (bandit)
- ✅ Test suite (pytest)
- ✅ Code coverage
- ✅ Package build validation (twine)

**Features:**

- Color-coded output
- Detailed error messages
- Auto-fix capability
- Fast mode for quick iteration
- Comprehensive summary report

---

### `pre_pr_check.sh`

**Bash script** for Unix-like systems (Linux, macOS, Git Bash on Windows).

**Usage:**

```bash
# Run all checks
bash scripts/pre_pr_check.sh

# Quick checks
bash scripts/pre_pr_check.sh --fast

# Auto-fix formatting
bash scripts/pre_pr_check.sh --fix
```

Simpler alternative to the Python version, performs the same core checks.

---

## Manual Test Scripts

These scripts are for **interactive testing** and should **not** be run by pytest.

### `manual_test_live_view.py`

Interactive GUI test for live view functionality. Requires PyQt6.

### `manual_test_pyqtgraph.py`

Visual test for PyQtGraph integration showing a test waveform.

### `manual_test_waveform_display.py`

Interactive test for the waveform display widget with test buttons.

### `manual_test_dependency_check.py`

Demonstrates the dependency checker behavior for GUI components.

**To run these:**

```bash
python scripts/manual_test_live_view.py
python scripts/manual_test_pyqtgraph.py
# etc.
```

---

## Tips for Contributors

**Before creating a PR:**

1. Run `make pre-pr` to validate everything
2. Fix any issues reported
3. If you have formatting issues: `make pre-pr-fix`
4. During development: `make pre-pr-fast` for quick checks

**Quick iteration cycle:**

```bash
# Make changes to code
# ...

# Quick check (fast mode with auto-fix)
python scripts/pre_pr_check.py --fast --fix

# If all passes, run full validation
make pre-pr
```

This will save you time by catching issues locally before CI runs!
