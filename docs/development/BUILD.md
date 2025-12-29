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

# Or install the built package locally (after running `python -m build`)
# Bash / WSL
pip install dist/*.whl

# Windows PowerShell (keep the pip upgrade separate so globbing works)
python -m pip install --upgrade pip
python -m pip install (Get-ChildItem dist\*.whl)

# Windows Command Prompt (cmd.exe)
for %f in (dist\*.whl) do python -m pip install --upgrade pip "%f"
```

## Expected Output

After `python -m build`, you should see:
```
dist/
├── siglent_oscilloscope-0.1.0.tar.gz
└── siglent_oscilloscope-0.1.0-py3-none-any.whl
```

If you see an error like `Invalid wheel filename (wrong number of parts): '*'` or
`Requirement 'dist/*.whl' looks like a filename, but the file does not exist`, it
usually means:

1. The `dist/` directory is empty because `python -m build` has not been run.
2. The shell (especially PowerShell) did not expand the `dist/*.whl` glob. Use the
   PowerShell example above so pip receives the actual wheel file path.

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
