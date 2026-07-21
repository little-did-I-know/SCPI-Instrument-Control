# Testing Guide

This guide covers the testing strategy, test organization, and best practices for SCPI Instrument Control.

## Overview

The project uses a comprehensive testing approach with multiple test categories:

- **Unit Tests** - Test individual components in isolation
- **Integration Tests** - Test component interactions
- **GUI Tests** - Test user interface components
- **Hardware Tests** - Test with real oscilloscope (optional)
- **Mock Tests** - Simulate hardware for reliable testing

**Test Framework:** pytest
**Coverage Tool:** pytest-cov
**Coverage Target:** >80% overall, >90% for core modules

## Quick Start

### Running Tests

**All tests:**

```bash
make test
```

**With coverage:**

```bash
make test-cov
```

**Fast parallel execution:**

```bash
make test-fast
```

**Specific test file:**

```bash
pytest tests/test_oscilloscope.py -v
```

**Specific test function:**

```bash
pytest tests/test_oscilloscope.py::test_connection -v
```

### Test Markers

**Skip hardware tests:**

```bash
pytest -m "not hardware"
```

**Only GUI tests:**

```bash
pytest -m gui
```

**Only hardware tests:**

```bash
pytest -m hardware
```

## Test Organization

### Directory Structure

```
tests/
├── conftest.py                       # Pytest configuration and fixtures
├── test_oscilloscope.py              # Oscilloscope class tests
├── test_channel.py                   # Channel control tests
├── test_trigger.py                   # Trigger configuration tests
├── test_measurement.py               # Measurement tests
├── test_waveform.py                  # Waveform data tests
├── test_connection.py                # Connection layer tests
├── test_protocol_decoders.py         # Protocol decoder tests
├── test_analysis.py                  # Analysis tools tests
├── test_exceptions.py                # Exception handling tests
├── test_math_channel.py              # Math channel tests
├── test_reference_waveform.py        # Reference waveform tests
├── test_automation.py                # Automation helpers tests
├── test_vector_graphics.py           # Vector graphics tests
├── test_gui/                         # GUI tests
│   ├── test_main_window.py
│   ├── test_widgets.py
│   ├── test_live_view.py
│   └── test_connection_manager.py
└── fixtures/                         # Test data files
    ├── sample_waveforms.npz
    ├── mock_responses.json
    └── test_configurations.yaml
```

### Test Categories

**Unit Tests:**

- File: `test_*.py`
- Location: `tests/`
- Purpose: Test individual functions/classes
- Speed: Fast (<1s per test)
- Dependencies: Mock external resources

**Integration Tests:**

- File: `test_*_integration.py`
- Location: `tests/`
- Purpose: Test component interactions
- Speed: Medium (1-5s per test)
- Dependencies: MockConnection

**GUI Tests:**

- Marker: `@pytest.mark.gui`
- Location: `tests/test_gui/`
- Purpose: Test UI components
- Speed: Slow (5-10s per test)
- Dependencies: PyQt6

**Hardware Tests:**

- Marker: `@pytest.mark.hardware`
- Location: `tests/`
- Purpose: Test with real oscilloscope
- Speed: Very slow (10-30s per test)
- Dependencies: Connected oscilloscope

## Writing Tests

### Basic Test Structure

```python
"""
tests/test_example.py
"""
import pytest
from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection


def test_basic_connection():
    """Test basic connection to oscilloscope."""
    # Arrange
    mock_conn = MockConnection()

    # Act
    scope = Oscilloscope(connection=mock_conn)

    # Assert
    assert scope.connected
    assert scope.model == "SDS2104X Plus"


def test_channel_enable():
    """Test enabling a channel."""
    # Arrange
    mock_conn = MockConnection()
    scope = Oscilloscope(connection=mock_conn)

    # Act
    scope.channel1.enabled = True

    # Assert
    assert scope.channel1.enabled is True
```

### Using Fixtures

**Define in conftest.py:**

