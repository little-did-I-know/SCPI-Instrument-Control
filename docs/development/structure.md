# Project Structure

This guide explains the organization of the Siglent Oscilloscope Control library codebase, making it easier to navigate, understand, and contribute.

## Overview

The project follows a standard Python package structure with clear separation of concerns:

```
Siglent-Oscilloscope/
├── siglent/              # Main package (core library)
├── tests/                # Test suite
├── docs/                 # Documentation
├── examples/             # Usage examples
├── scripts/              # Development and automation scripts
└── Configuration files   # Build, test, and tool configs
```

## Top-Level Structure

### Source Code

**`siglent/`** - Main Python package
- Core oscilloscope control library
- GUI application
- Protocol decoders
- Utilities and helpers

**`tests/`** - Test suite
- Unit tests
- Integration tests
- Test fixtures and utilities

**`examples/`** - Example scripts
- Basic usage examples
- Advanced feature demonstrations
- GUI usage examples

### Documentation

**`docs/`** - Documentation source
- User guides
- API reference (auto-generated)
- Development guides
- Markdown source files

**`site/`** - Built documentation (generated)
- Static HTML output
- Not version controlled

### Scripts

**`scripts/`** - Development utilities
- Documentation generation
- Pre-commit hooks
- Testing helpers
- Build automation

### Configuration

**Root directory:**
- `pyproject.toml` - Package metadata and build config
- `Makefile` - Task automation
- `mkdocs.yml` - Documentation configuration
- `.pre-commit-config.yaml` - Pre-commit hooks
- `README.md` - Project README
- `CHANGELOG.md` - Version history
- `LICENSE` - MIT License
- `CONTRIBUTING.md` - Contribution guidelines

## Package Structure (`siglent/`)

### Core Modules

The main package is organized by functionality:

```
siglent/
├── __init__.py                   # Package initialization, version
├── oscilloscope.py               # Main Oscilloscope class
├── channel.py                    # Channel control
├── trigger.py                    # Trigger configuration
├── measurement.py                # Measurement functionality
├── measurement_config.py         # Measurement configuration
├── waveform.py                   # Waveform data structures
├── math_channel.py               # Math channel operations
├── reference_waveform.py         # Reference waveform management
├── screen_capture.py             # Screenshot capture
├── scpi_commands.py              # SCPI command definitions
├── models.py                     # Data models and types
├── exceptions.py                 # Custom exceptions
├── analysis.py                   # Waveform analysis tools
├── automation.py                 # Automation helpers
├── vector_graphics.py            # Vector graphics (XY mode)
└── protocol_decode.py            # Protocol decoding utilities
```

### Connection Layer

**`siglent/connection/`** - Connection management

```
connection/
├── __init__.py           # Connection exports
├── base.py               # Base connection interface
├── socket.py             # TCP/IP socket connection
└── mock.py               # Mock connection for testing
```

**Key classes:**
- `Connection` - Abstract base class
- `SocketConnection` - Real TCP/IP implementation
- `MockConnection` - Testing/simulation

**Responsibilities:**
- Network communication
- SCPI command sending/receiving
- Connection lifecycle management
- Error handling and retries

### Protocol Decoders

**`siglent/protocol_decoders/`** - Digital protocol decoding

```
protocol_decoders/
├── __init__.py           # Decoder exports
├── i2c_decoder.py        # I2C protocol decoder
├── spi_decoder.py        # SPI protocol decoder
└── uart_decoder.py       # UART protocol decoder
```

**Features:**
- Decode captured waveforms
- Extract protocol data
- Error detection
- Timing analysis

### GUI Application

**`siglent/gui/`** - PyQt6 graphical interface

