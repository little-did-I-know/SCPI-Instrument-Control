# Siglent Oscilloscope Control - Test Suite

This directory contains the test suite for the Siglent Oscilloscope Control application.

## Running Tests

### Install Test Dependencies

First, ensure pytest is installed:

```bash
pip install pytest
```

### Run All Tests

From the project root directory:

```bash
pytest tests/ -v
```

### Run Specific Test Files

```bash
# Import tests
pytest tests/test_imports.py -v

# GUI initialization tests
pytest tests/test_gui_initialization.py -v

# Protocol decoder tests
pytest tests/test_protocol_decoders.py -v

# Math operations tests
pytest tests/test_math_operations.py -v
```

### Run Tests with Coverage

Install coverage first:

```bash
pip install pytest-cov
```

Then run:

```bash
pytest tests/ --cov=siglent --cov-report=html
```

View coverage report by opening `htmlcov/index.html` in a browser.

## Test Organization

### `test_imports.py`
- Tests that all modules can be imported without errors
- Catches AttributeError, ImportError, and other initialization issues
- Fast smoke tests to verify basic package integrity

### `test_gui_initialization.py`
- Tests GUI widget creation and initialization order
- Verifies MainWindow initialization doesn't have AttributeErrors
- Ensures all required widgets are created properly
- Catches initialization order issues (like waveform_display creation)

### `test_protocol_decoders.py`
- Tests protocol decoder creation and configuration
- Verifies required channels and parameters
- Tests event clearing and basic functionality

### `test_math_operations.py`
- Tests mathematical operations on waveforms
- Verifies addition, subtraction, multiplication, division
- Tests integration, differentiation, scaling, offset
- Ensures math channel creation and expression handling

## Writing New Tests

When adding new functionality, please add corresponding tests:

1. **For new modules**: Add import test in `test_imports.py`
2. **For new GUI widgets**: Add initialization test in `test_gui_initialization.py`
3. **For new decoders**: Add tests in `test_protocol_decoders.py`
4. **For new math operations**: Add tests in `test_math_operations.py`

### Test Template

```python
import pytest

def test_your_feature():
    """Test description."""
    # Arrange
    # ... setup code ...

    # Act
    # ... code to test ...

    # Assert
    assert result is not None
    assert expected == actual
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines. They require:
- Python 3.8+
- All dependencies from `pyproject.toml`
- QApplication instance for GUI tests (provided by pytest fixtures)

## Known Issues

- GUI tests require a display server (X11, Wayland, or Xvfb for headless)
- Some tests may need mock oscilloscope connections for full coverage
- Protocol decoder tests use synthetic waveforms, not real hardware captures