```python
"""
tests/conftest.py
"""
import pytest
from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection


@pytest.fixture
def mock_scope():
    """Create oscilloscope with mock connection."""
    conn = MockConnection()
    scope = Oscilloscope(connection=conn)
    yield scope
    scope.close()


@pytest.fixture
def sample_waveform():
    """Load sample waveform data."""
    import numpy as np
    return np.sin(np.linspace(0, 2*np.pi, 1000))
```

**Use in tests:**

```python
def test_with_fixture(mock_scope):
    """Test using fixture."""
    assert mock_scope.connected
    assert mock_scope.channel1 is not None


def test_waveform_processing(sample_waveform):
    """Test waveform processing."""
    assert len(sample_waveform) == 1000
    assert sample_waveform.max() <= 1.0
```

### Parametrized Tests

Test multiple scenarios efficiently:

```python
import pytest


@pytest.mark.parametrize("channel", [1, 2, 3, 4])
def test_all_channels(mock_scope, channel):
    """Test all channels."""
    ch = getattr(mock_scope, f'channel{channel}')
    ch.enabled = True
    assert ch.enabled is True


@pytest.mark.parametrize("voltage,expected", [
    (1.0, 1.0),
    (2.0, 2.0),
    (5.0, 5.0),
    (10.0, 10.0),
])
def test_voltage_scales(mock_scope, voltage, expected):
    """Test different voltage scales."""
    mock_scope.channel1.voltage_scale = voltage
    assert mock_scope.channel1.voltage_scale == expected


@pytest.mark.parametrize("trigger_mode", ["AUTO", "NORMAL", "SINGLE", "STOP"])
def test_trigger_modes(mock_scope, trigger_mode):
    """Test all trigger modes."""
    mock_scope.trigger.mode = trigger_mode
    assert mock_scope.trigger.mode == trigger_mode
```

### Testing Exceptions

```python
import pytest
from scpi_control.exceptions import SiglentConnectionError, CommandError


def test_connection_timeout():
    """Test connection timeout handling."""
    with pytest.raises(SiglentConnectionError):
        scope = Oscilloscope('invalid.ip.address', timeout=0.1)


def test_invalid_channel():
    """Test invalid channel raises error."""
    mock_scope = MockScope()
    with pytest.raises(ValueError, match="Channel must be 1-4"):
        mock_scope.get_waveform(5)


def test_command_error():
    """Test SCPI command error handling."""
    mock_scope = MockScope()
    with pytest.raises(CommandError):
        mock_scope._send_invalid_command()
```

### Async Tests

For GUI and worker threads:

```python
import pytest
from PyQt6.QtCore import QTimer


@pytest.mark.gui
class TestLiveView:
    """Test live view functionality."""

    def test_start_stop(self, qtbot, mock_scope):
        """Test starting and stopping live view."""
        window = MainWindow(mock_scope)

        # Start live view
        window.start_live_view()

        # Wait for signal
        with qtbot.waitSignal(window.live_view_started, timeout=1000):
            pass

        assert window.is_live_view_active

        # Stop live view
        window.stop_live_view()

        with qtbot.waitSignal(window.live_view_stopped, timeout=1000):
            pass

        assert not window.is_live_view_active
```

## Test Markers

### Available Markers

**`@pytest.mark.hardware`** - Requires real oscilloscope

```python
@pytest.mark.hardware
def test_real_connection():
    """Test with actual hardware."""
    scope = Oscilloscope('192.168.1.100')
    assert scope.connected
```

**`@pytest.mark.gui`** - Requires PyQt6

```python
@pytest.mark.gui
def test_main_window(qtbot):
    """Test GUI main window."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.isVisible()
```

**`@pytest.mark.slow`** - Slow running tests

```python
@pytest.mark.slow
def test_long_capture():
    """Test long duration capture."""
    # Takes >10 seconds
    pass
```

**`@pytest.mark.network`** - Requires network access

```python
@pytest.mark.network
def test_remote_connection():
    """Test remote network connection."""
    scope = Oscilloscope('remote.example.com')
```

### Marker Configuration

**In pyproject.toml:**

