# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Siglent Oscilloscope GUI application.

This file defines how to build standalone executables for Windows, macOS, and Linux.
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Get version from package or environment
def get_version():
    """Get version from siglent package or environment variable."""
    # Try environment variable first (set by CI)
    version = os.environ.get('APP_VERSION')
    if version:
        return version.lstrip('v')  # Remove 'v' prefix if present

    # Try importing from package
    try:
        import siglent
        return siglent.__version__
    except:
        return "0.0.0"

APP_VERSION = get_version()
print(f"Building version: {APP_VERSION}")

# Determine platform-specific settings
is_windows = sys.platform.startswith('win')
is_macos = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

# Icon file paths (create these in resources/ directory)
if is_windows:
    icon_file = 'resources/siglent-icon.ico'
elif is_macos:
    icon_file = 'resources/siglent-icon.icns'
else:
    icon_file = None  # Linux doesn't use icon in executable

# Check if icon exists, otherwise set to None
if icon_file and not Path(icon_file).exists():
    print(f"Warning: Icon file not found: {icon_file}")
    icon_file = None

a = Analysis(
    ['siglent/gui/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include README and LICENSE in distribution
        ('README.md', '.'),
        ('LICENSE', '.'),
        # Uncomment if you add resource files (images, etc.)
        # ('resources', 'resources'),
    ],
    hiddenimports=[
        # Core dependencies
        'numpy',
        'matplotlib',
        'matplotlib.backends.backend_qt5agg',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'scipy.io',
        # PyQt6 modules
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.sip',
        # PyQtGraph
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.exporters',
        # Optional dependencies
        'h5py',
        'shapely',
        'PIL',
        'PIL.Image',
        'svgpathtools',
        # Siglent package modules
        'siglent',
        'siglent.gui',
        'siglent.gui.widgets',
        'siglent.gui.utils',
        'siglent.protocol_decoders',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SiglentGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX (reduces file size by ~30%)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# macOS-specific: Create .app bundle
if is_macos:
    app = BUNDLE(
        exe,
        name='SiglentGUI.app',
        icon=icon_file,
        bundle_identifier='com.siglent.oscilloscope-gui',
        info_plist={
            'CFBundleName': 'Siglent Oscilloscope',
            'CFBundleDisplayName': 'Siglent Oscilloscope Control',
            'CFBundleVersion': APP_VERSION,
            'CFBundleShortVersionString': APP_VERSION,
            'NSHighResolutionCapable': 'True',
            'LSMinimumSystemVersion': '10.13.0',
        },
    )
