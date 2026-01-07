# Contributing to Siglent Oscilloscope Control

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/SCPI-Instrument-Control.git
   cd SCPI-Instrument-Control
   ```
3. **Add the upstream repository**:
   ```bash
   git remote add upstream https://github.com/little-did-I-know/SCPI-Instrument-Control.git
   ```

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- (Optional) A Siglent oscilloscope for hardware testing

### Install Development Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package in editable mode with all dependencies
pip install -e ".[dev,gui,hdf5,fun,all]"
```

### Verify Installation

```bash
# Run tests
pytest tests/

# Check code style
black --check siglent/ tests/ examples/
flake8 siglent/

# Try importing the package
python -c "from scpi_control import Oscilloscope; print('Success!')"
```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes**: Fix issues in existing code
- **New features**: Add new functionality
- **Documentation**: Improve README, docstrings, or examples
- **Tests**: Add or improve test coverage
- **Examples**: Provide new usage examples
- **Model support**: Add support for new oscilloscope models

### Before Starting Work

1. **Check existing issues** to avoid duplicate work
2. **Create or comment on an issue** describing what you plan to do
3. **Wait for feedback** from maintainers (especially for large changes)
4. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```

## Coding Standards

### Python Style

- Follow **PEP 8** style guide
- Use **Black** formatter with 100 character line length:
  ```bash
  black --line-length 100 siglent/ tests/
  ```
- Use **type hints** for function signatures
- Write **clear docstrings** for modules, classes, and functions

### Code Quality

```bash
# Format code with Black
black siglent/ tests/ examples/

# Lint with flake8
flake8 siglent/ --max-line-length=100

# Type checking (optional but recommended)
mypy siglent/
```

### Docstring Format

Use Google-style docstrings:

```python
def measure_frequency(self, channel: int) -> float:
    """Measure the frequency of a signal on the specified channel.

    Args:
        channel: Channel number (1-4)

    Returns:
        Frequency in Hz

    Raises:
        ValueError: If channel is out of range
        ConnectionError: If oscilloscope is not connected

    Example:
        >>> scope = Oscilloscope('192.168.1.100')
        >>> scope.connect()
        >>> freq = scope.measure_frequency(1)
        >>> print(f"Frequency: {freq/1000:.2f} kHz")
    """
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=siglent --cov-report=term-missing

# Run specific test file
pytest tests/test_waveform_parsing.py

# Run with verbose output
pytest tests/ -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures for common setup
- Mock hardware when necessary

Example test:

```python
import pytest
from scpi_control import Oscilloscope

def test_channel_configuration():
    """Test channel configuration parsing."""
    # Your test code here
    pass

@pytest.fixture
def mock_scope():
    """Fixture providing a mock oscilloscope."""
    # Setup mock
    yield mock_scope
    # Teardown
```

### Test Coverage Goals

- Aim for **80%+ coverage** for new code
- All new features should include tests
- Bug fixes should include regression tests

## Pull Request Process

### 1. Prepare Your Changes

```bash
# Make sure you're up to date with upstream
git fetch upstream
git rebase upstream/main

# Run the pre-PR validation script (RECOMMENDED)
make pre-pr              # Full validation
# Or: python scripts/pre_pr_check.py
# Or: bash scripts/pre_pr_check.sh

# Alternative: Manual checks
pytest tests/
black siglent/ tests/ examples/
flake8 siglent/

# Commit your changes
git add .
git commit -m "Brief description of changes"
```

**💡 Pro Tip:** Use the pre-PR validation script before committing to catch issues early:

```bash
# Run full validation (recommended before creating PR)
make pre-pr

# Quick validation during development
make pre-pr-fast

# Auto-fix formatting issues
make pre-pr-fix

# Or run directly with options
python scripts/pre_pr_check.py --fast --fix
```

The pre-PR script checks:

- ✅ Code formatting (Black)
- ✅ Import sorting (isort)
- ✅ Linting (flake8)
- ✅ Security (bandit)
- ✅ Tests (pytest)
- ✅ Coverage
- ✅ Package build validation

### 2. Commit Message Format

Use clear, descriptive commit messages:

```
Add frequency measurement validation

- Add input validation for channel parameter
- Raise ValueError for invalid channel numbers
- Add unit tests for validation logic
- Update docstring with parameter constraints
```

### 3. Push and Create PR

```bash
# Push to your fork
git push origin feature/my-new-feature

# Go to GitHub and create a Pull Request
```

### 4. PR Requirements

Your pull request should:

