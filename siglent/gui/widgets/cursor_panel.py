"""Cursor control panel for waveform measurements."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QRadioButton, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class CursorPanel(QWidget):
    """Widget for controlling measurement cursors and displaying cursor values.

    Provides controls for cursor mode selection and displays cursor measurements
    including time, voltage, and delta values.

    Signals:
        cursor_mode_changed: Emitted when cursor mode changes (mode: str)
        clear_cursors: Emitted when clear cursors button is clicked
    """

    cursor_mode_changed = pyqtSignal(str)
    clear_cursors = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize cursor panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_mode = "off"

        self._init_ui()
        logger.info("Cursor panel initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Cursor mode selection
        mode_group = self._create_mode_group()
        layout.addWidget(mode_group)

        # Cursor values display
        values_group = self._create_values_group()
        layout.addWidget(values_group)

        layout.addStretch()

    def _create_mode_group(self) -> QGroupBox:
        """Create cursor mode selection group.

        Returns:
            Mode selection group box
        """
        group = QGroupBox("Cursor Mode")
        layout = QVBoxLayout(group)

        # Create button group for exclusive selection
        self.mode_button_group = QButtonGroup(self)

        # Mode radio buttons
        self.off_radio = QRadioButton("Off")
        self.off_radio.setChecked(True)
        self.off_radio.toggled.connect(lambda checked: self._on_mode_changed("off") if checked else None)
        self.mode_button_group.addButton(self.off_radio)
        layout.addWidget(self.off_radio)

        self.vertical_radio = QRadioButton("Vertical (Time)")
        self.vertical_radio.toggled.connect(lambda checked: self._on_mode_changed("vertical") if checked else None)
        self.mode_button_group.addButton(self.vertical_radio)
        layout.addWidget(self.vertical_radio)

        self.horizontal_radio = QRadioButton("Horizontal (Voltage)")
        self.horizontal_radio.toggled.connect(lambda checked: self._on_mode_changed("horizontal") if checked else None)
        self.mode_button_group.addButton(self.horizontal_radio)
        layout.addWidget(self.horizontal_radio)

        self.both_radio = QRadioButton("Both")
        self.both_radio.toggled.connect(lambda checked: self._on_mode_changed("both") if checked else None)
        self.mode_button_group.addButton(self.both_radio)
        layout.addWidget(self.both_radio)

        # Clear button
        clear_btn = QPushButton("Clear All Cursors")
        clear_btn.clicked.connect(self._on_clear_cursors)
        layout.addWidget(clear_btn)

        return group

    def _create_values_group(self) -> QGroupBox:
        """Create cursor values display group.

        Returns:
            Values display group box
        """
        group = QGroupBox("Cursor Measurements")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        # Cursor 1 (X1/Y1)
        layout.addWidget(QLabel("<b>Cursor 1:</b>"), 0, 0, 1, 2)

        layout.addWidget(QLabel("Time (X1):"), 1, 0)
        self.x1_label = QLabel("--")
        self.x1_label.setStyleSheet("color: #FFD700;")  # Yellow
        layout.addWidget(self.x1_label, 1, 1)

        layout.addWidget(QLabel("Voltage (Y1):"), 2, 0)
        self.y1_label = QLabel("--")
        self.y1_label.setStyleSheet("color: #FFD700;")
        layout.addWidget(self.y1_label, 2, 1)

        # Cursor 2 (X2/Y2)
        layout.addWidget(QLabel("<b>Cursor 2:</b>"), 3, 0, 1, 2)

        layout.addWidget(QLabel("Time (X2):"), 4, 0)
        self.x2_label = QLabel("--")
        self.x2_label.setStyleSheet("color: #00CED1;")  # Cyan
        layout.addWidget(self.x2_label, 4, 1)

        layout.addWidget(QLabel("Voltage (Y2):"), 5, 0)
        self.y2_label = QLabel("--")
        self.y2_label.setStyleSheet("color: #00CED1;")
        layout.addWidget(self.y2_label, 5, 1)

        # Delta measurements
        layout.addWidget(QLabel("<b>Delta (Δ):</b>"), 6, 0, 1, 2)

        layout.addWidget(QLabel("ΔTime (X2-X1):"), 7, 0)
        self.delta_time_label = QLabel("--")
        self.delta_time_label.setStyleSheet("color: #FF1493;")  # Magenta
        layout.addWidget(self.delta_time_label, 7, 1)

        layout.addWidget(QLabel("ΔVoltage (Y2-Y1):"), 8, 0)
        self.delta_voltage_label = QLabel("--")
        self.delta_voltage_label.setStyleSheet("color: #FF1493;")
        layout.addWidget(self.delta_voltage_label, 8, 1)

        layout.addWidget(QLabel("Frequency (1/ΔT):"), 9, 0)
        self.frequency_label = QLabel("--")
        self.frequency_label.setStyleSheet("color: #00FF00;")  # Green
        layout.addWidget(self.frequency_label, 9, 1)

        # Instructions
        instruction_label = QLabel("<i>Click on waveform to place cursors.<br>" "Drag to move. Right-click to remove.<br>" "ESC to clear all.</i>")
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #888888; font-size: 9pt;")
        layout.addWidget(instruction_label, 10, 0, 1, 2)

        return group

    def _on_mode_changed(self, mode: str):
        """Handle cursor mode change.

        Args:
            mode: New cursor mode ('off', 'vertical', 'horizontal', 'both')
        """
        self.current_mode = mode
        logger.info(f"Cursor mode changed to: {mode}")
        self.cursor_mode_changed.emit(mode)

        # Clear values when switching modes
        if mode == "off":
            self.clear_values()

    def _on_clear_cursors(self):
        """Handle clear cursors button click."""
        logger.info("Clear cursors requested")
        self.clear_cursors.emit()
        self.clear_values()

    def set_mode(self, mode: str):
        """Set cursor mode programmatically.

        Args:
            mode: Cursor mode ('off', 'vertical', 'horizontal', 'both')
        """
        mode = mode.lower()
        if mode == "off":
            self.off_radio.setChecked(True)
        elif mode == "vertical":
            self.vertical_radio.setChecked(True)
        elif mode == "horizontal":
            self.horizontal_radio.setChecked(True)
        elif mode == "both":
            self.both_radio.setChecked(True)

    def update_cursor_values(
        self,
        x1: Optional[float] = None,
        y1: Optional[float] = None,
        x2: Optional[float] = None,
        y2: Optional[float] = None,
    ):
        """Update cursor value displays.

        Args:
            x1: Cursor 1 X position (time)
            y1: Cursor 1 Y position (voltage)
            x2: Cursor 2 X position (time)
            y2: Cursor 2 Y position (voltage)
        """
        # Update cursor 1
        if x1 is not None:
            self.x1_label.setText(self._format_time(x1))
        else:
            self.x1_label.setText("--")

        if y1 is not None:
            self.y1_label.setText(self._format_voltage(y1))
        else:
            self.y1_label.setText("--")

        # Update cursor 2
        if x2 is not None:
            self.x2_label.setText(self._format_time(x2))
        else:
            self.x2_label.setText("--")

        if y2 is not None:
            self.y2_label.setText(self._format_voltage(y2))
        else:
            self.y2_label.setText("--")

        # Calculate and update deltas
        if x1 is not None and x2 is not None:
            delta_time = x2 - x1
            self.delta_time_label.setText(self._format_time(delta_time))

            # Calculate frequency (1/ΔT) if ΔT is not zero
            if abs(delta_time) > 1e-15:
                frequency = 1.0 / abs(delta_time)
                self.frequency_label.setText(self._format_frequency(frequency))
            else:
                self.frequency_label.setText("∞")
        else:
            self.delta_time_label.setText("--")
            self.frequency_label.setText("--")

        if y1 is not None and y2 is not None:
            delta_voltage = y2 - y1
            self.delta_voltage_label.setText(self._format_voltage(delta_voltage))
        else:
            self.delta_voltage_label.setText("--")

    def clear_values(self):
        """Clear all cursor value displays."""
        self.x1_label.setText("--")
        self.y1_label.setText("--")
        self.x2_label.setText("--")
        self.y2_label.setText("--")
        self.delta_time_label.setText("--")
        self.delta_voltage_label.setText("--")
        self.frequency_label.setText("--")

    def _format_time(self, time: float) -> str:
        """Format time value with appropriate unit.

        Args:
            time: Time in seconds

        Returns:
            Formatted time string
        """
        abs_time = abs(time)
        sign = "-" if time < 0 else ""

        if abs_time < 1e-9:
            return f"{sign}{abs_time*1e12:.3f} ps"
        elif abs_time < 1e-6:
            return f"{sign}{abs_time*1e9:.3f} ns"
        elif abs_time < 1e-3:
            return f"{sign}{abs_time*1e6:.3f} µs"
        elif abs_time < 1:
            return f"{sign}{abs_time*1e3:.3f} ms"
        else:
            return f"{sign}{abs_time:.3f} s"

    def _format_voltage(self, voltage: float) -> str:
        """Format voltage value with appropriate unit.

        Args:
            voltage: Voltage in volts

        Returns:
            Formatted voltage string
        """
        abs_voltage = abs(voltage)
        sign = "-" if voltage < 0 else ""

        if abs_voltage < 1e-3:
            return f"{sign}{abs_voltage*1e6:.3f} µV"
        elif abs_voltage < 1:
            return f"{sign}{abs_voltage*1e3:.3f} mV"
        else:
            return f"{sign}{abs_voltage:.3f} V"

    def _format_frequency(self, frequency: float) -> str:
        """Format frequency value with appropriate unit.

        Args:
            frequency: Frequency in Hz

        Returns:
            Formatted frequency string
        """
        if frequency < 1e3:
            return f"{frequency:.3f} Hz"
        elif frequency < 1e6:
            return f"{frequency/1e3:.3f} kHz"
        elif frequency < 1e9:
            return f"{frequency/1e6:.3f} MHz"
        else:
            return f"{frequency/1e9:.3f} GHz"
