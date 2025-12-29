"""GUI application entry point for Siglent oscilloscope control."""

import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def _require_gui_dependencies():
    """Import PyQt6 dependencies with a helpful error if missing."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
    except ModuleNotFoundError as exc:
        raise ImportError(
            "PyQt6 is required for the GUI. Install the GUI extras with:\n"
            '  pip install "Siglent-Oscilloscope[gui]"'
        ) from exc

    return QApplication, Qt


def main():
    """Main entry point for the GUI application."""
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
