# PyPI Deployment Guide

This guide explains how to build and upload the Siglent package to PyPI.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/
2. **TestPyPI Account** (optional, recommended for testing): https://test.pypi.org/
3. **API Token**: Generate an API token from your PyPI account settings

## Installation of Build Tools

```bash
pip install build twine
```

Or if you installed the dev dependencies:

```bash
pip install -e ".[dev]"
```

## Building the Package

### 1. Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info
```

### 2. Build the Distribution

```bash
python -m build
```

This creates two files in the `dist/` directory:

- `siglent-0.1.0.tar.gz` (source distribution)
- `siglent-0.1.0-py3-none-any.whl` (wheel distribution)

### 3. Check the Build

```bash
twine check dist/*
```

This verifies that the package description will render properly on PyPI.

## Testing on TestPyPI (Recommended)

Before uploading to the real PyPI, test on TestPyPI:

### 1. Upload to TestPyPI

```bash
twine upload --repository testpypi dist/*
```

You'll be prompted for:

- Username: `__token__`
- Password: Your TestPyPI API token (including the `pypi-` prefix)

### 2. Test Installation from TestPyPI

```bash
# Create a fresh virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ siglent
```

Note: `--extra-index-url` is needed because dependencies (PyQt6, numpy, matplotlib) are on the regular PyPI.

### 3. Test the Installation

```python
# Test import
from scpi_control import Oscilloscope
print(Oscilloscope.__module__)

# Test GUI command
# siglent-gui
```

## Uploading to PyPI

Once you've verified everything works on TestPyPI:

### 1. Upload to PyPI

```bash
twine upload dist/*
```

You'll be prompted for:

- Username: `__token__`
- Password: Your PyPI API token (including the `pypi-` prefix)

### 2. Verify Upload

Visit https://pypi.org/project/siglent/ to see your package page.

### 3. Test Installation

```bash
pip install siglent
```

## Using API Tokens

For security, use API tokens instead of username/password:

### Create `.pypirc` File

Create `~/.pypirc` (Linux/Mac) or `%USERPROFILE%\.pypirc` (Windows):

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-testpypi-api-token-here
```

Then you can upload without being prompted:

```bash
twine upload --repository testpypi dist/*
twine upload dist/*
```

## Version Updates

When releasing a new version:

### 1. Update Version Number

Edit `pyproject.toml`:

```toml
[project]
name = "siglent"
version = "0.2.0"  # Update this
```

Also update in `siglent/__init__.py`:

```python
__version__ = "0.2.0"
```

### 2. Update Changelog

Create a `CHANGELOG.md` file to track changes between versions.

### 3. Create Git Tag (Optional)

```bash
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

### 4. Rebuild and Upload

```bash
rm -rf dist/ build/ *.egg-info
python -m build
twine check dist/*
twine upload dist/*
```

## Checklist Before Upload

- [ ] All tests pass
- [ ] Version number updated in `pyproject.toml` and `__init__.py`
- [ ] README.md is up to date
- [ ] CHANGELOG.md updated (if using)
- [ ] LICENSE file present
- [ ] Examples are included and working
- [ ] Built package passes `twine check`
- [ ] Tested on TestPyPI
- [ ] Git repository is clean (all changes committed)
- [ ] Created git tag for version

## Troubleshooting

### Common Issues

**"File already exists"**

- You're trying to upload the same version twice
- PyPI doesn't allow overwriting releases
- Increment the version number

**"Invalid distribution file"**

- Clean build artifacts: `rm -rf dist/ build/ *.egg-info`
- Rebuild: `python -m build`

**"Package description failed to render"**

- Run `twine check dist/*` to see the issue
- Usually a syntax error in README.md
- Fix and rebuild

**Import errors after installation**

- Check that all dependencies are listed in `pyproject.toml`
- Verify package structure with `pip show siglent`

## Resources

- PyPI: https://pypi.org/
- TestPyPI: https://test.pypi.org/
- Packaging Tutorial: https://packaging.python.org/tutorials/packaging-projects/
- Twine Documentation: https://twine.readthedocs.io/
