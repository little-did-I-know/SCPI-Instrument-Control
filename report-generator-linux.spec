# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Siglent Report Generator - Linux

This spec file builds a standalone Linux executable for the
Siglent Report Generator application.

Usage:
    pyinstaller report-generator-linux.spec

The executable will be created in dist/SiglentReportGenerator/

Note: On Linux, you may need to install system dependencies:
    - libxcb-xinerama0 (for PyQt6)
    - libxcb-cursor0 (for PyQt6)
    - libxkbcommon-x11-0 (for PyQt6)

Install with:
    sudo apt-get install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# Collect all data files and submodules for dependencies
datas = []
hiddenimports = []

# PyQt6 data files
datas += collect_data_files('PyQt6')

# Matplotlib data files (fonts, etc.)
datas += collect_data_files('matplotlib')

# reportlab fonts and resources
datas += collect_data_files('reportlab')

# PIL/Pillow data
datas += collect_data_files('PIL')

# Hidden imports for PyQt6
hiddenimports += collect_submodules('PyQt6')

# Hidden imports for matplotlib backends
hiddenimports += [
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_agg',
]

# Hidden imports for reportlab
hiddenimports += [
    'reportlab.pdfgen',
    'reportlab.lib',
    'reportlab.platypus',
]

# Hidden imports for PIL
hiddenimports += collect_submodules('PIL')

# NumPy and SciPy
hiddenimports += [
    'numpy',
    'scipy',
    'scipy.special',
    'scipy.linalg',
]

# Requests and urllib
hiddenimports += [
    'requests',
    'urllib3',
]

# Analysis
a = Analysis(
    ['scpi_control/report_generator/app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'tkinter',
        'PyQt6.QtWebEngine',  # Not needed for report generator
        'pyqtgraph',  # Not needed for report generator
        'IPython',
        'jupyter',
        'notebook',
    ],
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SiglentReportGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SiglentReportGenerator',
)

# Optional: Create an AppImage-ready directory structure
# This creates a directory structure compatible with AppImage tools
"""
import shutil
from pathlib import Path

# Create AppDir structure
appdir = Path('dist/SiglentReportGenerator.AppDir')
appdir.mkdir(exist_ok=True)

# Copy executable
shutil.copytree('dist/SiglentReportGenerator', appdir / 'usr/bin', dirs_exist_ok=True)

# Create desktop file
desktop_content = '''[Desktop Entry]
Type=Application
Name=Siglent Report Generator
Comment=Generate professional oscilloscope test reports
Exec=SiglentReportGenerator
Icon=siglent-report-generator
Categories=Development;Science;
Terminal=false
'''

(appdir / 'siglent-report-generator.desktop').write_text(desktop_content)

# Create AppRun script
apprun_content = '''#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin/:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib/:${LD_LIBRARY_PATH}"
cd "${HERE}/usr/bin"
exec "./SiglentReportGenerator" "$@"
'''

apprun_path = appdir / 'AppRun'
apprun_path.write_text(apprun_content)
apprun_path.chmod(0o755)

print(f"AppDir created at: {appdir}")
print("To create AppImage, use: appimagetool SiglentReportGenerator.AppDir")
"""
