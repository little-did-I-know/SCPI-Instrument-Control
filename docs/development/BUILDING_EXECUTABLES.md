# Building Standalone Executables

This guide explains how to build standalone executables for the Siglent Oscilloscope GUI application that can run without Python installed.

## Overview

The project uses [PyInstaller](https://pyinstaller.org/) to create standalone executables for:

- **Windows**: `.exe` executable
- **macOS**: `.app` application bundle
- **Linux**: Binary executable

These executables bundle Python and all dependencies, allowing users to run the GUI without installing Python.

## Quick Start

### Local Build (Current Platform)

Build an executable for your current operating system:

```bash
# Using Make (recommended)
make build-exe

# Or using Python script directly
python scripts/build_executable.py
```

The executable will be created in the `dist/` directory.

### Automated Builds (All Platforms)

The project includes a GitHub Actions workflow that automatically builds executables for all platforms when you push a version tag:

```bash
# Create and push a version tag
git tag v0.3.2
git push origin v0.3.2
```

This will:
1. Build executables for Windows, macOS, and Linux
2. Create release archives (.zip for Windows/macOS, .tar.gz for Linux)
3. Upload to GitHub Releases automatically

## Prerequisites

### For Local Builds

1. **Install the package with all dependencies:**
   ```bash
   pip install -e ".[all]"
   ```

2. **Install PyInstaller:**
   ```bash
   pip install ".[build-exe]"
   # or directly:
   pip install pyinstaller
   ```

3. **Create application icons** (optional but recommended):
   - Windows: `resources/siglent-icon.ico`
   - macOS: `resources/siglent-icon.icns`
   - Linux: Icons not embedded in binary

See [Creating Application Icons](#creating-application-icons) below.

## Building Methods

### Method 1: Using Make (Recommended)

```bash
# Build for current platform
make build-exe

# Clean build artifacts first
make build-exe-clean
make build-exe

# Build and test the executable
make build-exe-test
```

### Method 2: Using Build Script

```bash
# Basic build
python scripts/build_executable.py

# Clean and build
python scripts/build_executable.py --clean

# Build and test
python scripts/build_executable.py --test

# Build and create distribution archive
python scripts/build_executable.py --archive
```

### Method 3: Using PyInstaller Directly

```bash
# Build using the spec file
pyinstaller --clean siglent-gui.spec
```

## Build Artifacts

After building, you'll find:

### Windows
```
dist/
└── SiglentGUI.exe          # ~150-250 MB single executable
```

### macOS
```
dist/
└── SiglentGUI.app/         # Application bundle
    └── Contents/
        ├── MacOS/
        │   └── SiglentGUI  # Actual executable
        ├── Resources/
        └── Info.plist
```

### Linux
```
dist/
└── SiglentGUI              # ~150-250 MB binary
```

## Distribution

### Creating Release Archives

The build script can create distributable archives:

```bash
python scripts/build_executable.py --archive
```

This creates:
- **Windows**: `SiglentGUI-v0.3.1-Windows-x64.zip`
- **macOS**: `SiglentGUI-v0.3.1-macOS-arm64.zip`
- **Linux**: `SiglentGUI-v0.3.1-Linux-x86_64.tar.gz`

Each archive includes:
- The executable/app
- README.md
- LICENSE

### Automated Release Process

When you push a version tag (e.g., `v0.3.2`), GitHub Actions will:

1. Build executables on Windows, macOS, and Linux runners
2. Create platform-specific archives
3. Upload to GitHub Releases
4. Add installation instructions to the release notes

**To trigger a release:**

```bash
# Ensure your code is committed
git add .
git commit -m "Release v0.3.2"

# Create and push tag
git tag v0.3.2
git push origin main
git push origin v0.3.2
```

Then check the "Actions" tab on GitHub to monitor the build progress.

## Creating Application Icons

Application icons make your executable look professional and identifiable.

### Icon Requirements

- **Windows (.ico)**: Multi-resolution, recommended sizes: 16x16, 32x32, 48x48, 256x256
- **macOS (.icns)**: Multi-resolution, recommended sizes: 16x16 to 1024x1024
- **Linux**: Icons are typically not embedded; use desktop file instead

### Creating Icons from PNG

1. **Create a high-resolution PNG** (1024x1024 or larger) with your logo/icon

2. **Convert to .ico (Windows):**

   Using online tools:
   - https://convertio.co/png-ico/
   - https://www.icoconverter.com/

   Or using ImageMagick:
   ```bash
   convert icon.png -define icon:auto-resize=256,128,64,48,32,16 siglent-icon.ico
   ```

3. **Convert to .icns (macOS):**

   Using `iconutil` (macOS only):
   ```bash
   # Create iconset directory
   mkdir siglent-icon.iconset

   # Create different sizes
   sips -z 16 16     icon.png --out siglent-icon.iconset/icon_16x16.png
   sips -z 32 32     icon.png --out siglent-icon.iconset/icon_16x16@2x.png
   sips -z 32 32     icon.png --out siglent-icon.iconset/icon_32x32.png
   sips -z 64 64     icon.png --out siglent-icon.iconset/icon_32x32@2x.png
   sips -z 128 128   icon.png --out siglent-icon.iconset/icon_128x128.png
   sips -z 256 256   icon.png --out siglent-icon.iconset/icon_128x128@2x.png
   sips -z 256 256   icon.png --out siglent-icon.iconset/icon_256x256.png
   sips -z 512 512   icon.png --out siglent-icon.iconset/icon_256x256@2x.png
   sips -z 512 512   icon.png --out siglent-icon.iconset/icon_512x512.png
   sips -z 1024 1024 icon.png --out siglent-icon.iconset/icon_512x512@2x.png

   # Convert to icns
   iconutil -c icns siglent-icon.iconset
   ```

   Or use online tools:
   - https://cloudconvert.com/png-to-icns
   - https://iconverticons.com/online/

4. **Place icons in resources directory:**
   ```
   resources/
   ├── siglent-icon.ico    # Windows
   └── siglent-icon.icns   # macOS
   ```

### Icon Design Tips

- Use simple, recognizable designs (works well at small sizes)
- Include the Siglent logo or oscilloscope imagery
- Use high contrast colors
- Test at multiple sizes (16x16 to 512x512)
- Save with transparent background (PNG/ICNS)

## Configuration

### PyInstaller Spec File

The build configuration is in `siglent-gui.spec`. Key settings:

```python
# Executable name
exe = EXE(
    ...
    name='SiglentGUI',              # Output name
    console=False,                   # No console window (GUI app)
    icon='resources/siglent-icon.ico'  # Application icon
)

# Hidden imports (add modules that PyInstaller misses)
hiddenimports=[
    'PyQt6',
    'pyqtgraph',
    'numpy',
    # ... more
]

# Excluded modules (reduce size)
excludes=[
    'tkinter',   # Don't need Tkinter
    'pytest',    # Don't need test framework
]
```

### Customizing the Build

To modify the build:

1. Edit `siglent-gui.spec`
2. Add/remove hidden imports
3. Include additional data files
4. Change executable name or icon

Then rebuild:
```bash
make build-exe
```

## Troubleshooting

### Build Fails with Missing Modules

**Problem:** PyInstaller can't find a module

**Solution:** Add to `hiddenimports` in `siglent-gui.spec`:
```python
hiddenimports=[
    'missing_module_name',
]
```

### Executable is Too Large

**Problem:** Executable is 400+ MB

**Solutions:**
- Add unused modules to `excludes` list
- Enable UPX compression (already enabled)
- Use folder distribution instead of single file

### Executable Won't Start

**Problem:** Executable crashes on startup

**Solutions:**
- Check console output (run from terminal)
- Test on clean machine without Python installed
- Verify all dependencies are included

**Windows:** Run from Command Prompt to see errors:
```cmd
dist\SiglentGUI.exe
```

**macOS:** Check Console app for crash logs

**Linux:** Run from terminal:
```bash
./dist/SiglentGUI
```

### Icon Not Showing

**Problem:** Executable doesn't show custom icon

**Solutions:**
- Verify icon files exist in `resources/` directory
- Check icon file format (.ico for Windows, .icns for macOS)
- Rebuild after adding icons
- On Windows, icon cache may need refresh (restart Explorer)

### macOS "App is Damaged" Error

**Problem:** macOS Gatekeeper blocks unsigned app

**Solution:** Users need to right-click → Open the first time

For developers: Code sign the app (requires Apple Developer account):
```bash
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/SiglentGUI.app
```

### Antivirus False Positives

**Problem:** Windows Defender flags executable as malware

**Solutions:**
- This is common with PyInstaller executables
- Code sign the executable (requires certificate)
- Submit to Microsoft for analysis
- Users can add exception in their antivirus

## Testing Executables

### Local Testing

1. **Build the executable:**
   ```bash
   make build-exe
   ```

2. **Test on your development machine:**
   ```bash
   # Windows
   dist\SiglentGUI.exe

   # macOS
   open dist/SiglentGUI.app

   # Linux
   ./dist/SiglentGUI
   ```

3. **Test on clean VM/machine without Python:**
   - Use VirtualBox, VMware, or physical machine
   - Verify no Python installation needed
   - Test all GUI features

### Automated Testing

The GitHub Actions workflow includes basic checks:
- Verifies executable was created
- Checks file size (should be 100-300 MB)
- Validates archive creation

## File Size Optimization

Typical executable sizes:
- **Minimal**: ~100 MB (core GUI only)
- **Standard**: ~150-200 MB (all features)
- **Maximum**: ~250-300 MB (all optional features)

To reduce size:

1. **Exclude unused modules in spec file:**
   ```python
   excludes=['tkinter', 'IPython', 'jupyter', 'pytest']
   ```

2. **Remove optional dependencies:**
   - Comment out unused items in `hiddenimports`

3. **Use UPX compression** (already enabled):
   ```python
   upx=True,
   ```

4. **Use folder distribution** instead of single file (faster startup):
   - Edit spec file: change `exe = EXE(...)` parameters
   - Remove single-file mode

## Release Checklist

Before creating a release with executables:

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md`
- [ ] Test locally on current platform
- [ ] Create application icons (if not done)
- [ ] Commit all changes
- [ ] Create and push version tag
- [ ] Monitor GitHub Actions build
- [ ] Test downloaded executables from release
- [ ] Update release notes if needed

## Advanced Topics

### Code Signing

For production releases, code signing prevents security warnings:

**Windows:**
- Requires code signing certificate (from DigiCert, Sectigo, etc.)
- Use SignTool.exe
- Cost: $100-400/year

**macOS:**
- Requires Apple Developer account ($99/year)
- Use `codesign` and `notarytool`
- Necessary for Gatekeeper approval

**Linux:**
- Generally not required
- Can use GPG signatures for packages

### Creating Installers

For professional distribution:

**Windows:**
- Inno Setup (free)
- NSIS (free)
- WiX Toolset (free)

**macOS:**
- DMG canvas (paid)
- `hdiutil` (built-in, free)
- `.pkg` installer

**Linux:**
- AppImage
- Flatpak
- Snap package
- .deb / .rpm packages

## Additional Resources

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [PyQt6 Deployment Guide](https://www.riverbankcomputing.com/static/Docs/PyQt6/deployment.html)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Getting Help

If you encounter issues building executables:

1. Check this documentation
2. Review [PyInstaller troubleshooting](https://pyinstaller.org/en/stable/when-things-go-wrong.html)
3. Search existing [GitHub Issues](https://github.com/little-did-I-know/Siglent-Oscilloscope/issues)
4. Create a new issue with:
   - Your OS and Python version
   - Full error message
   - Build command used
   - PyInstaller version