```
gui/
├── __init__.py                      # GUI package init
├── app.py                           # Application entry point
├── main_window.py                   # Main window class
├── connection_manager.py            # Connection dialog
├── vnc_window.py                    # VNC viewer window
├── live_view_worker.py              # Background live view worker
├── waveform_capture_worker.py       # Background capture worker
├── utils/
│   └── validators.py                # Input validators
└── widgets/                         # UI components
    ├── __init__.py
    ├── channel_control.py           # Channel controls
    ├── trigger_control.py           # Trigger controls
    ├── timebase_control.py          # Timebase controls
    ├── measurement_panel.py         # Measurements display
    ├── cursor_panel.py              # Cursor controls
    ├── math_panel.py                # Math channel controls
    ├── reference_panel.py           # Reference waveforms
    ├── protocol_decode_panel.py     # Protocol decoder UI
    ├── fft_display.py               # FFT analysis display
    ├── visual_measurement_panel.py  # Visual markers
    ├── vector_graphics_panel.py     # Vector graphics UI
    ├── waveform_display.py          # Waveform plot (matplotlib)
    ├── waveform_display_pg.py       # Waveform plot (PyQtGraph)
    ├── terminal_widget.py           # SCPI terminal
    ├── scope_web_view.py            # Web view widget
    ├── error_dialog.py              # Error display
    ├── measurement_marker.py        # Measurement marker base
    └── measurement_markers/         # Specific marker types
        ├── __init__.py
        ├── voltage_marker.py        # Voltage markers
        ├── timing_marker.py         # Time markers
        └── frequency_marker.py      # Frequency markers
```

**Architecture:**
- **MVC pattern** - Separation of concerns
- **Worker threads** - Background tasks (live view, capture)
- **Signal/Slot** - PyQt event system
- **Widget composition** - Reusable UI components

**Entry point:**
```bash
siglent-gui
# Defined in pyproject.toml:
# siglent-gui = "siglent.gui.app:main"
```

## Test Suite (`tests/`)

### Test Organization

```
tests/
├── test_oscilloscope.py              # Oscilloscope class tests
├── test_channel.py                   # Channel tests
├── test_trigger.py                   # Trigger tests
├── test_measurement.py               # Measurement tests
├── test_waveform.py                  # Waveform tests
├── test_connection.py                # Connection tests
├── test_protocol_decoders.py         # Protocol decoder tests
├── test_analysis.py                  # Analysis tools tests
├── test_exceptions.py                # Exception handling tests
├── test_gui/                         # GUI tests
│   ├── test_main_window.py
│   ├── test_widgets.py
│   └── test_live_view.py
├── conftest.py                       # Pytest fixtures
└── fixtures/                         # Test data
    ├── sample_waveforms.npz
    └── mock_responses.json
```

### Test Categories

**Unit Tests:**
- Test individual functions/classes
- Mock external dependencies
- Fast execution
- High coverage target: >90%

**Integration Tests:**
- Test component interaction
- Use MockConnection
- Verify protocol correctness
- Coverage target: >80%

**GUI Tests:**
- Test UI components
- Marked with `@pytest.mark.gui`
- Require PyQt6
- Coverage target: >70%

**Hardware Tests:**
- Test with real oscilloscope
- Marked with `@pytest.mark.hardware`
- Skip by default (CI/CD)
- Manual execution only

### Running Tests

```bash
# All tests
make test

# Skip hardware tests
pytest -m "not hardware"

# Only GUI tests
pytest -m gui

# Specific test file
pytest tests/test_oscilloscope.py

# With coverage
make test-cov
```

## Documentation (`docs/`)

### Structure

```
docs/
├── index.md                          # Homepage
├── getting-started/                  # Getting started guides
│   ├── installation.md               # Installation instructions
│   ├── quickstart.md                 # Quick start guide
│   └── connection.md                 # Connection setup
├── user-guide/                       # User documentation
│   ├── basic-usage.md                # Basic usage
│   ├── waveform-capture.md           # Waveform capture
│   ├── measurements.md               # Measurements
│   ├── trigger-control.md            # Trigger control
│   └── advanced-features.md          # Advanced features
├── gui/                              # GUI documentation
│   ├── overview.md                   # GUI overview
│   ├── interface.md                  # Interface guide
│   ├── live-view.md                  # Live view
│   ├── visual-measurements.md        # Visual measurements
│   ├── fft-analysis.md               # FFT analysis
│   ├── protocol-decoding.md          # Protocol decoding
│   └── vector-graphics.md            # Vector graphics
├── api/                              # API reference (auto-generated)
│   ├── oscilloscope.md               # Oscilloscope class
│   ├── channel.md                    # Channel class
│   ├── trigger.md                    # Trigger class
│   ├── measurement.md                # Measurement class
│   ├── waveform.md                   # Waveform class
│   └── gui.md                        # GUI module
├── examples/                         # Examples (auto-generated)
│   └── *.md                          # Generated from examples/
└── development/                      # Development docs
    ├── building.md                   # Build guide
    ├── structure.md                  # This file
    └── testing.md                    # Testing guide
```

