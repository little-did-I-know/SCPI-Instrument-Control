# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-01-04

### Added

**Automated Test Report Generation** 📊
- **Installation**: `pip install "Siglent-Oscilloscope[report-generator]"`
- **PDF and Markdown Report Generators**
  - Professional publication-ready reports with waveform plots and analysis
  - Comprehensive metadata tracking (test ID, operator, timestamp, scope model)
  - Multiple output formats (PDF via ReportLab, Markdown with embedded plots)
  - Automatic file organization and asset management

- **Signal Type Detection** (`siglent/report_generator/utils/waveform_analyzer.py`)
  - Automatic waveform classification using FFT harmonic analysis
  - Detects 9 signal types: sine, square, triangle, sawtooth, pulse, DC, noise, complex, unknown
  - Confidence scoring for classification accuracy
  - THD (Total Harmonic Distortion) calculation for waveform quality assessment
  - Pattern matching algorithms for periodic signal identification:
    - Square waves: odd harmonics at 1/n amplitude ratio
    - Triangle waves: odd harmonics at 1/n² amplitude ratio
    - Sawtooth waves: all harmonics at 1/n amplitude ratio
  - Signal type displayed in both PDF and Markdown reports with confidence percentage
  - Added `SignalType` constants class for standardized type identification

- **Enhanced Waveform Statistics** (`siglent/report_generator/models/report_data.py`)
  - Comprehensive signal analysis with 25+ measurement parameters
  - Amplitude measurements: Vmax, Vmin, Vpp, VRMS, Vmean, DC offset
  - Frequency and timing: frequency, period, rise time, fall time, pulse width, duty cycle
  - Quality metrics: SNR (Signal-to-Noise Ratio), THD, noise level, overshoot, undershoot, jitter
  - Automatic statistics calculation via `WaveformData.analyze()` method
  - Smart unit formatting with SI prefixes (mV, µs, kHz, etc.)
  - Statistics integration in PDF and Markdown report generators

- **Plateau Stability Analysis** (Optional Feature)
  - Measures noise on high and low plateaus for periodic signals
  - Uses run-length encoding to identify flat signal regions
  - Analyzes middle 60% of each plateau to exclude edge transitions
  - Reports three metrics:
    - Plateau High Noise: Standard deviation on high-level plateaus
    - Plateau Low Noise: Standard deviation on low-level plateaus
    - Plateau Stability: Average noise across all plateaus
  - User-configurable via Report Options dialog checkbox
  - Auto-applies to pulse, square, triangle, sawtooth, and sine waves
  - Helpful for power supply ripple, logic level stability, and signal quality testing

- **LLM Model Detection Feature** (`siglent/report_generator/widgets/llm_settings_dialog.py`)
  - "Detect Models" button in Ollama and LM Studio configuration tabs
  - Automatically queries server for available models and populates dropdown
  - Changed model input from text field to editable combo box
  - Preserves previously selected model after detection
  - User-friendly error messages with troubleshooting steps
  - Shows model count and lists detected models
  - Leverages existing `LLMClient.get_available_models()` API
  - Works with both Ollama Python SDK and OpenAI-compatible endpoints

- **Report Options Dialog** (`siglent/report_generator/widgets/report_options_dialog.py`)
  - New checkbox: "Plateau Stability Analysis (Advanced)"
  - Tooltip explains feature usage and applicability
  - Settings persist with report templates
  - Integrated with `ReportOptions` model

### Changed - Report Generator Features

- **PDF Generation Progress Tracking** (`siglent/report_generator/generators/pdf_generator.py`)
  - Enhanced with granular waveform-level progress updates
  - Progress now updates for each waveform being processed: 20%, 25%, 30%, ..., 80%
  - Prevents freezing appearance during matplotlib plot generation
  - Progress callback shows current operation: "Processing section X/Y", "Rendering waveform Z"
  - Smooth progression instead of jumping from 20% to 100%
  - Integrated with `QProgressDialog` in GUI for visual feedback

- **Unicode Character Normalization** (`siglent/report_generator/generators/pdf_generator.py`)
  - Comprehensive character mapping for AI-generated text compatibility
  - Handles 30+ Unicode characters that ReportLab can't render:
    - Smart quotes (U+201C, U+201D, U+2018, U+2019) → regular quotes
    - Em-dash (U+2014) and en-dash (U+2013) → hyphens
    - Bullets (U+2022) → asterisks
    - Ellipsis (U+2026) → three dots
    - Math symbols: ≤→<=, ≥→>=, ≠→!=, ×→x, ÷→/
    - Degree symbols: °→deg, ℃→C, ℉→F
    - Non-breaking spaces and special formatting characters → regular space
  - Applied to all AI-generated text fields: executive summary, AI insights, AI summary
  - Prevents empty boxes, question marks, or missing characters in PDFs
  - Maintains readability while ensuring PDF compatibility

- **Waveform Statistics Display** (PDF and Markdown Generators)
  - Statistics tables now include signal type with confidence
  - Plateau stability metrics shown when enabled and applicable
  - Enhanced formatting with proper units and precision
  - Color-coded headers and organized metric grouping in PDFs
  - Responsive table layout that adapts to content

### Fixed - Report Generator Features

- **AI-Generated Text Rendering in PDFs**
  - Fixed special Unicode characters not rendering (showing as boxes/question marks)
  - Root cause: LLMs generate smart quotes, bullets, and math symbols that ReportLab can't handle
  - Solution: Comprehensive character normalization before PDF generation
  - Now handles text from Claude, GPT, Llama, and other LLMs correctly

- **Progress Bar Freezing During Plot Generation**
  - Fixed progress bar appearing to freeze at 20% during PDF generation
  - Root cause: No progress updates during slow matplotlib plot rendering
  - Solution: Track waveforms across sections and report per-waveform progress
  - Users now see smooth progression throughout the entire generation process

### Technical Improvements - Report Generator

