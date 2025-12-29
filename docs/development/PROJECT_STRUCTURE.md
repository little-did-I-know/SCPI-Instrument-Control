# Project Structure

This document describes the organization of the Siglent Oscilloscope Control project.

## Directory Layout

```
Siglent/
├── siglent/                 # Main package (installed)
│   ├── __init__.py
│   ├── oscilloscope.py     # Main API
│   ├── channel.py          # Channel control
│   ├── trigger.py          # Trigger settings
│   ├── waveform.py         # Waveform data structures
│   ├── measurement.py      # Measurement functions
│   ├── connection/         # Connection backends
│   ├── gui/                # GUI application
│   └── protocol_decoders/  # Protocol decoders
│
├── tests/                   # Test suite (not installed)
│   ├── test_imports.py
│   ├── test_gui_initialization.py
│   ├── test_protocol_decoders.py
│   └── ...
│
├── scripts/                 # Development utilities (not installed)
│   ├── run_debug.py        # Debug GUI launcher
│   ├── run_debug.bat       # Windows launcher
│   └── capture_screenshots.py
│
├── docs/                    # Documentation
│   ├── images/             # Screenshots (installed)
│   ├── development/        # Dev docs (not installed)
│   │   ├── BUILD.md
│   │   ├── PYPI_DEPLOYMENT.md
│   │   └── PROJECT_STRUCTURE.md
│   ├── VISUAL_MEASUREMENTS.md  # User guide (installed)
│   ├── SCREENSHOT_GUIDE.md     # Development guide
│   ├── CONTRIBUTING.md         # Contribution guide
│   ├── SECURITY.md             # Security policy
│   └── SDS800XHD_Series_ProgrammingGuide_EN11G.pdf  # Scope manual
│
├── examples/                # Example scripts (installed)
│   ├── basic_usage.py
│   ├── measurements.py
│   ├── live_plot.py
│   └── ...
│
├── dist/                    # Built packages (git ignored)
│   ├── siglent_oscilloscope-0.2.0.tar.gz
│   └── siglent_oscilloscope-0.2.0-py3-none-any.whl
│
├── README.md                # Main documentation (installed)
├── CHANGELOG.md             # Version history (installed)
├── LICENSE                  # MIT license (installed)
├── pyproject.toml           # Package metadata
└── MANIFEST.in              # Package inclusion rules
```

## What Gets Installed

When users install the package via `pip install Siglent-Oscilloscope`, they get:

**Code:**
- `siglent/` - Complete package with all modules
- `examples/` - Example scripts to get started

**Documentation:**
- `README.md` - Main documentation
- `CHANGELOG.md` - Version history
- `docs/VISUAL_MEASUREMENTS.md` - Visual measurement guide
- `docs/images/` - GUI screenshots
- `docs/SDS800XHD_Series_ProgrammingGuide_EN11G.pdf` - Scope manual

**Not Installed:**
- `tests/` - Test suite (for development only)
- `scripts/` - Development utilities
- `docs/development/` - Build and deployment documentation
- `docs/CONTRIBUTING.md`, `docs/SECURITY.md` - Development guides

## Directory Purposes

### siglent/
The main package containing all the production code. This is what gets imported when users run `import siglent`.

**Key modules:**
- `oscilloscope.py` - Main `Oscilloscope` class
- `channel.py` - Channel configuration
- `trigger.py` - Trigger settings
- `waveform.py` - Waveform data handling
- `measurement.py` - Measurement functions
- `gui/` - PyQt6 GUI application
- `connection/` - Connection backends (socket, mock)
- `protocol_decoders/` - I2C, SPI, UART decoders

### tests/
Automated test suite using pytest. Run with `pytest tests/` from the project root.

**Test categories:**
- Import tests - Verify all modules can be imported
- GUI initialization tests - Catch AttributeError and widget creation issues
- Protocol decoder tests - Verify decoder functionality
- Math operations tests - Test waveform math functions
- Live view tests - Test real-time plotting