### Auto-generated Documentation

**API Reference:**
- Generated from Python docstrings
- Uses `mkdocstrings` plugin
- Renders type hints, parameters, examples
- Automatically updates with code

**Examples:**
- Generated from `examples/` directory
- Uses `mkdocs-gen-files`
- Includes code with syntax highlighting
- Categorized by topic

**Generation scripts:**
```bash
scripts/docs/generate_api_stubs.py      # API reference
scripts/docs/generate_examples_docs.py  # Examples
```

**Build documentation:**
```bash
make docs-generate  # Generate auto-docs
make docs           # Build full site
make docs-serve     # Serve locally
```

## Examples (`examples/`)

### Organization

```
examples/
├── basic/                            # Basic usage
│   ├── connect.py                    # Connect to scope
│   ├── capture_waveform.py           # Capture waveform
│   └── simple_measurement.py         # Basic measurement
├── advanced/                         # Advanced features
│   ├── batch_capture.py              # Batch capture
│   ├── fft_analysis.py               # FFT analysis
│   ├── protocol_decode_i2c.py        # I2C decoding
│   └── automation.py                 # Automation example
├── gui/                              # GUI examples
│   ├── launch_gui.py                 # Launch GUI
│   └── custom_widget.py              # Custom widget
└── README.md                         # Examples overview
```

### Example Format

Each example includes:
- **Docstring** - Purpose and usage
- **Requirements** - Dependencies
- **Code** - Well-commented
- **Output** - Expected results

**Template:**
```python
"""
Example: Capture Waveform

Demonstrates how to connect to oscilloscope and capture a waveform.

Requirements:
- Siglent oscilloscope connected to network
- IP address configured

Usage:
    python capture_waveform.py
"""

from siglent import Oscilloscope

# Connect to oscilloscope
with Oscilloscope('192.168.1.100') as scope:
    # Enable channel
    scope.channel1.enabled = True

    # Capture waveform
    waveform = scope.get_waveform(1)

    # Print information
    print(f"Captured {len(waveform.data)} samples")
```

## Scripts (`scripts/`)

### Organization

```
scripts/
├── docs/                             # Documentation generation
│   ├── generate_api_stubs.py         # Generate API docs
│   ├── generate_examples_docs.py     # Generate example docs
│   ├── docs_config.yaml              # Doc generation config
│   └── __init__.py
├── hooks/                            # Git hooks
│   ├── validate_docstrings.py        # Docstring validator
│   └── __init__.py
├── pre_pr_check.py                   # Pre-PR validation script
├── pre_pr_check.sh                   # Shell version
├── manual_test_*.py                  # Manual testing scripts
├── run_debug.py                      # Debug launcher
├── run_debug.bat                     # Windows debug launcher
└── README.md                         # Scripts documentation
```

### Key Scripts

**Documentation:**
- `generate_api_stubs.py` - Creates API reference from docstrings
- `generate_examples_docs.py` - Creates example documentation

**Pre-commit:**
- `validate_docstrings.py` - Ensures docstring quality
- Runs automatically on commit

**Testing:**
- `manual_test_live_view.py` - Test live view performance
- `manual_test_pyqtgraph.py` - Test PyQtGraph integration
- `manual_test_waveform_display.py` - Test waveform display

**Validation:**
- `pre_pr_check.py` - Comprehensive pre-PR checks
- Runs: formatting, linting, tests, docs build

## Configuration Files

### Package Configuration

**`pyproject.toml`** - PEP 621 package metadata
- Package name, version, description
- Dependencies (core and optional)
- Entry points (scripts)
- Build system configuration
- Tool configurations (black, pytest)

**Example:**
```toml
[project]
name = "Siglent-Oscilloscope"
version = "0.3.0"
dependencies = ["numpy>=1.24.0", ...]

[project.optional-dependencies]
gui = ["PyQt6>=6.6.0", ...]

[project.scripts]
siglent-gui = "siglent.gui.app:main"
```

### Development Tools

**`Makefile`** - Task automation
- `make test` - Run tests
- `make build` - Build package
- `make docs` - Build documentation
- `make format` - Format code
- See [Building Guide](building.md) for all commands

