"""GUI application entry point for Siglent oscilloscope control."""

import logging
import sys
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def _check_gui_dependencies():
    """Check GUI dependencies and provide helpful installation instructions.

    Raises:
        ImportError: If required dependencies (PyQt6) are missing

    Warnings:
        Warns about missing optional dependencies (PyQtGraph, PyQt6-WebEngine)
    """
    missing_required = []
    missing_optional = []

    # Check required dependencies
    try:
        import PyQt6
    except ImportError:
        missing_required.append("PyQt6>=6.6.0")

    # Check optional but recommended dependencies
    try:
        import pyqtgraph
    except ImportError:
        missing_optional.append("pyqtgraph>=0.13.0 (recommended for high-performance live view)")

    try:
        import PyQt6.QtWebEngineWidgets
    except ImportError:
        missing_optional.append("PyQt6-WebEngine>=6.6.0 (recommended for VNC display)")

    # Handle missing required dependencies
    if missing_required:
        print("\n" + "=" * 70)
        print("ERROR: Missing Required GUI Dependencies")
        print("=" * 70)
        print("\nThe following required packages are missing:")
        for pkg in missing_required:
            print(f"  - {pkg}")
        print("\nPlease install the GUI version of Siglent-Oscilloscope:")
        print('  pip install "Siglent-Oscilloscope[gui]"')
        print("\nOr if installing from source:")
        print('  pip install -e ".[gui]"')
        print("=" * 70 + "\n")
        sys.exit(1)

    # Warn about missing optional dependencies
    if missing_optional:
        print("\n" + "=" * 70)
        print("WARNING: Missing Optional GUI Dependencies")
        print("=" * 70)
        print("\nThe GUI will work, but some features may be limited:")
        for pkg in missing_optional:
            print(f"  - {pkg}")
        print("\nFor the best experience, install the full GUI version:")
        print('  pip install "Siglent-Oscilloscope[gui]"')
        print("\nOr if installing from source:")
        print('  pip install -e ".[gui]"')
        print("=" * 70 + "\n")

        # Give user a moment to read the warning
        import time

        time.sleep(2)


def _require_gui_dependencies():
    """Import PyQt6 dependencies with a helpful error if missing."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        raise ImportError("PyQt6 is required for the GUI. Install the GUI extras with:\n" '  pip install "Siglent-Oscilloscope[gui]"') from exc

    return QApplication, Qt


def main():
    """Main entry point for the GUI application."""
    # Check dependencies and show helpful messages
    _check_gui_dependencies()

    QApplication, Qt = _require_gui_dependencies()

    from siglent.gui.main_window import MainWindow

    # Enable OpenGL context sharing for QtWebEngine (required for VNC window)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Siglent Oscilloscope Control")
    app.setOrganizationName("Siglent")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    logger.info("Starting Siglent Oscilloscope Control GUI")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
