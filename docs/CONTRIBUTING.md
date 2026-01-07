# Contributing to Siglent Oscilloscope Control

Thank you for your interest in contributing to this project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

This project follows a code of conduct that all contributors are expected to adhere to:

- **Be respectful**: Treat all contributors with respect and consideration
- **Be collaborative**: Work together and help each other
- **Be professional**: Focus on technical merit and constructive feedback
- **Be inclusive**: Welcome contributors from all backgrounds

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- A Siglent SD824x HD oscilloscope (for testing hardware interactions)
- Network access to the oscilloscope

### Useful Knowledge

- Python programming
- SCPI protocol basics
- PyQt6 for GUI development
- NumPy for data processing
- Matplotlib for plotting

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/siglent-control/siglent.git
cd siglent
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install in development mode**

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode with development dependencies.

4. **Verify installation**

```bash
python -c "from scpi_control import Oscilloscope; print('Success!')"
```

5. **Build and validate distributions (for releases)**

```bash
python -m build
twine check dist/*
```

Running `twine check` confirms that the built wheel and sdist include all package data (such as type information) and that the README renders correctly on PyPI.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:

- **Clear title**: Summarize the problem
- **Description**: Detailed description of the bug
- **Steps to reproduce**: List the steps to reproduce the issue
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: Python version, OS, oscilloscope model
- **Code sample**: Minimal code to reproduce (if applicable)

### Suggesting Enhancements

For feature requests or enhancements:

- Check if the feature already exists or is planned
- Create an issue describing the enhancement
- Explain the use case and benefits
- Provide examples if possible

### Pull Requests

1. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**
   - Write clear, documented code
   - Follow the coding standards (see below)
   - Add tests if applicable
   - Update documentation

3. **Commit your changes**

```bash
git add .
git commit -m "Add feature: brief description"
```

Use clear, descriptive commit messages:

- Start with a verb (Add, Fix, Update, Remove, etc.)
- Keep the first line under 50 characters
- Add details in the body if needed

4. **Push to your fork**

```bash
git push origin feature/your-feature-name
```

5. **Create a Pull Request**
   - Go to the repository on GitHub
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template with details

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use [Black](https://github.com/psf/black) for code formatting (line length: 100)
- Use meaningful variable and function names
- Add type hints where appropriate

### Code Formatting

Run Black before committing:

```bash
black siglent/ examples/
```

Check with flake8:

```bash
flake8 siglent/ --max-line-length=100
```

### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include examples in docstrings where helpful
- Update README.md if adding new features

Example docstring:

```python
def measure_frequency(self, channel: int) -> float:
    """Measure frequency on a channel.

    Args:
        channel: Channel number (1-4)

    Returns:
        Frequency in Hz

    Raises:
        InvalidParameterError: If channel number is invalid
        CommandError: If measurement fails

    Example:
        >>> scope = Oscilloscope('192.168.1.100')
        >>> scope.connect()
        >>> freq = scope.measurement.measure_frequency(1)
        >>> print(f"Frequency: {freq/1e6:.3f} MHz")
    """
```

### Import Organization

Organize imports in this order:

1. Standard library imports
2. Third-party imports
3. Local application imports

Use absolute imports for clarity.

### Error Handling

- Use custom exceptions from `siglent.exceptions`
- Provide clear error messages
- Log errors appropriately
- Don't silently catch exceptions

### Testing

While the project doesn't currently have automated tests, consider:

- Testing your changes with actual hardware
- Providing test scripts if adding new features
- Documenting how to test your changes

## Project Structure

```
siglent/
├── siglent/              # Main package
│   ├── __init__.py      # Package exports
│   ├── oscilloscope.py  # Main API
│   ├── channel.py       # Channel control
│   ├── trigger.py       # Trigger control
│   ├── waveform.py      # Waveform acquisition
│   ├── measurement.py   # Measurements
│   ├── exceptions.py    # Custom exceptions
│   ├── connection/      # Connection layer
│   └── gui/             # GUI application
├── examples/            # Example scripts
├── tests/               # Tests (future)
└── docs/                # Documentation (future)
```

## Areas for Contribution

### High Priority

- Additional oscilloscope model support
- Automated testing framework
- Improved error handling and validation
- Performance optimizations

### Medium Priority

- Additional GUI features (channel controls, trigger widget)
- More measurement types
- Advanced trigger modes (pulse, video, pattern)
- Waveform math operations

### Documentation

- More examples
- Video tutorials
- API reference documentation
- Troubleshooting guide

### Testing

- Unit tests for core functionality
- Integration tests with hardware
- GUI testing
- CI/CD pipeline setup

## Questions?

If you have questions:

- Check existing issues and documentation
- Create a new issue with the "question" label
- Be specific and provide context

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions help make this project better for everyone. We appreciate your time and effort!
