"""Measurement panel widget for oscilloscope GUI."""

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from siglent import Oscilloscope

logger = logging.getLogger(__name__)


class MeasurementPanel(QWidget):
    """Widget for displaying and controlling measurements."""

    # Available measurements
    MEASUREMENTS = [
        ("Frequency", "frequency"),
        ("Period", "period"),
        ("Peak-to-Peak", "vpp"),
        ("Amplitude", "amplitude"),
        ("Top", "top"),
        ("Base", "base"),
        ("Max", "maximum"),
        ("Min", "minimum"),
        ("Mean", "mean"),
        ("RMS", "rms"),
        ("Rise Time", "rise_time"),
        ("Fall Time", "fall_time"),
        ("Positive Width", "positive_width"),
        ("Negative Width", "negative_width"),
        ("Duty Cycle", "duty_cycle"),
    ]

    # Channels
    CHANNELS = ["C1", "C2", "C3", "C4"]

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize measurement panel widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.scope: Optional[Oscilloscope] = None
        self.active_measurements: List[Dict] = []
        self.auto_update = False
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_measurements)
        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Add measurement controls
        add_group = QGroupBox("Add Measurement")
        add_layout = QHBoxLayout(add_group)

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(self.CHANNELS)
        add_layout.addWidget(QLabel("Channel:"))
        add_layout.addWidget(self.channel_combo)

        self.measurement_combo = QComboBox()
        for name, _ in self.MEASUREMENTS:
            self.measurement_combo.addItem(name)
        add_layout.addWidget(QLabel("Type:"))
        add_layout.addWidget(self.measurement_combo)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add_measurement)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_group)

        # Measurement table
        results_group = QGroupBox("Active Measurements")
        results_layout = QVBoxLayout(results_group)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Channel", "Measurement", "Value", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        results_layout.addWidget(self.table)

        layout.addWidget(results_group)

        # Control buttons
        controls_layout = QHBoxLayout()

        self.update_btn = QPushButton("Update Now")
        self.update_btn.clicked.connect(self._update_measurements)
        controls_layout.addWidget(self.update_btn)

        self.auto_update_btn = QPushButton("Auto Update: OFF")
        self.auto_update_btn.setCheckable(True)
        self.auto_update_btn.toggled.connect(self._on_auto_update_toggled)
        controls_layout.addWidget(self.auto_update_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_all)
        controls_layout.addWidget(clear_btn)

        layout.addLayout(controls_layout)

        # Info label
        info_label = QLabel(
            "<b>Tips:</b><br>" "• Add measurements to track specific parameters<br>" "• Enable Auto Update to continuously refresh values<br>" "• Remove measurements by clicking the 'X' button"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { font-size: 9pt; color: #888; }")
        layout.addWidget(info_label)

        layout.addStretch()

    def set_scope(self, scope: Optional[Oscilloscope]):
        """Set the oscilloscope instance.

        Args:
            scope: Oscilloscope instance
        """
        self.scope = scope

    def _on_add_measurement(self):
        """Handle add measurement button."""
        if not self.scope:
            logger.warning("Cannot add measurement: no scope connected")
            return

        channel_text = self.channel_combo.currentText()
        channel_num = int(channel_text[1])  # Extract number from "C1"
        measurement_name = self.measurement_combo.currentText()

        # Find measurement type
        measurement_type = None
        for name, mtype in self.MEASUREMENTS:
            if name == measurement_name:
                measurement_type = mtype
                break

        if not measurement_type:
            return

        # Check if this measurement already exists
        for meas in self.active_measurements:
            if meas["channel"] == channel_num and meas["type"] == measurement_type:
                logger.info(f"Measurement already exists: {channel_text} {measurement_name}")
                return

        # Add to active measurements
        self.active_measurements.append(
            {
                "channel": channel_num,
                "type": measurement_type,
                "name": measurement_name,
                "value": None,
            }
        )

        self._refresh_table()
        logger.info(f"Added measurement: {channel_text} {measurement_name}")

    def _on_remove_measurement(self, index: int):
        """Handle remove measurement button.

        Args:
            index: Index of measurement to remove
        """
        if 0 <= index < len(self.active_measurements):
            meas = self.active_measurements.pop(index)
            self._refresh_table()
            logger.info(f"Removed measurement: C{meas['channel']} {meas['name']}")

    def _on_clear_all(self):
        """Handle clear all button."""
        self.active_measurements.clear()
        self._refresh_table()
        logger.info("Cleared all measurements")

    def _on_auto_update_toggled(self, checked: bool):
        """Handle auto update toggle.

        Args:
            checked: Auto update state
        """
        self.auto_update = checked

        if checked:
            self.auto_update_btn.setText("Auto Update: ON")
            self.update_timer.start(1000)  # Update every 1 second
            logger.info("Auto update enabled")
        else:
            self.auto_update_btn.setText("Auto Update: OFF")
            self.update_timer.stop()
            logger.info("Auto update disabled")

    def _refresh_table(self):
        """Refresh the measurement table."""
        self.table.setRowCount(len(self.active_measurements))

        for i, meas in enumerate(self.active_measurements):
            # Channel
            channel_item = QTableWidgetItem(f"C{meas['channel']}")
            channel_item.setFlags(channel_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, channel_item)

            # Measurement name
            name_item = QTableWidgetItem(meas["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, name_item)

            # Value
            value_text = meas["value"] if meas["value"] is not None else "---"
            value_item = QTableWidgetItem(value_text)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, value_item)

            # Remove button
            remove_btn = QPushButton("X")
            remove_btn.setMaximumWidth(30)
            remove_btn.clicked.connect(lambda checked, idx=i: self._on_remove_measurement(idx))
            self.table.setCellWidget(i, 3, remove_btn)

    def _update_measurements(self):
        """Update all measurement values."""
        if not self.scope:
            return

        for i, meas in enumerate(self.active_measurements):
            try:
                # Get measurement value
                value = self._get_measurement_value(meas["channel"], meas["type"])

                # Format the value
                if value is not None:
                    formatted_value = self._format_measurement_value(meas["type"], value)
                    meas["value"] = formatted_value
                else:
                    meas["value"] = "Error"

            except Exception as e:
                logger.debug(f"Error measuring {meas['name']} on C{meas['channel']}: {e}")
                meas["value"] = "Error"

        self._refresh_table()

    def _get_measurement_value(self, channel: int, meas_type: str) -> Optional[float]:
        """Get a measurement value from the oscilloscope.

        Args:
            channel: Channel number (1-4)
            meas_type: Measurement type

        Returns:
            Measurement value or None if error
        """
        if not self.scope:
            return None

        try:
            # Map measurement type to method
            method_name = f"measure_{meas_type}"
            if hasattr(self.scope.measurement, method_name):
                method = getattr(self.scope.measurement, method_name)
                return method(channel)
            else:
                logger.warning(f"Unknown measurement type: {meas_type}")
                return None

        except Exception as e:
            logger.debug(f"Measurement error: {e}")
            return None

    def _format_measurement_value(self, meas_type: str, value: float) -> str:
        """Format a measurement value for display.

        Args:
            meas_type: Measurement type
            value: Raw value

        Returns:
            Formatted string
        """
        if value is None:
            return "---"

        # Format based on measurement type
        if meas_type in ["frequency"]:
            if value >= 1e6:
                return f"{value/1e6:.3f} MHz"
            elif value >= 1e3:
                return f"{value/1e3:.3f} kHz"
            else:
                return f"{value:.3f} Hz"

        elif meas_type in ["period", "rise_time", "fall_time", "positive_width", "negative_width"]:
            if value >= 1.0:
                return f"{value:.3f} s"
            elif value >= 1e-3:
                return f"{value*1e3:.3f} ms"
            elif value >= 1e-6:
                return f"{value*1e6:.3f} µs"
            else:
                return f"{value*1e9:.3f} ns"

        elif meas_type in ["duty_cycle"]:
            return f"{value:.2f} %"

        else:  # Voltage measurements
            if abs(value) >= 1.0:
                return f"{value:.3f} V"
            else:
                return f"{value*1e3:.3f} mV"