See `tests/README.md` for testing instructions.

### scripts/
Development and debugging utilities. Not installed with the package.

**Scripts:**
- `run_debug.py` - Launch GUI with debug logging
- `run_debug.bat` - Windows convenience launcher
- `capture_screenshots.py` - Automated screenshot capture for docs

See `scripts/README.md` for details.

### docs/
Project documentation, split into user-facing and developer-facing content.

**User Documentation (installed):**
- `VISUAL_MEASUREMENTS.md` - How to use visual measurement markers
- `images/` - GUI screenshots for README
- `SDS800XHD_Series_ProgrammingGuide_EN11G.pdf` - Oscilloscope reference

**Developer Documentation (not installed):**
- `development/BUILD.md` - How to build and package
- `development/PYPI_DEPLOYMENT.md` - PyPI deployment guide
- `development/PROJECT_STRUCTURE.md` - This file
- `CONTRIBUTING.md` - How to contribute
- `SECURITY.md` - Security policy
- `SCREENSHOT_GUIDE.md` - Screenshot capture guide

### examples/
Example scripts demonstrating package features. These are installed with the package so users can easily get started.

**Examples:**
- `basic_usage.py` - Connect and capture waveforms
- `measurements.py` - Automated measurements
- `live_plot.py` - Real-time waveform display
- `batch_capture.py` - Capture multiple waveforms
- And more...

## Build Artifacts

### dist/
Contains built packages created by `python -m build`:
- `.tar.gz` - Source distribution
- `.whl` - Wheel (binary) distribution

These are uploaded to PyPI for distribution.

### Siglent_Oscilloscope.egg-info/
Metadata directory created during build. Git ignored.

## Version Control

### .gitignore
Excludes:
- Python cache files (`__pycache__`, `*.pyc`)
- Virtual environments (`.venv/`, `venv/`)
- Build artifacts (`dist/`, `build/`, `*.egg-info`)
- IDE files (`.vscode/`, `.idea/`)
- Test outputs (`.pytest_cache/`, `.coverage`)
- Development data files (`*.log`, `*.dat`, `*.csv`)

### .git/
Git repository data. The main branch is `main`.

## Package Configuration

### pyproject.toml
Modern Python package metadata and build configuration:
- Package name, version, description
- Dependencies (core and optional `[gui]` extras)
- Entry points (`siglent-gui` command)
- Build system (setuptools)

### MANIFEST.in
Controls what files are included in source distributions:
- **Include:** README, CHANGELOG, LICENSE, docs, examples
- **Exclude:** tests, scripts, development docs, build artifacts

## Development Workflow

1. **Make changes** to code in `siglent/`
2. **Add tests** in `tests/`
3. **Run tests:** `pytest tests/`
4. **Update docs** in `docs/` and `README.md`
5. **Update `CHANGELOG.md`** with changes
6. **Build package:** `python -m build`
7. **Check package:** `twine check dist/*`
8. **Test install:**
   - Bash/WSL: `pip install dist/*.whl`
   - PowerShell: run `python -m pip install --upgrade pip` first, then `python -m pip install (Get-ChildItem dist\*.whl)` so globbing resolves the wheel path
   - cmd.exe: `for %f in (dist\*.whl) do python -m pip install --upgrade pip "%f"`
9. **Deploy to PyPI:** `twine upload dist/*`

See `docs/development/BUILD.md` and `docs/development/PYPI_DEPLOYMENT.md` for detailed instructions.

## Migration from Old Structure

The project was reorganized in v0.2.0 to follow Python packaging best practices:

**Changes:**
- Created `tests/` directory for all test files
- Created `scripts/` directory for development utilities
- Consolidated all docs into `docs/` directory
- Moved build/deployment docs to `docs/development/`
- Updated MANIFEST.in to exclude development-only files
- Updated .gitignore for cleaner repository

This structure matches the conventions used by most PyPI packages and makes it clear what's for users vs. developers.
