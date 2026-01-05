# Building Standalone Executables

This guide explains how to build standalone executables for the Siglent Report Generator application.

## Prerequisites

### All Platforms

1. **Install Python 3.8+** with pip

2. **Install the package with all dependencies:**

   ```bash
   pip install -e ".[report-generator,build-exe]"
   ```

3. **Verify PyInstaller is installed:**
   ```bash
   pyinstaller --version
   ```

### Windows-Specific

- Windows 10/11 recommended
- Visual C++ Redistributable (usually already installed)

### Linux-Specific

- Install system dependencies for PyQt6:

  ```bash
  sudo apt-get install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
  ```

- For AppImage creation (optional):
  ```bash
  # Download appimagetool
  wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x appimagetool-x86_64.AppImage
  ```

## Building for Windows

### Method 1: Directory-based executable (Recommended)

This creates a folder with the executable and all dependencies:

```bash
# Navigate to project root
cd Siglent

# Build using the spec file
pyinstaller report-generator-windows.spec

# The executable will be in: dist/SiglentReportGenerator/
```

### Method 2: Single-file executable

To create a single `.exe` file (slower startup but easier to distribute):

1. Open `report-generator-windows.spec`
2. Uncomment the "one-file executable" section at the bottom
3. Comment out the `coll = COLLECT(...)` section
4. Build:
   ```bash
   pyinstaller report-generator-windows.spec
   ```

The single executable will be: `dist/SiglentReportGenerator.exe`

### Running the Windows executable

```bash
# Directory-based
cd dist/SiglentReportGenerator
./SiglentReportGenerator.exe

# Or just double-click SiglentReportGenerator.exe in File Explorer
```

### Creating an installer (Optional)

Use tools like:

- **Inno Setup** (free): https://jrsoftware.org/isinfo.php
- **NSIS** (free): https://nsis.sourceforge.io/
- **WiX Toolset** (free, creates .msi): https://wixtoolset.org/

## Building for Linux

### Method 1: Standard executable

```bash
# Navigate to project root
cd Siglent

# Build using the spec file
pyinstaller report-generator-linux.spec

# The executable will be in: dist/SiglentReportGenerator/
```

### Method 2: AppImage (Universal Linux Package)

AppImage is a portable format that works on most Linux distributions.

1. **Build the application:**

   ```bash
   pyinstaller report-generator-linux.spec
   ```

2. **Create AppDir structure:**

   ```bash
   # Create directory structure
   mkdir -p SiglentReportGenerator.AppDir/usr/bin
   mkdir -p SiglentReportGenerator.AppDir/usr/share/applications
   mkdir -p SiglentReportGenerator.AppDir/usr/share/icons/hicolor/256x256/apps

   # Copy the built application
   cp -r dist/SiglentReportGenerator/* SiglentReportGenerator.AppDir/usr/bin/

   # Create desktop entry
   cat > SiglentReportGenerator.AppDir/siglent-report-generator.desktop << 'EOF'
   [Desktop Entry]
   Type=Application
   Name=Siglent Report Generator
   Comment=Generate professional oscilloscope test reports
   Exec=SiglentReportGenerator
   Icon=siglent-report-generator
   Categories=Development;Science;Engineering;
   Terminal=false
   EOF

   # Create AppRun script
   cat > SiglentReportGenerator.AppDir/AppRun << 'EOF'
   #!/bin/bash
   SELF=$(readlink -f "$0")
   HERE=${SELF%/*}
   export PATH="${HERE}/usr/bin/:${PATH}"
   export LD_LIBRARY_PATH="${HERE}/usr/lib/:${LD_LIBRARY_PATH}"
   cd "${HERE}/usr/bin"
   exec "./SiglentReportGenerator" "$@"
   EOF

   chmod +x SiglentReportGenerator.AppDir/AppRun

   # Optional: Add icon (if you have one)
   # cp resources/icon.png SiglentReportGenerator.AppDir/siglent-report-generator.png
   # cp resources/icon.png SiglentReportGenerator.AppDir/usr/share/icons/hicolor/256x256/apps/siglent-report-generator.png
   ```

3. **Build AppImage:**

   ```bash
   # Using appimagetool
   ./appimagetool-x86_64.AppImage SiglentReportGenerator.AppDir SiglentReportGenerator-x86_64.AppImage

   # Make it executable
   chmod +x SiglentReportGenerator-x86_64.AppImage
   ```

4. **Run the AppImage:**
   ```bash
   ./SiglentReportGenerator-x86_64.AppImage
   ```

### Running the Linux executable

```bash
cd dist/SiglentReportGenerator
./SiglentReportGenerator
```

## Troubleshooting

### Missing dependencies error

If the executable fails with missing library errors:

**Windows:**

- Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe

**Linux:**

```bash
sudo apt-get install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
```

### "Failed to execute script" error

This usually means a hidden import is missing. To debug:

1. Open the spec file
2. Change `console=False` to `console=True`
3. Rebuild and run from terminal to see error messages
4. Add missing imports to the `hiddenimports` list

### Large executable size

The executable includes Python, PyQt6, matplotlib, and all dependencies. Typical sizes:

- **Windows directory build:** ~200-300 MB
- **Windows single-file:** ~250-350 MB
- **Linux directory build:** ~180-250 MB
- **Linux AppImage:** ~200-280 MB

To reduce size:

- Use UPX compression (already enabled)
- Remove unused dependencies from the spec file
- Consider using `--exclude-module` for large unused packages

### PyQt6 platform plugin errors

If you see "Could not find the Qt platform plugin":

**Windows:**

```bash
# Usually fixed by the spec file, but if needed:
set QT_QPA_PLATFORM_PLUGIN_PATH=<path-to-exe>/PyQt6/Qt6/plugins/platforms
```

**Linux:**

```bash
export QT_QPA_PLATFORM_PLUGIN_PATH=<path-to-exe>/PyQt6/Qt6/plugins/platforms
```

## Testing the Executable

After building, test all features:

1. **Launch the application**
2. **Import sample waveform file** (create one with examples/report_generation_example.py)
3. **Fill in metadata**
4. **Generate a PDF report** (if reportlab is included)
5. **Generate a Markdown report**
6. **Test LLM settings** (optional)
7. **Test chat sidebar** (optional, requires Ollama)

## Distribution

### Windows

Distribute either:

- The entire `dist/SiglentReportGenerator/` folder (users run the .exe inside)
- A single .exe file (if using one-file mode)
- An installer created with Inno Setup/NSIS

### Linux

Distribute either:

- The entire `dist/SiglentReportGenerator/` folder
- An AppImage file (recommended - works on most distros)
- A .deb or .rpm package (requires additional packaging)

### Important Notes

- **Include a README** with the executable explaining how to use it
- **List system requirements** (OS version, RAM, etc.)
- **Mention optional features** (LLM support requires Ollama/LM Studio)
- **Include license information** (MIT license from the project)

## CI/CD Automation

For automated builds using GitHub Actions or similar:

```yaml
# Example GitHub Actions workflow snippet
- name: Build Windows executable
  run: |
    pip install -e ".[report-generator,build-exe]"
    pyinstaller report-generator-windows.spec

- name: Upload artifact
  uses: actions/upload-artifact@v3
  with:
    name: SiglentReportGenerator-Windows
    path: dist/SiglentReportGenerator/
```

## Support

For build issues, please file an issue at:
https://github.com/little-did-I-know/Siglent-Oscilloscope/issues