**`.pre-commit-config.yaml`** - Pre-commit hooks
- Black formatting
- Flake8 linting
- Trailing whitespace
- End-of-file fixing
- Custom docstring validation

**`.editorconfig`** - Editor configuration
- Indent style (spaces)
- Indent size (4)
- End of line (LF)
- Character encoding (UTF-8)

### Testing

**`pytest.ini`** - Pytest configuration (in pyproject.toml)
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "hardware: tests requiring hardware",
    "gui: tests requiring PyQt6"
]
```

**`.coverage`** - Coverage data (generated)

**`codecov.yml`** - Codecov configuration
- Coverage targets
- Ignore patterns
- Comment behavior

### Documentation

**`mkdocs.yml`** - MkDocs configuration
- Site name and URL
- Theme (Material)
- Plugins (mkdocstrings, etc.)
- Navigation structure
- See [Building Guide](building.md#documentation)

**`.readthedocs.yml`** - Read the Docs config
- Python version
- Build requirements
- Documentation format

### Code Quality

**`.docstring-validation.yaml`** - Docstring rules
- Required sections
- Format requirements
- Validation rules

**`flake8` config** - In pyproject.toml
```toml
[tool.black]
line-length = 200
```

### Git

**`.gitignore`** - Ignored files
- `__pycache__/`, `*.pyc`
- `build/`, `dist/`, `*.egg-info/`
- `.venv/`, `venv/`
- `.coverage`, `htmlcov/`
- IDE files (`.idea/`, `.vscode/`)

**`.github/workflows/`** - GitHub Actions
- `test.yml` - Run tests on push/PR
- `lint.yml` - Code quality checks
- `build.yml` - Build package
- `publish.yml` - Publish to PyPI

## Module Dependencies

### Dependency Graph

```
oscilloscope.py
├── connection/socket.py
├── channel.py
│   └── scpi_commands.py
├── trigger.py
│   └── scpi_commands.py
├── measurement.py
│   ├── measurement_config.py
│   └── waveform.py
├── waveform.py
│   └── models.py
├── math_channel.py
├── reference_waveform.py
├── screen_capture.py
├── protocol_decode.py
│   └── protocol_decoders/
│       ├── i2c_decoder.py
│       ├── spi_decoder.py
│       └── uart_decoder.py
├── analysis.py
│   └── waveform.py
├── automation.py
│   └── oscilloscope.py
└── vector_graphics.py
    └── waveform.py
```

### Import Hierarchy

**Level 1** - Core utilities (no internal deps)
- `models.py`
- `exceptions.py`
- `scpi_commands.py`

**Level 2** - Connection and data
- `connection/`
- `waveform.py`
- `measurement_config.py`

**Level 3** - Components
- `channel.py`
- `trigger.py`
- `measurement.py`
- `math_channel.py`

**Level 4** - Main interface
- `oscilloscope.py`

**Level 5** - Extensions
- `analysis.py`
- `automation.py`
- `protocol_decode.py`
- `vector_graphics.py`

**Level 6** - GUI
- `gui/` package

## Design Patterns

### Main API

**Facade Pattern:**
- `Oscilloscope` class provides simple interface
- Hides complexity of SCPI protocol
- Aggregates channel, trigger, measurement classes

**Property Pattern:**
```python
class Channel:
    @property
    def voltage_scale(self) -> float:
        """Get voltage scale."""
        return self._get_voltage_scale()

    @voltage_scale.setter
    def voltage_scale(self, value: float):
        """Set voltage scale."""
        self._set_voltage_scale(value)
```

**Context Manager:**
```python
with Oscilloscope('192.168.1.100') as scope:
    # Use scope
    pass
# Automatically closed
```

### GUI Architecture

**Model-View-Controller (MVC):**
- **Model**: `siglent.oscilloscope` (core library)
- **View**: `gui/widgets/` (Qt widgets)
- **Controller**: `gui/main_window.py` (coordination)

**Observer Pattern:**
- Qt signals/slots for event handling
- Decoupled components
- Reactive updates

**Worker Thread Pattern:**
- Background tasks don't block UI
- `LiveViewWorker` - Continuous capture
- `WaveformCaptureWorker` - Single capture
- Qt `QThread` based

### Testing

**Mock Object Pattern:**
- `MockConnection` simulates oscilloscope
- Predictable responses
- No hardware required

**Fixture Pattern:**
- pytest fixtures for setup/teardown
- Reusable test data
- Shared configurations

**Parametrized Tests:**
```python
@pytest.mark.parametrize("channel", [1, 2, 3, 4])
def test_all_channels(channel):
    # Test each channel
    pass