```toml
[tool.pytest.ini_options]
markers = [
    "hardware: tests that require actual oscilloscope hardware",
    "gui: tests that require GUI dependencies (PyQt6)",
    "slow: tests that take >5 seconds",
    "network: tests that require network access",
]
```

### Skipping Markers

**Skip hardware tests:**

```bash
pytest -m "not hardware"
```

**Skip slow tests:**

```bash
pytest -m "not slow"
```

**Only run fast unit tests:**

```bash
pytest -m "not hardware and not gui and not slow"
```

## Mocking

### MockConnection

The project provides `MockConnection` (`scpi_control/connection/mock/base.py`) for
testing without hardware. There is no `add_response()`/`sent_commands` API — state
is configured via constructor keyword arguments and inspected via public
attributes:

```python
from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope

# Create a mock connection with initial state
mock = MockConnection(
    "mock",
    idn="Siglent Technologies,SDS824X HD,MOCK0001,3.8.12",
    channel_states={1: True, 2: False},
    voltage_scales={1: 0.5},
    sample_rate=1_000_000.0,
    timebase=1e-3,
)

scope = Oscilloscope("mock", connection=mock)
scope.connect()

# Inspect what the code under test actually sent
waveform = scope.get_waveform(1)
assert mock.waveform_requests == [1]
assert any("TIMebase" in q or "TDIV" in q for q in mock.queries)
```

Key constructor keyword arguments (all optional, keyword-only after `host`,
`port`, `timeout`):

- `idn` - the `*IDN?` response string; drives dialect/vendor auto-detection
- `channel_states`, `voltage_scales`, `voltage_offsets` - per-channel dicts,
  e.g. `{1: True}`, `{1: 0.5}`
- `waveform_payloads` - `{channel: bytes}` to serve a fixed captured payload
  instead of synthesis
- `signals` - `{channel: SignalSpec(...)}` to choose what a channel
  synthesizes (see [Synthetic Signals](../user-guide/synthetic-signals.md));
  channels without an explicit `SignalSpec` still synthesize a state-coupled
  default waveform - there is no "no signal" option
- `sample_rate`, `timebase` - initial acquisition settings
- `trigger_status` - a list of trigger-state tokens the mock returns
- `custom_responses` - `{command: response}` (or `{command: [responses, ...]}`
  to pop successive values on repeated queries) for exact-match query
  overrides, checked before any built-in handling
- `psu_mode`, `awg_mode`, `daq_mode` (with matching `psu_idn`/`psu_outputs`,
  `awg_idn`/`awg_channels`, `daq_idn`/`daq_readings`) - switch the mock to a
  power supply, function generator, or data logger personality instead of an
  oscilloscope

Instrumentation attributes recorded automatically, for assertions:

- `mock.writes` - every command passed to `write()`, in order
- `mock.queries` - every command passed to `query()`, in order
- `mock.waveform_requests` - channel numbers requested via `C{n}:WF?`, in order
- `mock.timebase_updates` - timebase values as they're changed
- `mock.scale_updates` - `{channel: [values, ...]}` as voltage scale changes,
  per channel

### Overriding Specific Responses

Use `custom_responses` for exact-match overrides that don't fit synthesis:

```python
mock = MockConnection(custom_responses={"C1:VDIV?": "C1:VDIV 2.00E+00V"})
```

Pass a list to return successive values across repeated queries of the same
command:

```python
mock = MockConnection(custom_responses={"SAST?": ["Stop", "Run", "Stop"]})
```

### Mocking External Dependencies

**Using unittest.mock:**

```python
from unittest.mock import Mock, patch, MagicMock


def test_network_request():
    """Test network request with mock."""
    with patch('scpi_control.connection.socket.socket') as mock_socket:
        # Configure mock
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recv.return_value = b"OK\n"

        # Test code
        conn = SocketConnection('192.168.1.100')
        response = conn.query("*IDN?")

        # Verify
        mock_sock.send.assert_called_once()
        mock_sock.recv.assert_called()


def test_file_io():
    """Test file I/O with mock."""
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = "data"

        # Test code that reads file
        result = load_configuration('config.yaml')

        # Verify
        mock_open.assert_called_with('config.yaml')
```

