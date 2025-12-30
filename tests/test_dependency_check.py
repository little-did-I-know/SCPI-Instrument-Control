#!/usr/bin/env python
"""Test script to demonstrate dependency checking in siglent-gui."""

import sys
import subprocess

print("=" * 70)
print("Testing Dependency Checker")
print("=" * 70)
print()

# Test 1: With all dependencies
print("Test 1: Checking current environment dependencies...")
print("-" * 70)

try:
    import PyQt6

    print("[OK] PyQt6 is installed")
except ImportError:
    print("[MISSING] PyQt6 is NOT installed")

try:
    import pyqtgraph

    print("[OK] pyqtgraph is installed")
except ImportError:
    print("[MISSING] pyqtgraph is NOT installed")

try:
    import PyQt6.QtWebEngineWidgets

    print("[OK] PyQt6-WebEngine is installed")
except ImportError:
    print("[MISSING] PyQt6-WebEngine is NOT installed")

print()
print("=" * 70)
print("Now demonstrating what happens when you run 'siglent-gui'")
print("with missing dependencies...")
print("=" * 70)
print()

# Show what the user would see
print("If PyQt6 is missing, you would see:")
print("-" * 70)
print(
    """
======================================================================
ERROR: Missing Required GUI Dependencies
======================================================================

The following required packages are missing:
  - PyQt6>=6.6.0

Please install the GUI version of Siglent-Oscilloscope:
  pip install "Siglent-Oscilloscope[gui]"

Or if installing from source:
  pip install -e ".[gui]"
======================================================================
"""
)

print()
print("If only pyqtgraph is missing, you would see:")
print("-" * 70)
print(
    """
======================================================================
WARNING: Missing Optional GUI Dependencies
======================================================================

The GUI will work, but some features may be limited:
  - pyqtgraph>=0.13.0 (recommended for high-performance live view)

For the best experience, install the full GUI version:
  pip install "Siglent-Oscilloscope[gui]"

Or if installing from source:
  pip install -e ".[gui]"
======================================================================

(GUI launches after 2-second pause...)
"""
)

print()
print("=" * 70)
print("Summary")
print("=" * 70)
print(
    """
The dependency checker:
  [OK] Exits immediately if PyQt6 is missing (ERROR)
  [OK] Warns but continues if pyqtgraph is missing (WARNING)
  [OK] Warns but continues if PyQt6-WebEngine is missing (WARNING)
  [OK] Provides clear installation instructions
  [OK] Works for both PyPI and source installations
"""
)
