"""
Application entry point for the Report Generator.

Launch with:
    python -m siglent.report_generator.app

Or after installation:
    siglent-report-generator
"""

import sys

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from siglent.report_generator.main_window import MainWindow


def main():
    """Main application entry point."""
    # Set required Qt attributes BEFORE creating QApplication
    # This is required for QtWebEngine to work properly
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("Siglent Report Generator")
    app.setOrganizationName("Siglent")

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