```

## Code Style

### Formatting

**Black** - Code formatter
- Line length: 200 characters
- Automatic formatting
- Consistent style

**Run:**
```bash
make format
```

### Linting

**Flake8** - Style checker
- PEP 8 compliance
- Complexity limits
- Import order

**Run:**
```bash
make lint
```

### Type Hints

**Required:**
- All public functions
- Class attributes
- Return types

**Example:**
```python
def get_waveform(self, channel: int) -> Waveform:
    """Get waveform from channel."""
    pass
```

**Type checking:**
```bash
mypy siglent/
```

### Docstrings

**Google style:**
```python
def function(arg1: str, arg2: int) -> bool:
    """Short description.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When condition occurs

    Example:
        >>> function("test", 42)
        True
    """
    pass
```

**Required sections:**
- Short description
- Args (if any)
- Returns (if not None)
- Raises (if any)

## Adding New Features

### Process

1. **Design**
   - Define interface
   - Consider existing patterns
   - Document API

2. **Implementation**
   - Follow project structure
   - Add to appropriate module
   - Maintain code style

3. **Testing**
   - Write unit tests
   - Add integration tests
   - Update test fixtures

4. **Documentation**
   - Add docstrings
   - Update user guide
   - Create examples

5. **Review**
   - Run `make check`
   - Run `make pre-pr`
   - Create pull request

### Where to Add

**New SCPI command:**
- Add to `scpi_commands.py`
- Add method to appropriate class

**New measurement:**
- Add to `measurement.py`
- Add to `measurement_config.py`
- Update GUI if needed

**New protocol decoder:**
- Create file in `protocol_decoders/`
- Add to `__init__.py`
- Create tests

**New GUI widget:**
- Create file in `gui/widgets/`
- Add to `main_window.py`
- Create tests in `tests/test_gui/`

**New analysis tool:**
- Add to `analysis.py`
- Add tests
- Add example

## Directory Conventions

### Naming

**Modules:** `lowercase_with_underscores.py`
- `oscilloscope.py`
- `protocol_decode.py`

**Classes:** `PascalCase`
- `Oscilloscope`
- `Channel`
- `WaveformData`

**Functions/Methods:** `lowercase_with_underscores`
- `get_waveform()`
- `enable_channel()`

**Constants:** `UPPERCASE_WITH_UNDERSCORES`
- `DEFAULT_TIMEOUT`
- `MAX_CHANNELS`

**Private:** `_leading_underscore`
- `_send_command()`
- `_internal_state`

### File Organization

**One class per file:**
- Preferred for main classes
- Exception: Related small classes

**Group related functions:**
- Utilities in one module
- Helpers together

**Separate concerns:**
- Data models vs logic
- UI vs business logic

## Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `siglent/oscilloscope.py` | Main API entry point |
| `siglent/connection/socket.py` | Network communication |
| `siglent/gui/main_window.py` | GUI main window |
| `tests/conftest.py` | Test fixtures |
| `pyproject.toml` | Package configuration |
| `Makefile` | Development tasks |
| `mkdocs.yml` | Documentation config |

### Important Directories

| Directory | Purpose |
|-----------|---------|
| `siglent/` | Main package code |
| `siglent/gui/` | GUI application |
| `siglent/connection/` | Connection layer |
| `siglent/protocol_decoders/` | Protocol decoders |
| `tests/` | Test suite |
| `docs/` | Documentation source |
| `examples/` | Usage examples |
| `scripts/` | Build and dev scripts |

### Entry Points

| Command | Module | Function |
|---------|--------|----------|
| `siglent-gui` | `siglent.gui.app` | `main()` |

## Next Steps

- [Building Guide](building.md) - Build and package the project
- [Testing Guide](testing.md) - Learn about testing
- [Contributing](../CONTRIBUTING.md) - Contribution guidelines
- [API Reference](../api/oscilloscope.md) - Detailed API docs
