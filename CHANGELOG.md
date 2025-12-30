# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.5] - 2025-12-30

### Changed
- **SEO and PyPI Metadata Improvements**
  - Enhanced package description with comprehensive feature highlights for better discoverability
  - Expanded keywords from 7 to 20 terms covering automation, data acquisition, GUI, protocol decoding, and visualization
  - Improved search ranking for oscilloscope automation, SCPI control, and lab equipment software

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
