# Pre-Commit and Code Coverage Guide

This document explains the pre-commit checks and code coverage tools available in the project.

## Quick Reference

```bash
# Before committing to your branch
make pre-commit-branch

# Before creating a pull request
make pre-pr

# Generate coverage report
make test-cov

# Upload coverage to Codecov
make codecov-report
```

## Pre-Commit Checks

### `make pre-commit-branch`

Lightweight checks for branch commits. Runs before you commit code to your feature branch.

**What it checks:**
- ✅ Code formatting (Black, Flake8)
- ✅ Quick test suite (parallel execution)

**When to use:** Before every commit on your feature branch

**Time:** ~30 seconds - 2 minutes

```bash
# Make your changes
git add .

# Run checks
make pre-commit-branch

# If passed, commit
git commit -m "your message"
```

### `make pre-pr`

Comprehensive validation before creating a pull request. This is the **full check** that includes everything.

**What it checks:**
- ✅ All code formatting and linting
- ✅ Full test suite
- ✅ Security checks
- ✅ Package build validation
- ✅ Code coverage generation and upload

**When to use:** Before creating or updating a pull request

**Time:** ~3-5 minutes

```bash
# Run before creating PR
make pre-pr

# If passed, you're ready to create/update PR
git push origin your-branch
```

### `make pre-pr-fast`

Quick pre-PR validation that skips slow checks (coverage, full build).

**When to use:** During active development when you want quick feedback

**Time:** ~1-2 minutes

### `make pre-pr-fix`

Runs pre-PR validation with automatic fixing of formatting issues.

**When to use:** When you have formatting violations and want them auto-fixed

## Code Coverage

### Understanding Coverage

Code coverage measures how much of your code is executed during tests. Higher coverage generally means more confident code changes.

**Coverage metrics:**
- **Line coverage:** Percentage of code lines executed
- **Branch coverage:** Percentage of code branches (if/else) executed
- **Function coverage:** Percentage of functions called

### `make test-cov`

Generate local coverage report (HTML + XML + terminal).

**Output files:**
- `htmlcov/index.html` - Interactive HTML report
- `coverage.xml` - Machine-readable XML for tools
- Terminal summary

**Usage:**
```bash
make test-cov

# Open the HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### `make codecov-report`

Generate coverage and upload to [Codecov](https://codecov.io).

**What it does:**
1. Runs full test suite with coverage
2. Generates coverage.xml
3. Uploads to Codecov

**Requirements:**
- Codecov account and repository setup
- `CODECOV_TOKEN` environment variable (for private repos)

**Usage:**
```bash
# Set token (one-time, for private repos)
export CODECOV_TOKEN=your-token-here

# Generate and upload
make codecov-report
```

### `make codecov-upload`

Upload existing coverage.xml to Codecov (doesn't run tests).

**When to use:** When you already have coverage.xml and just want to upload

### Configuration Files

#### `.codecov.yml`

Codecov configuration:
- Coverage thresholds (70-100%)
- Ignore patterns (tests/, scripts/, examples/)
- PR comment settings
- Status check behavior

#### `pyproject.toml` - Coverage Settings

```toml
[tool.coverage.run]
source = ["siglent"]
omit = ["*/tests/*", "*/examples/*", "*/scripts/*"]
branch = true

[tool.coverage.report]
precision = 2
show_missing = true
```

## Continuous Integration

The CI/CD pipeline automatically runs these checks:

**On every push:**
- Linting and formatting checks
- Full test suite
- Coverage generation

**On pull requests:**
- All of the above
- Coverage upload to Codecov
- Coverage comparison with base branch

## Best Practices

### Development Workflow

1. **During development:**
   ```bash
   # Make changes
   make format  # Auto-format code
   make test    # Run tests
   ```

2. **Before committing:**
   ```bash
   make pre-commit-branch
   git commit -m "your message"
   ```

3. **Before pushing:**
   ```bash
   # Optional: check coverage
   make test-cov
   ```

4. **Before creating PR:**
   ```bash
   make pre-pr
   git push origin your-branch
   # Create PR on GitHub
   ```

### Writing Tests

- Aim for **70%+ coverage** on new code
- Test edge cases and error paths
- Use descriptive test names
- Mark hardware tests: `@pytest.mark.hardware`
- Mark GUI tests: `@pytest.mark.gui`

### Coverage Goals

- **Minimum:** 70% overall coverage
- **Target:** 80-90% coverage
- **Critical code:** 95%+ coverage (core functionality)
- **Acceptable lower coverage:** Examples, scripts, GUI code

## Troubleshooting

### Coverage Upload Fails

**Problem:** `codecov-upload` fails with authentication error

**Solution:**
```bash
# For private repos, set token
export CODECOV_TOKEN=your-token-here

# For public repos, token is optional
make codecov-upload
```

### Pre-commit Checks Fail

**Problem:** `pre-commit-branch` fails on formatting

**Solution:**
```bash
# Auto-fix formatting
make format

# Re-run checks
make pre-commit-branch
```

### Tests Pass Locally But Fail in CI

**Problem:** Tests pass with `make test` but fail in CI

**Common causes:**
- Platform-specific behavior (Windows vs Linux)
- Missing dependencies
- Hardware-dependent tests
- Time-dependent tests

**Solution:**
```bash
# Run tests exactly as CI does
make test-cov

# Check for hardware/GUI tests that need markers
pytest tests/ -v --collect-only | grep "hardware\|gui"
```

## Additional Resources

- [Codecov Documentation](https://docs.codecov.com/)
- [pytest Coverage Plugin](https://pytest-cov.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Black Code Formatter](https://black.readthedocs.io/)
- [Flake8 Linter](https://flake8.pycqa.org/)

## Summary of Make Targets

| Command | Purpose | Time | When to Use |
|---------|---------|------|-------------|
| `make pre-commit-branch` | Lightweight branch checks | ~1 min | Before every commit |
| `make pre-pr` | Full PR validation + coverage | ~5 min | Before creating PR |
| `make pre-pr-fast` | Quick PR validation | ~2 min | During development |
| `make pre-pr-fix` | PR validation with auto-fix | ~5 min | When fixing format issues |
| `make test-cov` | Generate coverage report | ~2 min | Check local coverage |
| `make codecov-report` | Coverage + upload | ~3 min | Before/after PR |
| `make codecov-upload` | Upload existing coverage | ~10 sec | Re-upload after generation |

---

**Last Updated:** January 2026