### pytest-mock Plugin

```bash
pip install pytest-mock
```

```python
def test_with_mocker(mocker):
    """Test using pytest-mock."""
    # Mock method
    mock_send = mocker.patch('scpi_control.connection.SocketConnection.send')
    mock_send.return_value = "OK"

    # Test
    conn = SocketConnection('192.168.1.100')
    result = conn.query("*IDN?")

    # Verify
    mock_send.assert_called_once_with("*IDN?")
    assert result == "OK"
```

## Fixtures

### Common Fixtures

**In conftest.py:**

```python
import pytest
import numpy as np
from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection


@pytest.fixture(scope="session")
def sample_data_dir(tmp_path_factory):
    """Create temporary directory for test data."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture
def mock_scope():
    """Create oscilloscope with mock connection."""
    conn = MockConnection()
    scope = Oscilloscope(connection=mock)
    yield scope
    scope.close()


@pytest.fixture
def sine_wave():
    """Generate sine wave test data."""
    t = np.linspace(0, 1, 1000)
    return np.sin(2 * np.pi * 10 * t)  # 10 Hz


@pytest.fixture
def square_wave():
    """Generate square wave test data."""
    t = np.linspace(0, 1, 1000)
    return np.sign(np.sin(2 * np.pi * 10 * t))


@pytest.fixture
def captured_waveform(mock_scope):
    """Capture waveform from mock scope."""
    mock_scope.channel1.enabled = True
    return mock_scope.get_waveform(1)
```

### Fixture Scopes

**Function scope (default):**

```python
@pytest.fixture  # Created/destroyed for each test
def temp_file():
    f = open('test.txt', 'w')
    yield f
    f.close()
```

**Class scope:**

```python
@pytest.fixture(scope="class")  # Created once per test class
def database():
    db = Database()
    yield db
    db.close()
```

**Module scope:**

```python
@pytest.fixture(scope="module")  # Created once per test file
def expensive_resource():
    resource = create_expensive_resource()
    yield resource
    resource.cleanup()
```

**Session scope:**

```python
@pytest.fixture(scope="session")  # Created once per test session
def test_data_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("data")
```

### Fixture Dependencies

```python
@pytest.fixture
def database():
    """Database fixture."""
    db = Database()
    yield db
    db.close()


@pytest.fixture
def user_table(database):
    """User table depends on database."""
    database.create_table('users')
    yield database.table('users')
    database.drop_table('users')


def test_user_creation(user_table):
    """Test uses fixture that depends on another."""
    user_table.insert({'name': 'Alice'})
    assert user_table.count() == 1
```

## GUI Testing

### PyQt Testing with pytest-qt

**Install:**

```bash
pip install pytest-qt
```

**Basic widget test:**

```python
import pytest
from PyQt6.QtWidgets import QPushButton


@pytest.mark.gui
def test_button_click(qtbot):
    """Test button click."""
    button = QPushButton("Click me")
    qtbot.addWidget(button)

    # Simulate click
    with qtbot.waitSignal(button.clicked, timeout=1000):
        button.click()


@pytest.mark.gui
def test_main_window(qtbot, mock_scope):
    """Test main window."""
    from scpi_control.gui.main_window import MainWindow

    window = MainWindow(scope=mock_scope)
    qtbot.addWidget(window)

    # Wait for window to show
    window.show()
    qtbot.waitForWindowShown(window)

    assert window.isVisible()
    assert window.windowTitle() == "Siglent Oscilloscope Control"
```

### Signal Testing

