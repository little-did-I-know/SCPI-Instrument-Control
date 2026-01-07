# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Siglent Report Generator - Windows

This spec file builds a standalone Windows executable (.exe) for the
Siglent Report Generator application.

Usage:
    pyinstaller report-generator-windows.spec

The executable will be created in dist/SiglentReportGenerator/
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
        # Exclude ML/AI frameworks - not needed for LLM HTTP API calls
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'tensorboard',
        'jax',
        'transformers',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
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
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: 'resources/icon.ico'
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

# Optional: Create a one-file executable instead
# Uncomment the following to create a single .exe file:
"""
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SiglentReportGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
"""