- **FFT-Based Signal Analysis**
  - NumPy FFT with harmonic ratio analysis for signal classification
  - Autocorrelation for period detection in non-periodic signals
  - Robust against noise with configurable confidence thresholds
  - Optimized for real-world oscilloscope waveforms

- **Extensible Waveform Analyzer**
  - Static methods for modular analysis capabilities
  - Separation of detection, measurement, and formatting logic
  - Easy to add new signal types or analysis algorithms
  - Comprehensive docstrings with algorithm explanations

- **Report Options Architecture**
  - `ReportOptions` dataclass for type-safe configuration
  - Passed through generator chain to all analysis functions
  - Enables feature flags for optional expensive computations
  - JSON-serializable for template saving

- **Model Detection Integration**
  - Reuses existing LLMClient infrastructure
  - Handles both Ollama native API and OpenAI-compatible endpoints
  - Graceful error handling with actionable user feedback
  - No duplicate code between Ollama and LM Studio detection

**Power Supply - Now Stable** ✅
- Power supply support graduated from BETA to stable
- API is now considered production-ready
- Removed experimental warnings and beta tags
- Full support for SPD3303X series power supplies
- Installation: Standard package or `pip install "Siglent-Oscilloscope[power-supply-beta]"` (alias maintained)

**Pre-Commit Checks and Code Coverage** 🔍
- New `make pre-commit-branch` target for lightweight branch commit validation
  - Code formatting checks (Black, Flake8)
  - Fast parallel test execution
  - ~1 minute validation for rapid development
- Enhanced `make pre-pr` with codecov integration
  - Full test suite with coverage reporting
  - Automatic coverage upload to Codecov
  - Comprehensive validation before pull requests
- Codecov configuration (`.codecov.yml`)
  - 70-100% coverage range targets
  - Project and patch thresholds
  - Proper ignore patterns for tests, examples, docs
- Coverage documentation (`docs/development/PRE_COMMIT_CHECKS.md`)
  - Complete guide for pre-commit workflows
  - Coverage concepts and best practices
  - Troubleshooting and CI/CD integration

### Changed

**Documentation Updates**
- Updated README with comprehensive Automated Report Generation section
  - Installation instructions for `[report-generator]` extra
  - Code examples and feature highlights
  - Added to Features, Installation, Optional Extras, and Examples sections
- Removed BETA designation from power supply in documentation
- Enhanced package description with automated report generation features

**Project Organization**
- Reorganized main directory structure for better clarity
- Moved test/development scripts to `scripts/` directory:
  - `test_llm_model_detection.py`
  - `test_pdf_progress.py` and `test_report_progress.pdf`
  - `test_signal_detection.py`
  - `test_unicode_rendering.py` and `test_unicode_rendering.pdf`
- Moved `ICON_SETUP.md` to `docs/development/` for better organization
- Removed duplicate `codecov.yml` (keeping `.codecov.yml`)
- Cleaned up empty `node_modules/` directory
- Root directory now contains 22 essential files/directories

### Fixed

**Development Dependencies**
- Added `pytest-cov>=4.0.0` to dev dependencies
  - Fixes "unrecognized arguments: --cov" error
  - Ensures coverage plugin available after `pip install -e ".[dev]"`
- Added `codecov>=2.1.0` to dev dependencies
  - Required by `make codecov-report` and `make pre-pr`
  - Enables coverage uploads in development

**Makefile Pytest Integration**
- Updated all pytest calls to use `python -m pytest`
  - Ensures pytest-cov plugin is properly loaded
  - Fixes coverage generation in nested make calls
  - Updated targets: `test`, `test-cov`, `test-fast`, `test-exceptions`

## [0.4.0-beta.1] - 2026-01-04

### Added (EXPERIMENTAL 🧪)

