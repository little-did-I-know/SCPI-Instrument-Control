# Building the Project

This guide covers how to build, test, and package the Siglent Oscilloscope Control library for development and distribution.

## Overview

The project uses a modern Python build system based on:

- **Build Backend**: `setuptools` with PEP 517/518 support
- **Build Tool**: `python -m build`
- **Configuration**: `pyproject.toml` (PEP 621 metadata)
- **Task Runner**: `Makefile` for common development tasks
- **Package Manager**: `pip` for dependency management
- **Distribution**: PyPI (Python Package Index)

## Prerequisites

### System Requirements

**Python Version:**

- Python 3.8 or later
- Supports: 3.8, 3.9, 3.10, 3.11, 3.12

**Operating Systems:**

- Linux (tested on Ubuntu 20.04+)
- macOS (tested on 10.15+)
- Windows (tested on Windows 10/11)

**Development Tools:**

- Git (for version control)
- Make (GNU Make or compatible)
- pip (comes with Python)

### Installing Prerequisites

**Linux (Debian/Ubuntu):**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git make
```

**macOS:**

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install prerequisites
brew install python git make
```

**Windows:**

- Install [Python from python.org](https://www.python.org/downloads/)
- Install [Git for Windows](https://git-scm.com/download/win)
- Make is included with Git Bash or install via [Chocolatey](https://chocolatey.org/): `choco install make`

## Quick Start

### Clone Repository

```bash
git clone https://github.com/little-did-I-know/Siglent-Oscilloscope.git
cd Siglent-Oscilloscope
```

### Development Setup

**Complete environment setup (recommended):**

```bash
make dev-setup
```

This command:

1. Installs package in editable mode
2. Installs all dependencies (core + optional + dev)
3. Sets up pre-commit hooks
4. Configures development environment

**Manual setup:**

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with all dependencies
pip install -e ".[all,dev]"
```

### Verify Installation

```bash
# Show available make commands
make help

# Check package version
make version

# Run tests
make test
```

## Installation Options

The package has several installation profiles for different use cases:

### Core Package (Basic)

**Minimal installation:**

```bash
pip install -e .
```

**Dependencies:**

- `numpy>=1.24.0`
- `matplotlib>=3.7.0`
- `scipy>=1.10.0`

**Use Case:** Basic oscilloscope control, waveform capture, measurements

### Development Installation

**With development tools:**

```bash
pip install -e ".[dev]"
```

**Additional Dependencies:**

- `pytest>=7.0` - Testing framework
- `black>=23.0` - Code formatter
- `flake8>=6.0` - Linter
- `build>=0.10.0` - Build tool
- `twine>=4.0.0` - Package upload tool

**Use Case:** Contributing to the project, running tests

### GUI Installation

**With PyQt6 GUI:**

```bash
pip install -e ".[gui]"
```

**Additional Dependencies:**

- `PyQt6>=6.6.0` - Qt6 GUI framework
- `PyQt6-WebEngine>=6.6.0` - Web rendering (for VNC)
- `pyqtgraph>=0.13.0` - High-performance plotting

**Use Case:** Using the graphical interface

### HDF5 Support

**With HDF5 file format support:**

```bash
pip install -e ".[hdf5]"
```

**Additional Dependencies:**

- `h5py>=3.8.0` - HDF5 file format

**Use Case:** Saving large datasets in HDF5 format

### Vector Graphics (Fun!)

**With vector graphics features:**

```bash
pip install -e ".[fun]"
```

**Additional Dependencies:**

- `shapely>=2.0.0` - Geometric operations
- `Pillow>=10.0.0` - Image processing
- `svgpathtools>=1.6.0` - SVG path manipulation

**Use Case:** Creating XY mode shapes, waveform art

### Documentation Tools

**With documentation generation:**

```bash
pip install -e ".[docs]"
```

**Additional Dependencies:**

- `mkdocs>=1.5.0` - Documentation generator
- `mkdocs-material>=9.5.0` - Material theme
- `mkdocstrings[python]>=0.24.0` - API documentation from docstrings
- `mkdocs-gen-files>=0.5.0` - Dynamic file generation
- `mkdocs-literate-nav>=0.6.0` - Navigation from files
- `mkdocs-section-index>=0.3.0` - Section indexes

**Use Case:** Building and serving documentation

### Complete Installation

**All optional dependencies:**

```bash
make install-all
# or
pip install -e ".[all,dev]"
```

**Use Case:** Full development environment with all features

## Building the Package

### Build Distribution Packages

**Using Make:**

```bash
make build
```

**Manual build:**

```bash
# Install build tool
pip install build twine

# Build source and wheel distributions
python -m build

# Verify packages
twine check dist/*
```

**Output:**

```
dist/
  Siglent_Oscilloscope-0.3.0.tar.gz          # Source distribution
  Siglent_Oscilloscope-0.3.0-py3-none-any.whl  # Wheel distribution
```

### Clean Build Artifacts

**Remove all build artifacts:**

```bash
make clean
```

This removes:

- `build/` - Build directory
- `dist/` - Distribution packages
- `*.egg-info` - Package metadata
- `.pytest_cache` - Test cache
- `.coverage`, `htmlcov/` - Coverage reports
- `__pycache__` directories
- `*.pyc` files

### Build Process Details

**What happens during build:**

1. **Parse Configuration**
   - Read `pyproject.toml`
   - Extract package metadata
   - Identify dependencies

2. **Find Packages**
   - Scan for `siglent*` packages
   - Include package data (`py.typed`)

3. **Build Source Distribution (sdist)**
   - Create `.tar.gz` archive
   - Include source files
   - Add metadata

4. **Build Wheel (bdist_wheel)**
   - Create `.whl` file
   - Compiled bytecode
   - Platform-independent (`py3-none-any`)

5. **Validation**
   - Check metadata completeness
   - Verify README rendering
   - Validate package structure

## Testing

### Run Tests

**All tests:**

```bash
make test
```

**With coverage report:**

```bash
make test-cov
```

Opens `htmlcov/index.html` with detailed coverage report.

**Fast parallel testing:**

```bash
make test-fast
```

Uses `pytest-xdist` for parallel test execution.

**Specific tests:**

```bash
# Test specific file
pytest tests/test_oscilloscope.py -v

# Test specific function
pytest tests/test_oscilloscope.py::test_connection -v

# Test with markers
pytest tests/ -m "not hardware" -v  # Skip hardware tests
pytest tests/ -m gui -v              # Only GUI tests
```

### Test Markers

**Available markers:**

- `hardware` - Requires actual oscilloscope hardware
- `gui` - Requires GUI dependencies (PyQt6)

**Usage:**

```python
import pytest

@pytest.mark.hardware
def test_real_scope():
    """Test that requires connected oscilloscope."""
    pass

@pytest.mark.gui
def test_gui_window():
    """Test that requires PyQt6."""
    pass
```

**Skip hardware tests:**

```bash
pytest tests/ -m "not hardware"
```

### Coverage Requirements

**Current coverage targets:**

- **Overall**: >80%
- **Core modules**: >90%
- **GUI modules**: >70% (harder to test)

**View coverage:**

```bash
make test-cov
# Open htmlcov/index.html in browser
```

### Watch Mode

**Auto-run tests on file changes:**

```bash
make dev-test
```

Requires `pytest-watch`:

```bash
pip install pytest-watch
```

## Code Quality

### Linting

**Run all linting checks:**

```bash
make lint
```

**Checks performed:**

- **Black**: Code formatting (line length: 200)
- **Flake8**: Style guide enforcement

**Expected output:**

```
✓ All linting checks passed
```

### Formatting

**Auto-format code:**

```bash
make format
```

**Black configuration:**

- Line length: 200 characters
- Target: Python 3.8, 3.9, 3.10, 3.11, 3.12
- See `pyproject.toml` for details

**Formatted files:**

- `siglent/` - Main package
- `tests/` - Test files
- `examples/` - Example scripts

### Pre-commit Hooks

**Install hooks:**

```bash
make pre-commit-install
```

**Run manually:**

```bash
make pre-commit
```

**Configured hooks:**

- Trailing whitespace removal
- End-of-file fixer
- YAML syntax check
- Black formatting
- Flake8 linting

### Comprehensive Checks

**Run all checks before committing:**

```bash
make check
```

**Performs:**

1. Linting (Black + Flake8)
2. All tests
3. Build package
4. Validate distributions

**Pre-PR validation:**

```bash
make pre-pr
```

Runs comprehensive validation including:

- Code formatting
- Linting
- Type checking
- Tests with coverage
- Documentation build
- Package build

**Fast pre-PR (skip slow checks):**

```bash
make pre-pr-fast
```

**Auto-fix issues:**

```bash
make pre-pr-fix
```

## Documentation

### Generate Documentation

**From code docstrings:**

```bash
make docs-generate
```

**Runs scripts:**

- `scripts/docs/generate_examples_docs.py` - Creates example documentation
- `scripts/docs/generate_api_stubs.py` - Generates API reference from docstrings

**What gets generated:**

- API reference pages from Python docstrings
- Example documentation from `examples/` directory
- Navigation structure

### Build Documentation

**Build static site:**

```bash
make docs
```

**Output:** `site/` directory with static HTML

**Open documentation:**

```bash
# Linux/macOS
open site/index.html

# Windows
start site/index.html
```

### Serve Documentation Locally

**With live reload:**

```bash
make docs-serve
```

**Access:** http://127.0.0.1:8000

**Features:**

- Live reload on file changes
- Auto-rebuild on save
- Real-time preview

### Deploy Documentation

**To GitHub Pages:**

```bash
make docs-deploy
```

**Requirements:**

- Git repository
- GitHub Pages enabled
- Write access to repository

**What happens:**

1. Generates documentation from code
2. Builds MkDocs site
3. Pushes to `gh-pages` branch
4. Documentation live at: `https://little-did-I-know.github.io/Siglent-Oscilloscope/`

### Documentation Structure

```
docs/
├── index.md                 # Homepage
├── getting-started/         # Getting started guides
│   ├── installation.md
│   ├── quickstart.md
│   └── connection.md
├── user-guide/              # User documentation
│   ├── basic-usage.md
│   ├── waveform-capture.md
│   ├── measurements.md
│   ├── trigger-control.md
│   └── advanced-features.md
├── gui/                     # GUI documentation
│   ├── overview.md
│   ├── interface.md
│   ├── live-view.md
│   ├── visual-measurements.md
│   ├── fft-analysis.md
│   ├── protocol-decoding.md
│   └── vector-graphics.md
├── api/                     # API reference (auto-generated)
│   ├── oscilloscope.md
│   ├── channel.md
│   ├── trigger.md
│   └── gui.md
├── examples/                # Example code (auto-generated)
│   └── *.md
└── development/             # Development guides
    ├── building.md
    ├── structure.md
    └── testing.md
```

### Documentation Autodoc

**How it works:**

1. **mkdocstrings** - Extracts docstrings from Python code
2. **mkdocs-gen-files** - Dynamically generates markdown files
3. **Scripts** - Custom scripts generate example and API docs

**Example API documentation:**

Python code with docstrings:

```python
def get_waveform(self, channel: int) -> Waveform:
    """Get waveform data from specified channel.

    Args:
        channel: Channel number (1-4)

    Returns:
        Waveform object with data and metadata

    Raises:
        ValueError: If channel number is invalid
    """
    pass
```

Generated markdown:

```markdown
::: siglent.Oscilloscope.get_waveform
```

MkDocs renders this as formatted API documentation.

## Publishing

### Publish to TestPyPI

**Test upload:**

```bash
make publish-test
```

**Requirements:**

- TestPyPI account
- API token configured in `~/.pypirc`

**Verify:**

```bash
pip install -i https://test.pypi.org/simple/ Siglent-Oscilloscope
```

### Publish to PyPI

**Production release:**

```bash
make publish
```

**⚠️ Warning:** This publishes to production PyPI!

**Requirements:**

- PyPI account
- API token configured
- Write access to package

**Steps:**

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit changes
4. Create git tag: `git tag v0.3.0`
5. Push with tags: `git push --tags`
6. Clean: `make clean`
7. Build: `make build`
8. Publish: `make publish`

### PyPI Configuration

**Setup `~/.pypirc`:**

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-...  # Your PyPI API token

[testpypi]
username = __token__
password = pypi-...  # Your TestPyPI API token
```

**Security:**

- Use API tokens, not passwords
- Generate tokens at: https://pypi.org/manage/account/token/
- Limit token scope to specific projects

## Version Management

### Version Location

**Single source of truth:** `pyproject.toml`

```toml
[project]
version = "0.3.0"
```

**Also defined in:** `siglent/__init__.py`

```python
__version__ = "0.3.0"
```

**Check version:**

```bash
make version
# Output: Siglent-Oscilloscope v0.3.0
```

### Version Scheme

**Semantic Versioning (SemVer):**

- **Major.Minor.Patch** (e.g., `0.3.0`)
- **Major**: Breaking changes
- **Minor**: New features, backwards compatible
- **Patch**: Bug fixes, backwards compatible

**Development versions:**

- `0.3.0.dev1` - Development pre-release
- `0.3.0a1` - Alpha
- `0.3.0b1` - Beta
- `0.3.0rc1` - Release candidate

### Release Process

**1. Update version:**

```bash
# Edit pyproject.toml
version = "0.4.0"

# Edit siglent/__init__.py
__version__ = "0.4.0"
```

**2. Update changelog:**

```bash
# Edit CHANGELOG.md
## [0.4.0] - 2024-01-15
### Added
- New feature X
### Fixed
- Bug Y
```

**3. Commit and tag:**

```bash
git add pyproject.toml siglent/__init__.py CHANGELOG.md
git commit -m "Release v0.4.0"
git tag v0.4.0
git push origin main --tags
```

**4. Build and publish:**

```bash
make clean
make check         # Run all tests
make build         # Build packages
make publish       # Upload to PyPI
```

**5. Create GitHub release:**

- Go to: https://github.com/little-did-I-know/Siglent-Oscilloscope/releases
- Click "Create a new release"
- Select tag: `v0.4.0`
- Title: `Release 0.4.0`
- Description: Copy from CHANGELOG.md
- Attach: `dist/*.tar.gz` and `dist/*.whl`

## Continuous Integration

### GitHub Actions

**Automated workflows:**

- Run tests on push/PR
- Multiple Python versions
- Multiple operating systems
- Code coverage reporting
- Build validation

**Workflow files:**

```
.github/workflows/
├── test.yml           # Run tests
├── lint.yml           # Code quality
├── build.yml          # Build package
└── publish.yml        # Auto-publish on tag
```

### Local CI Simulation

**Run complete CI checks locally:**

```bash
make pre-pr
```

**Simulates:**

- All test suites
- Code formatting
- Linting
- Type checking
- Documentation build
- Package build

## Troubleshooting

### Build Failures

**Problem:** `ModuleNotFoundError` during build

**Solution:**

```bash
# Install build dependencies
pip install --upgrade build setuptools wheel
```

**Problem:** `twine check` fails

**Solution:**

```bash
# Check README syntax
pip install readme-renderer
python -c "import readme_renderer.rst; readme_renderer.rst.render(open('README.md').read())"
```

### Test Failures

**Problem:** Import errors in tests

**Solution:**

```bash
# Reinstall in editable mode
pip install -e ".[dev]"
```

**Problem:** GUI tests fail

**Solution:**

```bash
# Install GUI dependencies
pip install -e ".[gui]"

# Skip GUI tests if not needed
pytest tests/ -m "not gui"
```

### Documentation Build Failures

**Problem:** `mkdocs build` fails

**Solution:**

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Regenerate API docs
make docs-generate
```

**Problem:** Autodoc not finding modules

**Solution:**

```bash
# Ensure package is installed
pip install -e .

# Check mkdocs.yml configuration
# Verify plugins are installed
```

### Publishing Issues

**Problem:** `twine upload` authentication fails

**Solution:**

```bash
# Check ~/.pypirc configuration
# Regenerate API token at pypi.org
# Use __token__ as username
```

**Problem:** Package already exists

**Solution:**

```bash
# Increment version number
# Can't overwrite existing PyPI versions
```

## Development Workflows

### Daily Development

```bash
# 1. Pull latest changes
git pull

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes to code

# 4. Format code
make format

# 5. Run tests
make test

# 6. Commit changes
git add .
git commit -m "Add feature X"

# 7. Push branch
git push origin feature/my-feature

# 8. Create pull request
```

### Before Committing

```bash
# Format code
make format

# Run linting
make lint

# Run tests
make test

# Or run all at once
make check
```

### Before Creating PR

```bash
# Run comprehensive checks
make pre-pr

# Or with auto-fix
make pre-pr-fix
```

### Updating Dependencies

**Update all dependencies:**

```bash
pip install --upgrade -e ".[all,dev]"
```

**Update specific dependency:**

```bash
pip install --upgrade numpy
```

**Freeze dependencies:**

```bash
pip freeze > requirements.txt
```

## Quick Reference

### Common Make Commands

| Command             | Description                   |
| ------------------- | ----------------------------- |
| `make help`         | Show all available commands   |
| `make dev-setup`    | Complete development setup    |
| `make install`      | Install package (editable)    |
| `make install-all`  | Install with all dependencies |
| `make test`         | Run tests                     |
| `make test-cov`     | Run tests with coverage       |
| `make lint`         | Run linting checks            |
| `make format`       | Auto-format code              |
| `make clean`        | Remove build artifacts        |
| `make build`        | Build distribution packages   |
| `make check`        | Run all checks                |
| `make pre-pr`       | Pre-PR validation             |
| `make docs`         | Build documentation           |
| `make docs-serve`   | Serve docs locally            |
| `make publish-test` | Publish to TestPyPI           |
| `make publish`      | Publish to PyPI               |

### Build Artifacts

| Path             | Description                 |
| ---------------- | --------------------------- |
| `build/`         | Build directory (temporary) |
| `dist/`          | Distribution packages       |
| `*.egg-info/`    | Package metadata            |
| `site/`          | Built documentation         |
| `htmlcov/`       | Coverage report             |
| `.pytest_cache/` | Pytest cache                |

### Configuration Files

| File                      | Purpose                           |
| ------------------------- | --------------------------------- |
| `pyproject.toml`          | Package metadata and build config |
| `Makefile`                | Development task automation       |
| `mkdocs.yml`              | Documentation configuration       |
| `.pre-commit-config.yaml` | Pre-commit hooks                  |
| `pytest.ini`              | Pytest configuration              |

## Next Steps

- [Project Structure](structure.md) - Understand the codebase organization
- [Testing Guide](testing.md) - Learn about the test suite
- [Contributing Guidelines](../CONTRIBUTING.md) - How to contribute
- [Code of Conduct](../CODE_OF_CONDUCT.md) - Community guidelines
