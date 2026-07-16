"""
Application entry point for the Report Generator.

Launch with:
    python -m scpi_control.report_generator.app

Or after installation:
    siglent-report-generator

Logging
-------
This module is the ONLY place in the report generator that configures a
logging sink (handlers/levels), and it does so only for the
"scpi_control.report_generator" logger tree - the rest of the library
(driver, GUI, server, protocol decoders) is left alone. Library modules
must keep doing just `logger = logging.getLogger(__name__)` and never
attach handlers of their own - that boundary is deliberate.

`_configure_logging()` attaches:
  - a StreamHandler, so a console/dev run shows log output (previously,
    with no handler configured anywhere, Python fell back to
    `logging.lastResort`, a WARNING-level stderr handler, which silently
    dropped every DEBUG message and produced nothing at all in the
    PyInstaller windowed build where `sys.stderr` is typically None).
  - a FileHandler writing into the same per-user config directory
    `AppSettings` already resolves (see
    `AppSettings.get_settings_file()` in
    `scpi_control/report_generator/models/app_settings.py`), so the frozen
    app persists errors somewhere the user can actually find them. If the
    log file can't be opened (read-only directory, permissions, ...), we
    fall back to the stream handler alone rather than block startup.

Level defaults to INFO. Set the SCPI_REPORT_DEBUG environment variable
(any non-empty value) to raise verbosity to DEBUG, which surfaces the
Ollama connect diagnostics, prompt dumps, and PDF-generation progress
that used to be plain print() calls.
"""

import logging
import os
import sys

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from scpi_control.report_generator.main_window import MainWindow
from scpi_control.report_generator.models.app_settings import AppSettings

_logging_configured = False


def _configure_logging() -> None:
    """
    Attach a console + file logging sink to the "scpi_control.report_generator"
    logger tree.

    Safe to call more than once - only the first call has any effect, so
    calling main() twice (e.g. in tests) does not stack duplicate handlers.
    """
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    level = logging.DEBUG if os.environ.get("SCPI_REPORT_DEBUG") else logging.INFO

    pkg_logger = logging.getLogger("scpi_control.report_generator")
    pkg_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    pkg_logger.addHandler(stream_handler)

    try:
        log_dir = AppSettings.get_settings_file().parent
        log_file = log_dir / "report_generator.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        pkg_logger.addHandler(file_handler)
    except Exception:
        # A read-only directory or permissions issue here must not prevent
        # the app from launching - fall back to the stream handler alone.
        pkg_logger.warning("Could not open log file for writing; logging to console only.", exc_info=True)


def main():
    """Main application entry point."""
    _configure_logging()

    # Set required Qt attributes BEFORE creating QApplication
    # This is required for QtWebEngine to work properly
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("SCPI Report Generator")
    app.setOrganizationName("SCPI Instrument Control")

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
