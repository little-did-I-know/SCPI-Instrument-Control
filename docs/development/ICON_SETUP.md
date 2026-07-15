# Executable Icon Configuration

This document describes how the application icons are configured for different platforms when building standalone executables with PyInstaller.

## Icon Files

All PyInstaller spec files use the "Test Equipment" icon set in `resources/`:

- **Windows**: `resources/Test Equipment.ico`
- **macOS**: `resources/Test Equipment.icns`
- **Linux**: `resources/Test Equipment.png`

## Configured Executables

### 1. GUI Application (`siglent-gui.spec`)

**Icons Configured**:
- Windows: `resources/Test Equipment.ico`
- macOS: `resources/Test Equipment.icns` (for the .app bundle)
- Linux: no icon embedded (Linux doesn't support icons in bare executables)

**Build Command**:
```bash
pyinstaller siglent-gui.spec
# or: make build-exe
```

**Output**:
- Windows: `dist/SiglentGUI.exe` with embedded icon
- macOS: `dist/SiglentGUI.app` with icon in bundle
- Linux: `dist/SiglentGUI` (no embedded icon)

---

### 2. Report Generator - Windows (`report-generator-windows.spec`)

**Icons Configured**:
- Windows: `resources/Test Equipment.ico`

**Build Command**:
```bash
pyinstaller report-generator-windows.spec
```

**Output**:
- `dist/SiglentReportGenerator/SiglentReportGenerator.exe` with embedded icon

**Icon Locations in the spec**:
- Main executable's `icon=` argument (COLLECT-based build)
- A commented-out one-file executable variant also sets `icon=`

---

### 3. Report Generator - Linux (`report-generator-linux.spec`)

**Icons Configured**:
- PNG icon bundled in resources for AppImage/desktop integration
- Icon copied into the AppDir for Linux desktop entries

**Build Command**:
```bash
pyinstaller report-generator-linux.spec
```

**Output**:
- `dist/SiglentReportGenerator/SiglentReportGenerator` (no embedded icon)
- Icon bundled at `resources/Test Equipment.png` for desktop integration

**AppImage Integration**:
The AppDir-building section of the spec:
- Copies the icon to the AppDir root: `shutil.copy('resources/Test Equipment.png', appdir / 'siglent-report-generator.png')`
- Writes a desktop entry with `Icon=siglent-report-generator`

---

## Icon File Requirements

### Windows (.ico)
- **Format**: ICO (Windows Icon)
- **Sizes**: Multiple resolutions (16x16, 32x32, 48x48, 256x256 recommended)
- **Used By**: PyInstaller EXE on Windows

### macOS (.icns)
- **Format**: ICNS (Apple Icon Image)
- **Sizes**: Multiple resolutions up to 1024x1024
- **Used By**: PyInstaller .app bundle on macOS
- **Requirements**: Must contain at least 512x512@2x for Retina displays

### Linux (.png)
- **Format**: PNG
- **Recommended Size**: 256x256 or 512x512
- **Used By**: Desktop files, AppImage, window managers

---

## Testing the Icons

### Windows
1. Build the executable:
   ```bash
   pyinstaller siglent-gui.spec
   # or
   pyinstaller report-generator-windows.spec
   ```
2. Check the icon:
   - View `dist/` in File Explorer — the .exe should show the "Test Equipment" icon
   - Right-click → Properties → check icon in dialog
   - Run the .exe and check the taskbar icon

### macOS
1. Build the application: `pyinstaller siglent-gui.spec`
2. Check the icon:
   - Open `dist/` in Finder — the .app bundle should show the "Test Equipment" icon
   - Right-click → Get Info → check icon preview
   - Run the app and check the Dock icon

### Linux
1. Build the executable:
   ```bash
   pyinstaller siglent-gui.spec
   # or
   pyinstaller report-generator-linux.spec
   ```
2. For desktop integration:
   - Create a `.desktop` file in `~/.local/share/applications/`
   - Set `Icon=/path/to/resources/Test Equipment.png`
   - The application will use this icon in launchers and menus

---

## Troubleshooting

### Icon Not Appearing on Windows

**Problem**: .exe shows the default Python icon instead of the custom icon

**Solutions**:
1. Verify the icon file exists: `ls resources/Test\ Equipment.ico`
2. Rebuild with verbose output: `pyinstaller --clean siglent-gui.spec`
3. Check the spec file has the correct icon path
4. Ensure the icon file is a valid ICO (not just a renamed PNG)

### Icon Not Appearing on macOS

**Problem**: .app bundle shows a generic document icon

**Solutions**:
1. Verify the ICNS file exists: `ls resources/Test\ Equipment.icns`
2. Rebuild with: `pyinstaller --clean siglent-gui.spec`
3. Clear the icon cache: `sudo rm -rf /Library/Caches/com.apple.iconservices.store`
4. Restart Finder: `killall Finder`
5. Ensure the ICNS has the required resolutions (512x512@2x minimum)

### AppImage Icon Not Appearing on Linux

**Problem**: AppImage doesn't show an icon in the launcher

**Solutions**:
1. Verify the PNG is copied to the AppDir root
2. Check the desktop file has the correct `Icon=` entry
3. Ensure the icon filename matches (no spaces or special characters)
4. Update the desktop database: `update-desktop-database ~/.local/share/applications/`

---

## Icon in Application Code (PyQt6)

To use the icon within the running application (window title bar, about dialogs, etc.):

```python
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
import sys
from pathlib import Path

app = QApplication(sys.argv)

# Get icon path (works in both dev and bundled executable)
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    base_path = Path(sys._MEIPASS)
else:
    # Running in development
    base_path = Path(__file__).parent.parent

# Set application icon
icon_path = base_path / 'resources' / 'Test Equipment.ico'
if icon_path.exists():
    app.setWindowIcon(QIcon(str(icon_path)))

# Or set on a specific window
from PyQt6.QtWidgets import QMainWindow
window = QMainWindow()
window.setWindowIcon(QIcon(str(icon_path)))
```

**Note**: for bundled executables, the icon must also be included in `datas` in the spec file:

```python
datas=[
    ('resources/Test Equipment.ico', 'resources'),
    ('resources/Test Equipment.png', 'resources'),
],
```

---

## Build Automation

For the GUI, `make build-exe` wraps `pyinstaller --clean siglent-gui.spec` and picks the icon automatically via the spec's platform check. The report-generator specs don't have Make targets yet — invoke `pyinstaller` on the relevant `.spec` file directly, as shown above.

---

## Related Files

- `siglent-gui.spec` - GUI application build configuration
- `report-generator-windows.spec` - Windows report generator build
- `report-generator-linux.spec` - Linux report generator build
- `resources/Test Equipment.ico` - Windows icon
- `resources/Test Equipment.icns` - macOS icon
- `resources/Test Equipment.png` - Linux/web icon
- `MANIFEST.in` - Ensures icons are included in source distributions
