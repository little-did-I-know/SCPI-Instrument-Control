"""Detailed error dialog widget for displaying user-friendly error messages.

This module provides an error dialog that shows both user-friendly summaries
and expandable technical details for debugging.
"""

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

logger = logging.getLogger(__name__)


class DetailedErrorDialog(QDialog):
    """Shows user-friendly error messages with expandable technical details.

    This dialog provides two levels of information:
    1. User-friendly summary for non-technical users
    2. Technical details (stack trace, context) for debugging

    Example:
        >>> error_info = {
        ...     'type': 'TimeoutError',
        ...     'message': 'Timeout acquiring waveform from CH1',
        ...     'details': 'Socket timeout after 5.0 seconds',
        ...     'context': {'channel': 1, 'operation': 'get_waveform'},
        ...     'traceback': '...'
        ... }
        >>> dialog = DetailedErrorDialog(error_info, parent=main_window)
        >>> dialog.exec()
    """

    def __init__(self, error_info: dict, parent=None):
        """Initialize the error dialog.

        Args:
            error_info: Dictionary containing error details:
                - type: Error type name (e.g., 'TimeoutError')
                - message: User-friendly error message
                - details: Additional error details (optional)
                - context: Dictionary of context info (optional)
                - traceback: Stack trace string (optional)
                - timestamp: Error timestamp (optional, defaults to now)
            parent: Parent widget
        """
        super().__init__(parent)
        self.error_info = error_info
        self.setWindowTitle("Error Occurred")
        self.resize(500, 300)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()

        # Header with icon and error type
        header_layout = QHBoxLayout()

        # Error icon (using standard warning icon)
        icon_label = QLabel()
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxCritical)
        icon_label.setPixmap(icon.pixmap(48, 48))
        header_layout.addWidget(icon_label)

        # Error type and time
        error_type = self.error_info.get("type", "Error")
        timestamp = self.error_info.get("timestamp", datetime.now())
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = str(timestamp)

        type_label = QLabel(f"<b>{error_type}</b><br><small>{timestamp_str}</small>")
        header_layout.addWidget(type_label, stretch=1)

        layout.addLayout(header_layout)

        # User-friendly message
        message = self.error_info.get("message", "An error occurred")
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("QLabel { padding: 10px; }")
        layout.addWidget(message_label)

        # "Show Details" toggle button
        self.details_button = QPushButton("Show Details")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_button)

        # Technical details text area (initially hidden)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setFont(QApplication.font("QFontDatabase.FixedFont"))
        self.details_text.hide()

        # Build detailed text content
        details_content = []

        # Error details
        if "details" in self.error_info and self.error_info["details"]:
            details_content.append(f"Details: {self.error_info['details']}")

        # Context information
        if "context" in self.error_info and self.error_info["context"]:
            details_content.append("\nContext:")
            for key, value in self.error_info["context"].items():
                details_content.append(f"  {key}: {value}")

        # Stack trace
        if "traceback" in self.error_info and self.error_info["traceback"]:
            details_content.append(f"\nStack Trace:\n{self.error_info['traceback']}")

        if not details_content:
            details_content.append("No additional details available.")

        self.details_text.setPlainText("\n".join(details_content))
        layout.addWidget(self.details_text)

        # Buttons
        button_box = QDialogButtonBox()

        # Copy to Clipboard button
        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self._copy_to_clipboard)
        button_box.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)

        # Close button
        close_button = button_box.addButton(QDialogButtonBox.StandardButton.Close)
        close_button.clicked.connect(self.accept)

        layout.addWidget(button_box)

        self.setLayout(layout)

    def _toggle_details(self, checked: bool):
        """Toggle visibility of technical details.

        Args:
            checked: True to show details, False to hide
        """
        if checked:
            self.details_text.show()
            self.details_button.setText("Hide Details")
            self.resize(self.width(), 500)  # Expand dialog
        else:
            self.details_text.hide()
            self.details_button.setText("Show Details")
            self.resize(self.width(), 300)  # Shrink dialog

    def _copy_to_clipboard(self):
        """Copy full error details to clipboard."""
        clipboard = QApplication.clipboard()

        # Build comprehensive error report
        report_lines = [
            "=" * 60,
            "ERROR REPORT",
            "=" * 60,
            f"Type: {self.error_info.get('type', 'Unknown')}",
            f"Time: {self.error_info.get('timestamp', datetime.now())}",
            "",
            "Message:",
            self.error_info.get("message", "No message"),
            "",
        ]

        if "details" in self.error_info and self.error_info["details"]:
            report_lines.append("Details:")
            report_lines.append(self.error_info["details"])
            report_lines.append("")

        if "context" in self.error_info and self.error_info["context"]:
            report_lines.append("Context:")
            for key, value in self.error_info["context"].items():
                report_lines.append(f"  {key}: {value}")
            report_lines.append("")

        if "traceback" in self.error_info and self.error_info["traceback"]:
            report_lines.append("Stack Trace:")
            report_lines.append(self.error_info["traceback"])
            report_lines.append("")

        report_lines.append("=" * 60)

        clipboard.setText("\n".join(report_lines))

        # Update button text briefly to confirm
        sender = self.sender()
        if isinstance(sender, QPushButton):
            original_text = sender.text()
            sender.setText("Copied!")
            # Reset after 2 seconds
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(2000, lambda: sender.setText(original_text))


def show_error_dialog(error_info: dict, parent=None) -> int:
    """Convenience function to show an error dialog.

    Args:
        error_info: Dictionary containing error details (see DetailedErrorDialog)
        parent: Parent widget

    Returns:
        Dialog result code (typically QDialog.DialogCode.Accepted)

    Example:
        >>> show_error_dialog({
        ...     'type': 'ConnectionError',
        ...     'message': 'Failed to connect to oscilloscope',
        ...     'details': 'Connection refused on port 5024'
        ... })
    """
    dialog = DetailedErrorDialog(error_info, parent)
    return dialog.exec()
