"""Terminal widget for sending custom SCPI commands to the oscilloscope."""

import logging
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class TerminalWidget(QWidget):
    """Terminal widget for sending custom SCPI commands.

    Provides a console-like interface for sending raw SCPI commands
    to the oscilloscope and viewing responses.
    """

    command_sent = pyqtSignal(str, str)  # command, response

    def __init__(self, parent=None):
        """Initialize terminal widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._scope = None
        self._command_history = []
        self._history_index = -1

        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel("Send custom SCPI commands to the oscilloscope. " "Use '?' for queries (e.g., '*IDN?'). Press Up/Down for command history.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        layout.addWidget(info_label)

        # Splitter for output and examples
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Output display
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)

        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_layout.addWidget(output_label)

        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Courier New", 9))
        self.output_display.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px;
            }
        """
        )
        output_layout.addWidget(self.output_display)

        splitter.addWidget(output_widget)

        # Examples section
        examples_widget = QWidget()
        examples_layout = QVBoxLayout(examples_widget)
        examples_layout.setContentsMargins(0, 0, 0, 0)

        examples_label = QLabel("Common Commands:")
        examples_label.setStyleSheet("font-weight: bold;")
        examples_layout.addWidget(examples_label)

        self.examples_display = QTextEdit()
        self.examples_display.setReadOnly(True)
        self.examples_display.setFont(QFont("Courier New", 8))
        self.examples_display.setMaximumHeight(150)
        self.examples_display.setHtml(
            """
        <style>
            body { font-family: 'Courier New'; font-size: 9pt; }
            .cmd { color: #4ec9b0; font-weight: bold; }
            .desc { color: #666; }
        </style>
        <p><span class="cmd">*IDN?</span> <span class="desc">- Get device identification</span></p>
        <p><span class="cmd">C1:VDIV?</span> <span class="desc">- Get channel 1 voltage scale</span></p>
        <p><span class="cmd">C1:VDIV 1V</span> <span class="desc">- Set channel 1 to 1V/div</span></p>
        <p><span class="cmd">TDIV?</span> <span class="desc">- Get timebase scale</span></p>
        <p><span class="cmd">TRIG_MODE?</span> <span class="desc">- Get trigger mode</span></p>
        <p><span class="cmd">TRIG_MODE AUTO</span> <span class="desc">- Set trigger to AUTO mode</span></p>
        <p><span class="cmd">C1:TRA?</span> <span class="desc">- Get channel 1 trace on/off</span></p>
        <p><span class="cmd">C1:TRA ON</span> <span class="desc">- Enable channel 1</span></p>
        """
        )
        examples_layout.addWidget(self.examples_display)

        splitter.addWidget(examples_widget)
        splitter.setSizes([300, 150])

        layout.addWidget(splitter)

        # Input section
        input_layout = QHBoxLayout()

        # Timestamp checkbox
        self.timestamp_checkbox = QCheckBox("Timestamp")
        self.timestamp_checkbox.setChecked(True)
        input_layout.addWidget(self.timestamp_checkbox)

        # Command input
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter SCPI command here (e.g., *IDN?)")
        self.command_input.returnPressed.connect(self._on_send_command)
        self.command_input.setFont(QFont("Courier New", 10))
        self.command_input.setStyleSheet(
            """
            QLineEdit {
                padding: 6px;
                border: 2px solid #4CAF50;
                border-radius: 3px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #45a049;
            }
        """
        )

        # Enable Up/Down arrow keys for history
        self.command_input.keyPressEvent = self._handle_key_press

        input_layout.addWidget(self.command_input, 1)

        # Send button
        send_button = QPushButton("Send")
        send_button.clicked.connect(self._on_send_command)
        send_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """
        )
        input_layout.addWidget(send_button)

        # Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._on_clear_output)
        clear_button.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 6px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
        """
        )
        input_layout.addWidget(clear_button)

        layout.addLayout(input_layout)

        # Welcome message
        self._append_output("=== SCPI Terminal Ready ===", "#4CAF50")
        self._append_output("Connect to oscilloscope to send commands", "#888")
        self._append_output("")

    def set_oscilloscope(self, scope):
        """Set the oscilloscope instance.

        Args:
            scope: Oscilloscope instance
        """
        self._scope = scope
        if scope:
            self._append_output("=== Oscilloscope Connected ===", "#4CAF50")
            self._append_output("")
        else:
            self._append_output("=== Oscilloscope Disconnected ===", "#f44336")
            self._append_output("")

    def _handle_key_press(self, event):
        """Handle key press events for command history navigation.

        Args:
            event: QKeyEvent
        """
        if event.key() == Qt.Key.Key_Up:
            # Navigate up in history
            if self._command_history and self._history_index < len(self._command_history) - 1:
                self._history_index += 1
                self.command_input.setText(self._command_history[-(self._history_index + 1)])
        elif event.key() == Qt.Key.Key_Down:
            # Navigate down in history
            if self._history_index > 0:
                self._history_index -= 1
                self.command_input.setText(self._command_history[-(self._history_index + 1)])
            elif self._history_index == 0:
                self._history_index = -1
                self.command_input.clear()
        else:
            # Default key handling
            QLineEdit.keyPressEvent(self.command_input, event)

    def _on_send_command(self):
        """Handle send command button click."""
        command = self.command_input.text().strip()

        if not command:
            return

        if not self._scope or not self._scope.is_connected:
            self._append_output("ERROR: Not connected to oscilloscope", "#f44336")
            return

        # Add to history
        if not self._command_history or self._command_history[-1] != command:
            self._command_history.append(command)
        self._history_index = -1  # Reset history index

        # Display command
        timestamp = ""
        if self.timestamp_checkbox.isChecked():
            timestamp = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] "

        self._append_output(f"{timestamp}> {command}", "#569cd6")

        try:
            # Check if it's a query command
            if "?" in command:
                # Query command - expects response
                logger.info(f"Sending query: {command}")
                response = self._scope.query(command)
                self._append_output(f"  {response}", "#4ec9b0")
                self.command_sent.emit(command, response)
            else:
                # Write command - no response expected
                logger.info(f"Sending command: {command}")
                self._scope.write(command)
                self._append_output("  OK", "#4CAF50")
                self.command_sent.emit(command, "OK")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Command failed: {error_msg}")
            self._append_output(f"  ERROR: {error_msg}", "#f44336")
            self.command_sent.emit(command, f"ERROR: {error_msg}")

        # Clear input
        self.command_input.clear()

        # Scroll to bottom
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output_display.setTextCursor(cursor)

    def _on_clear_output(self):
        """Clear the output display."""
        self.output_display.clear()
        self._append_output("=== Output Cleared ===", "#888")
        self._append_output("")

    def _append_output(self, text: str, color: str = "#d4d4d4"):
        """Append text to output display with color.

        Args:
            text: Text to append
            color: HTML color code
        """
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<span style="color: {color};">{text}</span><br>')
        self.output_display.setTextCursor(cursor)

    def send_command(self, command: str):
        """Programmatically send a command.

        Args:
            command: SCPI command to send
        """
        self.command_input.setText(command)
        self._on_send_command()