```python
@pytest.mark.gui
def test_signal_emission(qtbot):
    """Test Qt signal emission."""
    from PyQt6.QtCore import QObject, pyqtSignal

    class Emitter(QObject):
        signal = pyqtSignal(str)

    emitter = Emitter()

    # Wait for signal
    with qtbot.waitSignal(emitter.signal, timeout=1000) as blocker:
        emitter.signal.emit("test message")

    assert blocker.args == ["test message"]


@pytest.mark.gui
def test_multiple_signals(qtbot):
    """Test waiting for multiple signals."""
    obj1 = Emitter()
    obj2 = Emitter()

    with qtbot.waitSignals([obj1.signal, obj2.signal], timeout=1000):
        obj1.signal.emit("one")
        obj2.signal.emit("two")
```

### Mouse and Keyboard Events

```python
from PyQt6.QtCore import Qt


@pytest.mark.gui
def test_mouse_click(qtbot):
    """Test mouse click event."""
    button = QPushButton("Click")
    qtbot.addWidget(button)

    # Simulate click at center
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


@pytest.mark.gui
def test_keyboard_input(qtbot):
    """Test keyboard input."""
    from PyQt6.QtWidgets import QLineEdit

    line_edit = QLineEdit()
    qtbot.addWidget(line_edit)

    # Type text
    qtbot.keyClicks(line_edit, "Hello World")
    assert line_edit.text() == "Hello World"

    # Press Enter
    qtbot.keyPress(line_edit, Qt.Key.Key_Return)
```

## Coverage

### Generating Coverage Reports

**Basic coverage:**

```bash
pytest --cov=siglent tests/
```

**HTML report:**

```bash
pytest --cov=siglent --cov-report=html tests/
# Open htmlcov/index.html
```

**Terminal report:**

```bash
pytest --cov=siglent --cov-report=term-missing tests/
```

**Multiple formats:**

```bash
pytest --cov=siglent --cov-report=html --cov-report=term-missing tests/
```

**Using Make:**

```bash
make test-cov
```

### Coverage Configuration

**In pyproject.toml:**

```toml
[tool.coverage.run]
source = ["siglent"]
omit = [
    "*/tests/*",
    "*/test_*.py",
    "*/__pycache__/*",
    "*/site-packages/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### Coverage Targets

**Overall target:** >80%

**Module-specific targets:**

- Core modules (`oscilloscope.py`, `channel.py`, etc.): >90%
- Connection layer: >85%
- Protocol decoders: >80%
- GUI modules: >70%
- Utilities: >75%

### Excluding Code from Coverage

```python
def debug_function():  # pragma: no cover
    """Function not covered in tests."""
    print("Debug info")


if TYPE_CHECKING:  # Excluded by default
    from typing import Optional


if __name__ == "__main__":  # Excluded by default
    main()
```

## Continuous Integration

### GitHub Actions

**Workflow file: `.github/workflows/test.yml`**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.8", "3.9", "3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest -m "not hardware and not gui"

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Local CI Simulation

**Run all checks:**

```bash
make pre-pr
```

**Individual checks:**

```bash
make lint      # Linting
make format    # Code formatting
make test      # Tests
make build     # Package build
```

## Best Practices

### Test Naming

**Good:**

```python
def test_channel_enable_sets_state():
    """Test enabling channel sets state correctly."""
    pass

def test_trigger_level_validation_raises_error_for_invalid_value():
    """Test trigger level validation."""
    pass
```

**Bad:**

```python
def test1():
    pass

def test_function():
    pass
```

### Arrange-Act-Assert

```python
def test_example():
    """Test following AAA pattern."""
    # Arrange - Set up test data
    scope = MockScope()
    scope.channel1.enabled = False

    # Act - Perform action
    scope.channel1.enabled = True

    # Assert - Verify result
    assert scope.channel1.enabled is True
```

### One Assertion Per Test (Guideline)

**Prefer:**

```python
def test_connection_establishes():
    """Test connection established."""
    scope = Oscilloscope('192.168.1.100')
    assert scope.connected


def test_connection_identifies_model():
    """Test model identification."""
    scope = Oscilloscope('192.168.1.100')
    assert scope.model == "SDS2104X Plus"