- ✅ **Pass all CI checks** (tests, linting, build)
- ✅ **Include tests** for new functionality
- ✅ **Update documentation** if needed
- ✅ **Add changelog entry** in CHANGELOG.md
- ✅ **Have a clear description** of changes
- ✅ **Reference related issues** (e.g., "Fixes #123")

### 5. PR Description Template

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to not work as expected)
- [ ] Documentation update

## Testing

- [ ] Tests pass locally
- [ ] Added tests for new functionality
- [ ] Tested with real hardware (if applicable)

## Checklist

- [ ] Code follows style guidelines (Black, flake8)
- [ ] Self-reviewed code
- [ ] Commented complex code sections
- [ ] Updated documentation
- [ ] Added changelog entry
- [ ] No new warnings introduced
```

## Reporting Bugs

### Before Submitting a Bug Report

1. **Check existing issues** to avoid duplicates
2. **Test with the latest version** from main branch
3. **Gather information**:
   - Your Python version
   - Package version
   - Operating system
   - Oscilloscope model
   - Full error traceback

### Bug Report Template

Use the GitHub issue template or include:

````markdown
**Describe the bug**
Clear description of the problem

**To Reproduce**
Steps to reproduce:

1. Connect to scope at '...'
2. Call function '...'
3. See error

**Expected behavior**
What you expected to happen

**Actual behavior**
What actually happened

**Error message/traceback**

```python
Full traceback here
```
````

**Environment:**

- OS: [e.g., Windows 11, Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- Package version: [e.g., 0.2.5]
- Oscilloscope model: [e.g., SDS824X HD]

**Additional context**
Any other relevant information

````

## Suggesting Features

### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature

**Use Case**
Why is this feature needed? What problem does it solve?

**Proposed Solution**
How do you envision this working?

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Mock-ups, examples, or references
````

### Feature Development Process

1. **Submit feature request** as GitHub issue
2. **Discuss with maintainers** - wait for approval
3. **Design phase** - plan the implementation
4. **Implementation** - write code and tests
5. **Documentation** - update docs and examples
6. **Review** - submit PR and address feedback

### Experimental Features

For features that are innovative but need user feedback before stabilization:

**When to mark as experimental:**

- New hardware support (untested models)
- Novel functionality without proven use cases
- API designs that need validation
- Features requiring extensive real-world testing

**How to implement:**

- Use optional dependency groups: `[feature-name-beta]`
- Add module-level warnings: `warnings.warn(..., FutureWarning)`
- Mark with `@experimental` decorator for individual methods
- Document clearly in README and changelog
- Use pre-release versions: `0.x.0-alpha.1`, `0.x.0-beta.1`

**Full guide**: See [`docs/development/EXPERIMENTAL_FEATURES.md`](EXPERIMENTAL_FEATURES.md) for comprehensive instructions on:

- Marking features as experimental
- Version numbering strategies
- Testing requirements
- Documentation standards
- Graduation and deprecation process

**Example:**

```python
# siglent/power_supply.py (experimental module)
import warnings
warnings.warn(
    "siglent.power_supply is experimental. API may change.",
    FutureWarning
)
```

## Development Tips

### Hardware Testing

If you have a Siglent oscilloscope:

```python
# Create a test configuration
# tests/test_config.py
SCOPE_IP = "192.168.1.100"  # Your oscilloscope IP
SCOPE_MODEL = "SDS824X HD"

# Use in tests
@pytest.mark.hardware
def test_real_connection():
    """Test with real hardware (skip if not available)."""
    scope = Oscilloscope(SCOPE_IP)
    # Test code
```

Run hardware tests separately:

```bash
pytest -m hardware
```

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from scpi_control import Oscilloscope
scope = Oscilloscope('192.168.1.100')
# Debug output will show SCPI commands
```

### Adding New Models

To add support for a new oscilloscope model:

1. **Add model detection** in `siglent/models/capability.py`
2. **Add model-specific commands** if needed
3. **Test with actual hardware** if possible
4. **Update documentation** in README.md
5. **Add to supported models list**

## Documentation

### Updating Documentation

- **README.md**: User-facing documentation
- **Docstrings**: Code-level documentation
- **Examples**: Usage examples in `examples/`
- **API docs**: Function/class documentation

### Documentation Style

- Use clear, concise language
- Provide code examples
- Link to related documentation
- Keep up to date with code changes

## Community

### Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Email**: Contact maintainers for private matters

### Recognition

Contributors are recognized in:

- Git commit history
- GitHub contributors page
- Release notes (for significant contributions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Siglent Oscilloscope Control! 🎉
