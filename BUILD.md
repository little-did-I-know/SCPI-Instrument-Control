# Quick Build Instructions

## Build for PyPI

```bash
# 1. Install build tools (if not already installed)
pip install build twine

# 2. Clean previous builds
rm -rf dist/ build/ *.egg-info

# 3. Build the package
python -m build

# 4. Check the package
twine check dist/*

# 5. (Optional) Test upload to TestPyPI
twine upload --repository testpypi dist/*

# 6. Upload to PyPI
twine upload dist/*
```

## Test Local Installation

```bash
# Install in editable mode for development
pip install -e .

# Or install the built package locally
pip install dist/siglent_oscilloscope-0.1.0-py3-none-any.whl
```

## Expected Output

After `python -m build`, you should see:
```
dist/
├── siglent_oscilloscope-0.1.0.tar.gz
└── siglent_oscilloscope-0.1.0-py3-none-any.whl
```

Note: PyPI normalizes "Siglent-Oscilloscope" to "siglent_oscilloscope" in filenames.

## Verify Package Contents

```bash
# View wheel contents
unzip -l dist/siglent_oscilloscope-0.1.0-py3-none-any.whl

# Or use tar for source distribution
tar -tzf dist/siglent_oscilloscope-0.1.0.tar.gz
```

## Quick Test

```python
# After installation
python -c "from siglent import Oscilloscope; print(Oscilloscope.__version__)"

# Test GUI command
siglent-gui --help
```
