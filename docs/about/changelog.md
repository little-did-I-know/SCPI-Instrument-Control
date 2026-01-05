# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

See [full changelog on GitHub](https://github.com/little-did-I-know/Siglent-Oscilloscope/blob/main/CHANGELOG.md) for detailed version history.

Previous releases include:

- **v0.2.6**: Background waveform capture, progress dialogs, intelligent downsampling, modern graph styling
- **v0.2.5**: Comprehensive test suite (490+ tests), Codecov integration, professional badges
- **v0.2.4**: Vector graphics/XY mode, GUI integration, shape generators
- **v0.2.3**: Version numbering fix
- **v0.2.2**: Workflow updates
- **v0.2.1**: Project structure reorganization
- **v0.2.0**: High-performance live view with PyQtGraph, visual measurement system
- **v0.1.0**: Initial release with basic SCPI control and GUI

[View full changelog](https://github.com/little-did-I-know/Siglent-Oscilloscope/blob/main/CHANGELOG.md)