**Power Supply Control** - BETA Release
- ⚠️ **EXPERIMENTAL**: Power supply API is unstable and may change without warning
- **Installation**: `pip install "Siglent-Oscilloscope[power-supply-beta]"`
- **Target Stable Release**: v0.5.0 (pending community feedback)
- **Feedback**: Please report issues at [GitHub Issues](https://github.com/little-did-I-know/Siglent-Oscilloscope/issues)

**Core Power Supply Features**:
- **Main PowerSupply Class** (`siglent.power_supply.PowerSupply`)
  - SCPI-based communication over Ethernet (port 5024) or USB
  - **Multiple connection types supported**:
    - **Ethernet/LAN** via `SocketConnection` (default)
    - **USB** via `VISAConnection` (new - requires `[usb]` extras)
    - **GPIB** via `VISAConnection` (IEEE-488)
    - **Serial** via `VISAConnection` (RS-232)
  - Automatic model detection from `*IDN?` response
  - Capability-based feature availability
  - Context manager support for automatic connection management
  - Support for multiple power supply models via capability registry

- **Model Support**:
  - **Siglent SPD3303X / SPD3303X-E** (triple output, 30V/3A + 30V/3A + 5V/3A)
    - Full feature support including OVP, OCP, timer, waveform generation, tracking modes
  - **Siglent SPD1305X** (single output, 30V/5A)
  - **Siglent SPD1168X** (single output, 16V/8A)
  - **Generic SCPI-99 PSUs** (fallback with conservative defaults)

- **Output Control** (`siglent.power_supply_output.PowerSupplyOutput`)
  - Voltage setpoint control with validation against model limits
  - Current limit configuration
  - Output enable/disable
  - Real-time voltage, current, and power measurements
  - Operating mode detection (CV/CC)
  - Over-voltage protection (OVP) and over-current protection (OCP) settings
  - Timer functionality (Siglent SPD specific)
  - Waveform generation enable/disable (SPD3303X specific)

- **Advanced Features**:
  - **Tracking Modes** for multi-output PSUs:
    - Independent mode (default)
    - Series tracking (voltages add)
    - Parallel tracking (currents add)
  - Dynamic output creation based on model capabilities
  - Model-specific SCPI command variants
  - Comprehensive error handling and logging

- **Model Registry and Capability System** (`siglent.psu_models`)
  - `PSUCapability` dataclass with complete model specifications
  - `OutputSpec` defining per-output voltage/current/power limits
  - Automatic model detection with fuzzy matching
  - Generic SCPI fallback for unknown models
  - Extensible registry for adding new models

- **SCPI Command Management** (`siglent.psu_scpi_commands`)
  - Model-specific command variants (Siglent SPD vs generic SCPI)
  - Template-based command generation with parameter substitution
  - Support for multiple SCPI dialects

- **Data Logging** (`siglent.psu_data_logger`)
  - **PSUDataLogger**: Manual data capture with configurable channels
  - **TimedPSULogger**: Automated time-series data collection
    - Configurable sampling intervals
    - Background thread-based acquisition
    - Real-time data access during logging
    - Export to CSV, JSON, or custom formats
  - Voltage, current, and power logging for all outputs
  - Timestamp-based data organization

- **Connection Layer** (`siglent.connection`)
  - **VISAConnection** class for USB/GPIB/Serial support (new)
    - PyVISA-based connection supporting multiple transport protocols
    - USB-TMC protocol for USB connections
    - GPIB (IEEE-488) support
    - Serial (RS-232) support
    - Optional dependency: install with `[usb]` extras
    - Pure Python backend (pyvisa-py) requires no proprietary drivers
  - **Resource discovery utilities**:
    - `list_visa_resources()` - List all VISA devices
    - `find_siglent_devices()` - Automatically find Siglent instruments
  - Graceful fallback when PyVISA not installed

- **Examples**:
  - `examples/psu_basic_control.py` - Basic voltage/current control, measurements (Ethernet)
  - `examples/psu_usb_connection.py` - USB/GPIB/Serial connection examples (new)
  - `examples/psu_advanced_features.py` - Tracking modes, data logging, timer, waveform generation
  - `examples/psu_gui_test.py` - GUI integration test (experimental)

- **Testing**:
  - `tests/test_power_supply.py` - Unit tests with mock connection
  - `tests/test_visa_connection.py` - Tests for USB/VISA connections (new)
  - Hardware tests marked with `@pytest.mark.hardware`
  - Coverage for core functionality, model detection, SCPI commands, VISA connections

**Documentation**:
- Added `docs/development/EXPERIMENTAL_FEATURES.md` - Comprehensive guide for experimental features
  - Guidelines for marking features as experimental
  - Version numbering strategies (alpha/beta/rc)
  - Installation and discovery patterns
  - Documentation standards
  - Testing requirements
  - Graduation and deprecation processes
- Updated `docs/development/contributing.md` with experimental features section
- Module docstrings with experimental warnings and installation instructions

### Changed

- **Version Bumped**: `0.3.2` → `0.4.0-beta.1`
  - Pre-release version indicates experimental status
  - Follows semantic versioning with beta tag

- **Package Description Updated**:
  - PyPI description now mentions power supply support (beta)
  - Added SPD series models to package description
  - New keywords: "power supply", "SPD", "PSU", "voltage", "current"

- **Export Structure**:
  - `siglent.__init__.py` clearly separates stable vs experimental exports
  - PowerSupply, PSUDataLogger, TimedPSULogger marked as experimental (v0.4.0-beta.1)
  - Documentation in docstring warns about experimental status

### Technical Details

**Experimental Feature Implementation**:
- Module-level `FutureWarning` on import with clear experimental notice
- Optional dependency groups in pyproject.toml:
  - `[power-supply-beta]` - Power supply features (no extra dependencies)
  - `[usb]` - USB/GPIB/Serial support via PyVISA (optional)
- `[experimental]` group added for future experimental features
- Graceful degradation when optional dependencies not installed

**Architecture Highlights**:
- **Connection abstraction layer** (`BaseConnection`)
  - `SocketConnection` for TCP/IP Ethernet (default)
  - `VISAConnection` for USB/GPIB/Serial (optional via PyVISA)
  - Consistent SCPI interface across all connection types
- Shares exception hierarchy (`SiglentConnectionError`, `SiglentTimeoutError`, `CommandError`)
- Capability-based design allows easy addition of new models
- SCPI command abstraction supports multiple manufacturers and SCPI dialects
- Pluggable transport layer - easy to add new connection types

**Known Limitations** (Beta Status):
- Limited hardware testing (primarily SPD3303X-E)
- Some SCPI commands may vary between models
- Timer and waveform generation features only tested on SPD3303X
- Remote sensing support not yet implemented
- No GUI integration for power supply control (gui test script only)

**API Stability Notice**:
- Power supply API may change in future releases without deprecation warnings
- Breaking changes possible in any 0.x release
- Recommend pinning to specific version for production use: `Siglent-Oscilloscope==0.4.0-beta.1`
- Feedback welcome to help stabilize API before v0.5.0 stable release

### Upgrading from 0.3.x

**For Oscilloscope Users** (No Changes Required):
- All oscilloscope functionality remains stable
- No breaking changes to existing APIs
- Update to `0.4.0-beta.1` is backward compatible

**For Power Supply Users** (New Feature):
```bash
# Install with power supply support (Ethernet/LAN only)
pip install "Siglent-Oscilloscope[power-supply-beta]==0.4.0-beta.1"

# Install with USB support (includes PyVISA for USB/GPIB/Serial)
pip install "Siglent-Oscilloscope[usb]==0.4.0-beta.1"

# Install both
pip install "Siglent-Oscilloscope[power-supply-beta,usb]==0.4.0-beta.1"
```

**For Developers**:
- See `docs/development/EXPERIMENTAL_FEATURES.md` for guidance on experimental features
- Power supply modules will show experimental warnings on import
- Set `PYTHONWARNINGS=default::FutureWarning` to see all warnings during development

## [0.3.1] - 2026-01-02

### Added
- **Comprehensive MkDocs Documentation**
  - Added complete user guide documentation (5 files, ~3,000 lines):
    - `basic-usage.md` - Foundation for connecting and controlling oscilloscope
    - `waveform-capture.md` - Advanced capture techniques and data formats
    - `measurements.md` - Automated measurement capabilities
    - `trigger-control.md` - Comprehensive trigger configuration
    - `advanced-features.md` - FFT, math channels, automation, protocol decoding
  - Added GUI documentation (7 files, ~4,700 lines):
    - `overview.md` - GUI introduction and installation
    - `interface.md` - Complete UI reference with keyboard shortcuts
    - `live-view.md` - Real-time waveform visualization
    - `visual-measurements.md` - Interactive measurement markers
    - `fft-analysis.md` - Frequency domain analysis
    - `protocol-decoding.md` - I2C/SPI/UART decoding
    - `vector-graphics.md` - XY mode and waveform generation
  - Added connection guide (~960 lines):
    - `connection.md` - Network setup, troubleshooting, VNC access
  - Added development documentation (3 files, ~2,950 lines):
    - `building.md` - Build system, testing, documentation generation
    - `structure.md` - Codebase organization and design patterns
    - `testing.md` - Testing strategy and best practices
  - Added API reference:
    - `gui.md` - Auto-generated GUI API docs using mkdocstrings
  - **Total: 17 documentation files, ~11,900 lines**
- Material for MkDocs theme with admonitions (tip, info, warning)
- Comprehensive examples, troubleshooting sections, and cross-references
- mkdocstrings integration for auto-generating API docs from Python docstrings

### Fixed
- **Windows Executable Build Workflow**
  - Fixed 7-Zip archive creation failing with "The system cannot find the file specified" errors
  - Updated Windows build workflow to correctly reference README.md and LICENSE from parent directory
  - Changed paths from `README.md LICENSE` to `../README.md ../LICENSE` to match macOS/Linux builds
  - Resolved workflow exit code 1 error during archive creation

## [0.3.0] - Unreleased

### ⚠️ BREAKING CHANGES

- **Exception Class Renaming** (Issue #3 from Code Review)
  - `ConnectionError` renamed to `SiglentConnectionError` to avoid shadowing Python's built-in `ConnectionError`
  - `TimeoutError` renamed to `SiglentTimeoutError` to avoid shadowing Python's built-in `TimeoutError`
  - **Migration Guide:**
    - Update imports: `from siglent.exceptions import SiglentConnectionError, SiglentTimeoutError`
    - Update exception handling: `except (SiglentConnectionError, SiglentTimeoutError) as e:`
    - Backward compatibility aliases provided for transition period (will be removed in v1.0.0)
    - If you use `from siglent import ConnectionError`, update to `from siglent import SiglentConnectionError`
  - **Why:** Prevents naming conflicts with Python built-ins, improves code clarity, follows best practices
  - **Impact:** All code that imports or catches `ConnectionError` or `TimeoutError` from siglent.exceptions needs updating

### Added
- **Waveform Validation System** (`siglent/gui/utils/validators.py`)
  - `WaveformValidator` class for comprehensive data quality checks
  - Validates waveform data before plotting or processing
  - Catches common issues that cause blank plots:
    - None/missing waveforms
    - Empty voltage or time arrays
    - Mismatched array lengths between time and voltage
    - All-NaN or excessive NaN values (>50%)
    - Invalid voltage ranges (all zeros, infinite values)
    - Suspiciously large voltages (>1000V)
  - `validate()` method returns (is_valid, list_of_issues)
  - `validate_multiple()` separates valid from invalid waveforms
  - `get_summary()` generates diagnostic strings like "CH1: 50,000 samples, range -2.5V to +2.5V"
- **Detailed Error Dialog Widget** (`siglent/gui/widgets/error_dialog.py`)
  - `DetailedErrorDialog` class for user-friendly error reporting
  - Two-level error display:
    - User-friendly summary for non-technical users
    - Expandable technical details (stack trace, context) for debugging
  - Features:
    - Error icon and timestamp display
    - "Show Details" / "Hide Details" toggle button
    - Read-only text area for stack traces and context
    - "Copy to Clipboard" button for comprehensive error reports
    - Automatic dialog resizing when showing/hiding details
  - Structured error info dictionary format:
    - `type`: Error type name (e.g., 'TimeoutError')
    - `message`: User-friendly error message
    - `details`: Additional error details
    - `context`: Dictionary of context info (operation, settings, etc.)
    - `traceback`: Full stack trace string
    - `timestamp`: Error occurrence time
  - Convenience function `show_error_dialog()` for quick usage
- **Real-Time Status Updates** (LiveViewWorker)
  - New `status_update` signal (pyqtSignal(str)) for user feedback
  - Status messages during acquisition cycle:
    - "Checking enabled channels..."
    - "Acquiring CH1...", "Acquiring CH2...", etc.
    - "Validating waveforms..."
    - "Live view: CH1, CH2 (50,000, 100,000 samples)"
    - "No enabled channels", "Not connected"
  - Status bar updates reflect worker progress in real-time

### Changed
- **LiveViewWorker Error Handling Enhanced**
  - Changed `error_occurred` signal from `pyqtSignal(str)` → `pyqtSignal(dict)`
  - Errors now emit structured dictionaries with full context
  - Error info includes:
    - Error type, message, details
    - Operation context (update_interval, operation name)
    - Full traceback for debugging
    - Timestamp for error tracking
  - Integration with `WaveformValidator` for data quality checks
  - Only emits valid waveforms (invalid ones logged at WARNING level)
  - Enhanced logging: acquisition results logged at INFO/WARNING for visibility
- **WaveformCaptureWorker Validation Integration**
  - Validates all captured waveforms before emitting via `WaveformValidator.validate_multiple()`
  - Logs validation failures at WARNING level (visible to users)
  - Only emits valid waveforms to prevent blank plots
  - Enhanced error messages include validation failure details
  - Progress message updated: "Processing waveforms..." → "Validating waveforms..."
- **WaveformDisplayPG Pre-Plot Validation**
  - Validates all waveforms before plotting via `WaveformValidator.validate_multiple()`
  - Invalid waveforms logged at WARNING level with specific issues
  - Info label shows "Invalid data - check logs" when all waveforms fail validation
  - Enhanced diagnostic logging:
    - Valid waveforms logged at INFO level with summary
    - Runtime validation checks for None and empty arrays
    - Voltage range logging: "[−2.5V to +2.5V]" or "[all NaN]"
  - Only stores and plots valid waveforms
- **Main Window Error Handling Integration**
  - Connected to new `status_update` signal from LiveViewWorker
  - New `_on_live_view_status()` method updates status bar with worker messages
  - Enhanced `_on_live_view_error()` method:
    - Accepts structured error dictionary instead of plain string
    - Shows `DetailedErrorDialog` for rich error information
    - Brief error message in status bar (60 chars max, 5 second timeout)
    - Fallback to QMessageBox for legacy string errors
  - User-friendly error display with expandable technical details

### Fixed
- **Blank Plot Issue from Invalid Waveforms**
  - Root cause: Invalid waveforms (None, empty arrays, all NaN) were being plotted
  - Solution: Comprehensive validation before plotting in all code paths
  - Workers now validate data before emitting to GUI
  - Display widget validates again before rendering as safety check
- **Cryptic Error Messages**
  - Users previously saw raw exception strings in status bar
  - Now see structured error dialogs with context and debugging info
  - Technical details hidden by default but available on demand
- **Missing Waveform Quality Diagnostics**
  - Added comprehensive validation with specific issue reporting
  - Users now see exactly why waveforms failed (e.g., "CH1: All voltage values are NaN")
  - Validation results logged at WARNING level for visibility
- **Bare Exception Handling in Vector Graphics** (Issue #2 from Code Review)
  - Replaced bare `except:` clauses with specific exception types in `vector_graphics.py`
  - Now catches `CommandError`, `SiglentConnectionError`, `SiglentTimeoutError` explicitly
  - Prevents catching system exceptions like `KeyboardInterrupt` and `SystemExit`
  - Improves debugging and error handling clarity
- **Socket Read Race Condition** (Issue #5 from Code Review)
  - Added timeout protection in `socket.py` read loop
  - Prevents infinite loop if oscilloscope doesn't send newline-terminated responses
  - Raises `SiglentTimeoutError` with detailed message showing bytes received
  - Improves reliability and error diagnostics
- **Version Mismatch** (Issue #1 from Code Review)
  - Fixed version inconsistency between `__init__.py` (0.1.0) and `pyproject.toml` (0.2.6)
  - Both now correctly report version 0.2.6 (will be bumped to 0.3.0 for this release)

### Technical Improvements
- **Input Validation for SCPI Commands** (Issue #4 from Code Review)
  - Added ASCII validation before encoding commands in `socket.py`
  - Raises `CommandError` with clear message if non-ASCII characters detected
  - Prevents `UnicodeEncodeError` exceptions during command transmission
  - Example: `CommandError: SCPI command contains non-ASCII characters: "C1:VDIV 1.0V\u2013"`
- **Magic Number Constants** (Issue #6 from Code Review)
  - Added named constants for waveform conversion in `waveform.py`:
    - `WAVEFORM_CODE_PER_DIV_8BIT = 25.0` (codes per division for 8-bit ADC)
    - `WAVEFORM_CODE_PER_DIV_16BIT = 6400.0` (codes per division for 16-bit ADC)
    - `WAVEFORM_CODE_CENTER = 0` (center code for signed integer data)
  - Improved code documentation with conversion formula from SCPI manual
  - Makes waveform parsing logic easier to understand and maintain
- Centralized waveform validation logic in reusable `WaveformValidator` class
- Structured error reporting enables better debugging and user support
- Separation of user-facing messages from technical diagnostics
- Thread-safe error propagation from workers to main GUI thread
- Validation happens at multiple checkpoints (capture → emit → display)
- All docstrings updated to reference new exception names
- Backward compatibility aliases ensure gradual migration path

## [0.2.6] - 2025-12-31

### Added
- **Background Waveform Capture Worker** (`waveform_capture_worker.py`)
  - Non-blocking waveform acquisition in separate thread
  - Progress updates during multi-channel capture
  - Cancellable long-running downloads
  - Thread-safe signal/slot architecture
  - Real-time status updates: "Downloading CH1 data from scope..."
- **Progress Dialog for Capture Operations**
  - Visual progress indication during waveform downloads
  - Shows channel-by-channel progress
  - Cancel button to abort slow captures
  - Auto-closes on completion
  - Prevents concurrent capture operations
- **Intelligent Waveform Downsampling**
  - Min-max decimation algorithm for large datasets
  - Preserves signal peaks, valleys, and transients
  - Configurable threshold (default: 500,000 points)
  - Downsamples 5M point waveforms to 500K for display
  - Original data fully preserved for export/analysis
  - Status indicator shows "(display downsampled)" when active
- **Modern Graph Visual Styling** (PyQtGraph)
  - GitHub-inspired dark theme (#0d1117 background)
  - Thicker, smoother waveform lines (2.0px with antialiasing)
  - Vibrant channel colors for better visibility:
    - CH1: Bright Yellow (255, 220, 50)
    - CH2: Turquoise/Cyan (64, 224, 208)
    - CH3: Hot Pink (255, 105, 180)
    - CH4: Bright Green (50, 255, 100)
  - Subtle dotted grid (20% opacity)
  - Modern typography (Segoe UI, 11pt labels)
  - Muted axis colors for professional appearance
  - Sample count with thousands separators (e.g., "5,000,000 samples")

### Changed
- **Waveform Capture Architecture Refactored**
  - Moved from synchronous to asynchronous capture model
  - Capture operations now run in `WaveformCaptureWorker` thread
  - Main GUI thread remains responsive during downloads
  - Enhanced error handling with user-friendly messages
- **Canvas Rendering Optimization** (Matplotlib)
  - Replaced all blocking `canvas.draw()` calls with `canvas.draw_idle()`
  - Removed redundant `canvas.update()`, `canvas.repaint()` calls
  - Deferred rendering prevents GUI thread blocking
  - Applied to 17+ instances across waveform_display.py
- **Downsampling Threshold Increased**
  - Changed from 100,000 to 500,000 point threshold
  - Provides 5x more waveform detail on display
  - Maintains smooth performance even with millions of samples
- **Progress Dialog Signal Handling Improved**
  - Disconnects `canceled` signal before closing to prevent race conditions
  - Only triggers cancellation if worker thread is actually running
  - Eliminates spurious "User cancelled capture" messages

### Fixed
- **Critical: GUI Freezing During Waveform Capture**
  - Fixed multi-second GUI freeze when capturing large waveforms (5M samples)
  - Root cause: Synchronous SCPI queries blocked main thread for 5-10+ seconds
  - Solution: Background worker thread handles all network I/O
  - GUI remains fully responsive during capture operations
- **Progress Dialog Race Condition**
  - Fixed spurious cancellation events when dialog auto-closed
  - Dialog now properly disconnects signals before closing
  - Prevents "cancelled" state after successful capture
- **Large Waveform Display Performance**
  - Fixed severe lag when plotting 5+ million point waveforms
  - PyQtGraph could still block GUI thread with massive datasets
  - Min-max downsampling reduces display points by 10x while preserving signal fidelity
- **Incomplete Waveform Display Issue**
  - Fixed waveforms not showing full captured data
  - Increased downsampling threshold from 100K to 500K points
  - Users now see 5x more detail in displayed waveforms

### Performance
- **Waveform Capture**: No longer blocks GUI (runs in background thread)
- **Display Rendering**: 10x faster for large waveforms via intelligent downsampling
- **Canvas Updates**: Non-blocking deferred rendering throughout
- **User Responsiveness**: Can interact with GUI during long captures

### Technical Improvements
- Thread-safe capture worker with Qt signals for status updates
- Signal/slot disconnect pattern prevents race conditions
- Min-max decimation preserves signal integrity during downsampling
- NumPy-optimized downsampling algorithm for performance
- Clean separation of capture, processing, and display concerns

## [0.2.5] - 2025-12-30

### Added
- **Buy Me a Coffee Badge**
  - Added support/donation badge to README
  - Links to https://buymeacoffee.com/little.did.i.know
- **Comprehensive Test Suite**
  - Added `tests/test_channel.py` - 50+ test cases for channel control (280 lines)
    - Tests for enable/disable, voltage scale, offset, coupling
    - Probe ratio, bandwidth limit configuration
    - Multi-channel validation
  - Added `tests/test_trigger_comprehensive.py` - 40+ test cases for trigger (320 lines)
    - Mode control (AUTO, NORMAL, SINGLE, STOP)
    - Source, level, slope configuration
    - Edge trigger setup and actions
    - Holdoff and coupling control
  - Added `tests/test_measurement_comprehensive.py` - 45+ test cases for measurements (340 lines)
    - Frequency, period, Vpp, RMS, amplitude measurements
    - Min/max/mean voltage measurements
    - Timing measurements (rise/fall time, duty cycle)
    - Statistical measurements and cursor support
  - Added `tests/test_waveform_comprehensive.py` - 35+ test cases for waveform handling (280 lines)
    - WaveformData creation and properties
    - Binary waveform capture and parsing
    - Multi-format save/load (CSV, NPZ, MAT, HDF5)
    - Waveform analysis and comparison
  - Added `tests/test_socket_connection.py` - 33+ test cases for connection (270 lines)
    - Connection lifecycle (connect, disconnect, reconnect)
    - Command sending and querying
    - Binary data queries
    - Context manager and error handling
  - **Total: 490+ new test cases across 5 test modules**
- **Test Coverage and Quality Assurance**
  - Integrated pytest with coverage reporting in CI workflow
  - Added Codecov integration for test coverage tracking and visualization
  - Multi-version testing across Python 3.8-3.12
  - Coverage badge display on GitHub and PyPI
  - **Coverage Improvement**: Overall coverage increased from 39% to 42%
    - channel.py: Enhanced test coverage with comprehensive scenarios
    - trigger.py: Added extensive mode and configuration tests
    - measurement.py: Added tests for all measurement types
    - waveform.py: Added capture, save/load, and analysis tests
    - connection/socket.py: Added full connection lifecycle tests
- **Professional Project Badges**
  - CI build status badge (GitHub Actions)
  - Test coverage badge (Codecov)
  - PyPI downloads per month badge
  - GitHub issues tracker badge
  - GitHub stars badge
  - Last commit timestamp badge
- **Codecov Configuration**
  - Added `codecov.yml` with project-specific settings
  - Configured coverage thresholds and reporting
- **Pytest Configuration**
  - Added `[tool.pytest.ini_options]` to `pyproject.toml`
  - Configured test markers for hardware and GUI tests
  - Added strict pytest configuration for better test quality
- **Contributing Guide**
  - Comprehensive `CONTRIBUTING.md` with development guidelines
  - Code style, testing, and PR submission instructions
  - Development setup and best practices documentation
- **Community Standards**
  - Added `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1)
    - Private reporting contacts (email, GitHub, security advisory)
    - Clear enforcement responsibilities (maintainers defined)
    - Anti-retaliation policy
    - Step-by-step "What Happens Next" process
    - Appeals process for disputed decisions
  - Added `SECURITY.md` with vulnerability reporting process
  - Added security best practices and safe usage guidelines
- **Development Automation**
  - Added `.pre-commit-config.yaml` for automated code quality checks
  - Configured Black, Flake8, isort, Bandit security scanning
  - Added file cleanup and validation hooks
- **Makefile for Development**
  - Added comprehensive Makefile with common development tasks
  - Commands for testing, linting, formatting, building, publishing
  - Quick setup commands: `make dev-setup`, `make check`
  - Shortcuts: `make test-cov`, `make format`, `make gui`
  - Pre-PR commands: `make pre-pr`, `make pre-pr-fast`, `make pre-pr-fix`
- **Pre-PR Validation Scripts**
  - Added `scripts/pre_pr_check.py` - Comprehensive Python validation script
  - Added `scripts/pre_pr_check.sh` - Bash version for Unix-like systems
  - Automated checks: formatting, linting, security, tests, coverage, build
  - Options: `--fast` (skip slow checks), `--fix` (auto-fix issues)
  - Color-coded output with detailed error reporting
- **GitHub Issue Templates**
  - Structured bug report template (`.github/ISSUE_TEMPLATE/bug_report.yml`)
  - Feature request template (`.github/ISSUE_TEMPLATE/feature_request.yml`)
  - Issue template configuration with links to discussions
- **Pull Request Template**
  - Comprehensive PR template (`.github/PULL_REQUEST_TEMPLATE.md`)
  - Checklists for code quality, testing, and documentation
  - Sections for type of change, testing details, and migration guides
- **Dependabot Configuration**
  - Automated dependency updates (`.github/dependabot.yml`)
  - Weekly updates for Python packages and GitHub Actions
  - Grouped updates by dependency type (dev, security, GUI, core)
- **Interactive Tutorial**
  - Jupyter notebook tutorial (`examples/interactive_tutorial.ipynb`)
  - Step-by-step guide for oscilloscope control
  - Examples of waveform capture, FFT analysis, measurements
  - Multi-channel capture and data export demonstrations

### Changed
- **SEO and PyPI Metadata Improvements**
  - Enhanced package description with comprehensive feature highlights for better discoverability
  - Expanded keywords from 7 to 20 terms covering automation, data acquisition, GUI, protocol decoding, and visualization
  - Improved search ranking for oscilloscope automation, SCPI control, and lab equipment software
- **CI/CD Enhancements**
  - Enhanced CI workflow with dedicated test suite job
  - Added pytest-cov and pytest-xdist dependencies
  - Improved test execution with verbose output and coverage reporting
- **Test Organization**
  - Moved manual test scripts to `scripts/` directory
  - Reorganized interactive GUI tests as manual scripts
  - Ensured automated tests properly handle optional dependencies
- **README Improvements**
  - Added Community and Support section with links to issues, discussions, security
  - Added Resources section highlighting tutorial, examples, and guides
  - Added Quick Start for Contributors with Makefile commands
  - Improved Contributing section with detailed instructions

### Fixed
- **Test Suite Issues**
  - Fixed CI test failures due to missing PyQt6 dependencies
  - Moved manual test scripts (`test_live_view.py`, `test_pyqtgraph.py`, `test_dependency_check.py`, `test_waveform_display.py`) to `scripts/` directory
  - Prevented pytest from collecting non-test GUI demo scripts
  - Ensured GUI tests skip gracefully when PyQt6 is not installed
  - Fixed hanging test in `test_socket_connection.py::TestSocketQueryBinary::test_query_binary`
    - Test was using `mock_socket.recv.return_value` which caused infinite loop in `read_raw()`
    - Changed to `side_effect` to return data once then raise timeout to signal end of data
- **Python 3.8 Compatibility**
  - Fixed `pyproject.toml` license field to use PEP 621 compliant format
  - Changed `license = "MIT"` to `license = {text = "MIT"}` for Python 3.8 compatibility
  - Resolved build errors in older setuptools versions

## [0.2.4] - 2025-12-29

### Added
- **Vector Graphics / XY Mode Features** (requires `[fun]` extras)
  - New `vector_graphics.py` module for generating waveforms for XY mode display
  - `VectorDisplay` class for managing XY mode and waveform generation
  - `Shape` factory with generators for:
    - Basic shapes: circle, rectangle, polygon, star, line
    - Lissajous figures for classic oscilloscope patterns
    - Text rendering (experimental)
  - `VectorPath` class with transformation methods (rotate, scale, translate, flip)
  - Waveform export to CSV, NumPy, and binary formats for AWG upload
  - **GUI Integration**: New "Vector Graphics 🎨" tab in GUI application
    - Shape selection with dynamic parameter controls (Circle, Rectangle, Star, Triangle, Lissajous, Line)
    - XY mode enable/disable directly from GUI
    - Waveform generation with sample rate and duration controls
    - Export to CSV, NumPy, or Binary format for AWG upload
    - Works even without scope connection (offline waveform generation)
    - Graceful degradation: shows installation instructions if `[fun]` extras not installed
  - Example script: `examples/vector_graphics_xy_mode.py` with animations
  - Optional dependency group `[fun]` in pyproject.toml:
    - shapely>=2.0.0 (geometric operations)
    - Pillow>=10.0.0 (text rendering)
    - svgpathtools>=1.6.0 (SVG path support)

### Changed
- Updated README.md with comprehensive Vector Graphics / XY Mode section
  - Added GUI tab documentation with step-by-step usage instructions
  - Added example use cases (calibration, education, pattern testing)
  - Updated installation instructions to include `[fun]` extras option
  - Added `[fun]` to Optional Extras requirements section
- Updated `siglent/gui/main_window.py` to integrate Vector Graphics tab
- Updated `siglent/gui/widgets/__init__.py` with import note for optional panel

## [0.2.3] - 2025-12-29

### Changed
- project.toml version number due to pypi version number conflict

## [0.2.2] - 2025-12-29

### Changed
- **GitHub Workflow Updates**
  - Simplified PyPI publishing workflow
  - Removed TestPyPI publishing step for streamlined releases
  - Workflow now publishes directly to PyPI on releases or manual trigger

## [0.2.1] - 2025-12-29

### Changed
- **Project Structure Reorganization** to follow Python packaging best practices
  - Moved all test files to `tests/` directory
  - Moved development utilities to `scripts/` directory
  - Consolidated documentation into `docs/` directory
  - Created `docs/development/` for build and deployment documentation
  - Updated MANIFEST.in to properly exclude development files from distribution
  - Updated .gitignore to properly exclude build artifacts
  - Added `docs/development/PROJECT_STRUCTURE.md` documenting the project layout

### Fixed
- Improved .gitignore to properly exclude dist/, build/, and egg-info directories

## [0.2.0] - 2025-12-29

### Added
- **High-Performance Live View** with PyQtGraph
  - 100x faster real-time plotting (1000+ fps capability vs 5-10 fps)
  - Replaced matplotlib with PyQtGraph for live waveform display
  - Non-blocking threaded data acquisition
  - Smooth updates at 5-20 fps with responsive GUI
  - Supports all 4 channels simultaneously
- **Interactive Visual Measurement System**
  - Click-and-drag measurement markers directly on waveforms
  - 15+ measurement types with specialized visual markers:
    - Frequency/Period with auto-detection
    - Voltage measurements (Vpp, Amplitude, Max, Min, RMS, Mean)
    - Timing measurements (Rise Time, Fall Time, Pulse Width, Duty Cycle)
  - Real-time measurement updates as you adjust marker gates
  - Visual gates and markers with color-coded styling
  - Auto-placement with intelligent positioning
- **Measurement Configuration Management**
  - Save measurement setups to JSON files
  - Load previously saved configurations
  - Configuration browser and management
  - Shareable measurement templates
- **Measurement Export Functionality**
  - Export results to CSV format
  - Export to JSON with full configuration
  - Batch measurement support
  - Timestamp and metadata inclusion
- **Background Worker Thread** (`LiveViewWorker`)
  - Prevents GUI freezing during SCPI queries
  - Thread-safe signal/slot communication
  - Configurable update intervals (default: 200ms)
  - Automatic error handling and reporting
- **Visual Measurement Panel** (`visual_measurement_panel.py`)
  - Add/remove markers via UI
  - Enable/disable individual markers
  - Live measurement value display
  - Auto-update mode with 1-second refresh
  - Marker list with real-time results
- **New Measurement Marker Classes**
  - Base `MeasurementMarker` abstract class
  - `FrequencyMarker` with period auto-detection
  - `VoltageMarker` with threshold visualization
  - `TimingMarker` with edge detection
- **PyQtGraph-based Waveform Display** (`waveform_display_pg.py`)
  - Drop-in replacement for matplotlib display
  - Preserved all existing features (cursors, zoom, pan)
  - Optimized update performance
  - Configurable visual styling
- **Measurement Data Models** (`measurement_config.py`)
  - `MeasurementMarkerConfig` dataclass
  - `MeasurementConfigSet` for collections
  - JSON serialization/deserialization
  - Configuration validation

### Changed
- Migrated live view from matplotlib to PyQtGraph for dramatic performance improvement
- Replaced timer-based acquisition with threaded worker pattern
- Enhanced waveform display with marker support methods
- Updated main window to integrate visual measurement panel
- Improved channel enabled detection to handle scope response format

### Fixed
- **Channel Detection Bug**: Fixed `channel.enabled` property failing to detect "C1:TRA ON" response format (channel.py:48)
- **GUI Freezing**: Moved blocking SCPI queries to background thread to maintain GUI responsiveness
- **Live View Startup**: Removed non-existent `refresh_state()` call that caused crashes
- **Waveform Update Performance**: Eliminated unnecessary canvas redraws during live view

### Dependencies
- Added `pyqtgraph>=0.13.0` to GUI dependencies
- Updated installation instructions for `[gui]` extra

### Technical Improvements
- Thread-safe Qt signal/slot architecture for live updates
- Abstract base class pattern for extensible measurement markers
- Dataclass-based configuration management
- Separation of rendering and calculation logic
- Optimized matplotlib blitting for fast partial updates (fallback mode)
- Coordinate system handling for zoom/pan compatibility

### Performance
- Live view: 100x faster (5-10 fps → 1000+ fps capability)
- SCPI queries: Moved to background thread (GUI unblocked)
- Canvas updates: <1ms per frame vs 100-500ms previously
- Measurement calculations: Real-time NumPy-based processing

## [0.1.0] - 2025-12-25

### Added
- Initial release of Siglent oscilloscope control package
- Complete programmatic API for controlling Siglent SD824x HD oscilloscopes
- TCP/IP socket connection via SCPI protocol (port 5024)
- Full channel control (all 4 channels)
  - Voltage scale and offset configuration
  - Coupling mode (DC/AC/GND)
  - Probe ratio settings
  - Bandwidth limiting
- Comprehensive trigger control
  - Trigger modes (Auto, Normal, Single, Stop)
  - Edge trigger configuration
  - Source selection and level control
  - Slope and coupling settings
- Waveform acquisition and processing
  - Binary waveform download
  - Automatic voltage conversion
  - NumPy array output
  - CSV and NPY export formats
- Automated measurements
  - Frequency, period, Vpp, RMS, amplitude
  - Rise/fall time, duty cycle
  - Min/max/mean calculations
  - Cursor support
- PyQt6-based GUI application
  - Connection management dialog
  - Acquisition controls (Run/Stop/Single)
  - Live waveform view with configurable update rate
  - Single waveform capture
  - Multi-channel matplotlib display with oscilloscope-style theming
  - Interactive zoom and pan
  - Waveform export to PNG/PDF/SVG
- Console script entry point (`siglent-gui`)
- Comprehensive example scripts
  - Basic usage and configuration
  - Waveform capture and export
  - Automated measurements
  - Live plotting
- Full documentation
  - API documentation in README
  - PyPI deployment guide
  - Build instructions
  - Example scripts with explanations

### Technical Details
- Python 3.8+ support
- Dependencies: PyQt6, NumPy, Matplotlib
- MIT License
- Type hints throughout codebase
- Context manager support for oscilloscope connections
- Comprehensive error handling with custom exceptions

[0.1.0]: https://github.com/siglent-control/siglent/releases/tag/v0.1.0