```

**Over:**

```python
def test_connection():
    """Test connection (too many assertions)."""
    scope = Oscilloscope('192.168.1.100')
    assert scope.connected
    assert scope.model == "SDS2104X Plus"
    assert scope.serial_number is not None
    assert scope.firmware_version is not None
```

### Test Independence

**Good** - Tests don't depend on each other:

```python
def test_A():
    scope = create_scope()
    # Test A
    scope.close()


def test_B():
    scope = create_scope()  # Fresh scope
    # Test B
    scope.close()
```

**Bad** - Tests share state:

```python
global_scope = None

def test_A():
    global global_scope
    global_scope = create_scope()
    # Test A


def test_B():
    # Depends on test_A running first
    global_scope.do_something()
```

### Descriptive Assertions

**Good:**

```python
assert result == expected, f"Expected {expected}, got {result}"
```

**Better:**

```python
assert result == expected, (
    f"Waveform processing failed: "
    f"expected {expected} samples, got {result}"
)
```

## Troubleshooting

### Tests Failing

**Import errors:**

```bash
# Reinstall in editable mode
pip install -e ".[dev]"
```

**Fixture not found:**

```python
# Check conftest.py exists
# Verify fixture is defined
# Check fixture scope
```

**Mock not working:**

```python
# Verify mock patch path
# Check mock is configured before use
# Use spec=True for stricter mocking
mock = Mock(spec=RealClass)
```

### Coverage Issues

**Missing coverage:**

```bash
# Generate detailed report
pytest --cov=siglent --cov-report=term-missing tests/

# Check which lines are missing
# Add tests for uncovered code
```

**Incorrect coverage:**

```bash
# Clear coverage cache
rm -rf .coverage htmlcov/

# Run clean coverage
pytest --cov=siglent --cov-report=html tests/
```

### GUI Tests Failing

**No display:**

```bash
# Linux: Install xvfb
sudo apt-get install xvfb

# Run with xvfb
xvfb-run pytest -m gui
```

**Timing issues:**

```python
# Increase timeouts
with qtbot.waitSignal(signal, timeout=5000):  # 5 seconds
    pass

# Add explicit waits
qtbot.wait(100)  # 100ms
```

## Quick Reference

### Common Commands

| Command                    | Description                 |
| -------------------------- | --------------------------- |
| `make test`                | Run all tests               |
| `make test-cov`            | Run tests with coverage     |
| `make test-fast`           | Run tests in parallel       |
| `pytest -v`                | Verbose output              |
| `pytest -k "test_name"`    | Run specific tests          |
| `pytest -m "not hardware"` | Skip hardware tests         |
| `pytest -x`                | Stop on first failure       |
| `pytest --pdb`             | Drop to debugger on failure |

### Useful Pytest Options

| Option          | Description            |
| --------------- | ---------------------- |
| `-v, --verbose` | Verbose output         |
| `-s`            | Show print statements  |
| `-x`            | Exit on first failure  |
| `--pdb`         | Drop to debugger       |
| `--lf`          | Run last failed tests  |
| `--ff`          | Run failed tests first |
| `-k EXPRESSION` | Run matching tests     |
| `-m MARKER`     | Run marked tests       |
| `--cov=MODULE`  | Measure coverage       |

### Test Structure Template

```python
"""
tests/test_module.py

Tests for module functionality.
"""
import pytest
from scpi_control import Module


class TestModule:
    """Test suite for Module."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        # Arrange
        obj = Module()

        # Act
        result = obj.method()

        # Assert
        assert result is not None


    @pytest.mark.parametrize("input,expected", [
        (1, 2),
        (2, 4),
        (3, 6),
    ])
    def test_with_parameters(self, input, expected):
        """Test with multiple parameters."""
        assert Module.double(input) == expected


    def test_exception_handling(self):
        """Test exception handling."""
        with pytest.raises(ValueError):
            Module.invalid_operation()
```

## Next Steps

- [Building Guide](building.md) - Build and package the project
- [Project Structure](structure.md) - Understand the codebase
- [Contributing Guidelines](contributing.md) - How to contribute
- [API Reference](../api/oscilloscope.md) - API documentation
