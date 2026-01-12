"""Channel configuration widget for DAQ/Data Logger.

This module provides a widget for configuring DAQ channels including
measurement function, range, and enable/disable states.
"""

import logging
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Measurement functions with display names and SCPI identifiers
MEASUREMENT_FUNCTIONS = [
    ("DC Voltage", "VOLT:DC"),
    ("AC Voltage", "VOLT:AC"),
    ("DC Current", "CURR:DC"),
    ("AC Current", "CURR:AC"),
    ("2-Wire Resistance", "RES"),
    ("4-Wire Resistance", "FRES"),
    ("Temperature (TC-K)", "TEMP:TC:K"),
    ("Temperature (TC-J)", "TEMP:TC:J"),
    ("Temperature (RTD)", "TEMP:RTD"),
    ("Frequency", "FREQ"),
    ("Period", "PER"),
]

# Ranges for different measurement types
RANGES = {
    "VOLT:DC": ["AUTO", "0.1", "1", "10", "100", "300"],
    "VOLT:AC": ["AUTO", "0.1", "1", "10", "100", "300"],
    "CURR:DC": ["AUTO", "0.01", "0.1", "1"],
    "CURR:AC": ["AUTO", "0.01", "0.1", "1"],
    "RES": ["AUTO", "100", "1k", "10k", "100k", "1M", "10M", "100M"],
    "FRES": ["AUTO", "100", "1k", "10k", "100k", "1M", "10M", "100M"],
    "TEMP:TC:K": ["---"],
    "TEMP:TC:J": ["---"],
    "TEMP:RTD": ["---"],
    "FREQ": ["AUTO"],
    "PER": ["AUTO"],
}


class ChannelRow(QWidget):
    """A single channel configuration row."""

    config_changed = pyqtSignal(int, dict)  # channel, config

    def __init__(self, channel: int, parent=None):
        """Initialize channel row.

        Args:
            channel: Channel number (e.g., 101)
            parent: Parent widget
        """
        super().__init__(parent)
        self.channel = channel
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)

        # Enable checkbox
        self.enable_cb = QCheckBox()
        self.enable_cb.setToolTip("Enable channel for scanning")
        self.enable_cb.stateChanged.connect(self._on_config_changed)
        layout.addWidget(self.enable_cb)

        # Channel label
        self.channel_label = QLabel(f"CH{self.channel}")
        self.channel_label.setMinimumWidth(50)
        self.channel_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.channel_label)

        # Measurement function
        self.function_combo = QComboBox()
        self.function_combo.setMinimumWidth(140)
        for display_name, _ in MEASUREMENT_FUNCTIONS:
            self.function_combo.addItem(display_name)
        self.function_combo.currentIndexChanged.connect(self._on_function_changed)
        layout.addWidget(self.function_combo)

        # Range
        self.range_combo = QComboBox()
        self.range_combo.setMinimumWidth(80)
        self._update_ranges()
        self.range_combo.currentIndexChanged.connect(self._on_config_changed)
        layout.addWidget(self.range_combo)

        # Current reading display
        self.reading_label = QLabel("---")
        self.reading_label.setMinimumWidth(100)
        self.reading_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.reading_label.setStyleSheet("color: #00ff00; font-family: monospace;")
        layout.addWidget(self.reading_label)

    def _on_function_changed(self, index: int):
        """Handle measurement function change."""
        self._update_ranges()
        self._on_config_changed()

    def _update_ranges(self):
        """Update range options based on selected function."""
        func_index = self.function_combo.currentIndex()
        if func_index >= 0 and func_index < len(MEASUREMENT_FUNCTIONS):
            _, func_id = MEASUREMENT_FUNCTIONS[func_index]
            ranges = RANGES.get(func_id, ["AUTO"])

            self.range_combo.blockSignals(True)
            self.range_combo.clear()
            self.range_combo.addItems(ranges)
            self.range_combo.blockSignals(False)

    def _on_config_changed(self):
        """Emit config changed signal."""
        config = self.get_config()
        self.config_changed.emit(self.channel, config)

    def get_config(self) -> Dict:
        """Get the current configuration.

        Returns:
            Dictionary with channel configuration
        """
        func_index = self.function_combo.currentIndex()
        func_display, func_id = MEASUREMENT_FUNCTIONS[func_index]

        return {
            "enabled": self.enable_cb.isChecked(),
            "function": func_id,
            "function_display": func_display,
            "range": self.range_combo.currentText(),
        }

    def set_config(self, config: Dict):
        """Set the channel configuration.

        Args:
            config: Configuration dictionary
        """
        self.enable_cb.setChecked(config.get("enabled", False))

        func_id = config.get("function", "VOLT:DC")
        for i, (_, fid) in enumerate(MEASUREMENT_FUNCTIONS):
            if fid == func_id:
                self.function_combo.setCurrentIndex(i)
                break

        range_val = config.get("range", "AUTO")
        idx = self.range_combo.findText(range_val)
        if idx >= 0:
            self.range_combo.setCurrentIndex(idx)

    def update_reading(self, value: float, unit: str = ""):
        """Update the displayed reading.

        Args:
            value: Reading value
            unit: Unit string
        """
        self.reading_label.setText(f"{value:.6f} {unit}".strip())

    def clear_reading(self):
        """Clear the displayed reading."""
        self.reading_label.setText("---")


class DAQChannelConfig(QWidget):
    """DAQ channel configuration panel.

    Signals:
        config_changed: Emitted when any channel configuration changes
    """

    config_changed = pyqtSignal(dict)  # Complete configuration

    def __init__(self, parent=None):
        """Initialize the channel configuration widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.channel_rows: Dict[int, ChannelRow] = {}
        self.available_channels: List[int] = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header = QLabel("Channel Configuration")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        # Quick actions
        action_layout = QHBoxLayout()

        self.enable_all_btn = QPushButton("Enable All")
        self.enable_all_btn.clicked.connect(self._enable_all)
        action_layout.addWidget(self.enable_all_btn)

        self.disable_all_btn = QPushButton("Disable All")
        self.disable_all_btn.clicked.connect(self._disable_all)
        action_layout.addWidget(self.disable_all_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Scrollable channel list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.channel_container = QWidget()
        self.channel_layout = QVBoxLayout(self.channel_container)
        self.channel_layout.setSpacing(2)
        self.channel_layout.addStretch()

        scroll.setWidget(self.channel_container)
        layout.addWidget(scroll)

    def set_available_channels(self, channels: List[int]):
        """Set the available channels to configure.

        Args:
            channels: List of channel numbers
        """
        self.available_channels = channels

        # Clear existing rows
        for row in self.channel_rows.values():
            self.channel_layout.removeWidget(row)
            row.deleteLater()
        self.channel_rows.clear()

        # Create new rows
        for ch in sorted(channels):
            row = ChannelRow(ch)
            row.config_changed.connect(self._on_channel_changed)
            self.channel_rows[ch] = row
            # Insert before stretch
            self.channel_layout.insertWidget(self.channel_layout.count() - 1, row)

    def _on_channel_changed(self, channel: int, config: Dict):
        """Handle channel configuration change."""
        self.config_changed.emit(self.get_all_configs())

    def get_all_configs(self) -> Dict[int, Dict]:
        """Get configuration for all channels.

        Returns:
            Dictionary mapping channel number to configuration
        """
        return {ch: row.get_config() for ch, row in self.channel_rows.items()}

    def get_enabled_channels(self) -> List[int]:
        """Get list of enabled channel numbers.

        Returns:
            List of enabled channel numbers
        """
        return [ch for ch, row in self.channel_rows.items() if row.get_config()["enabled"]]

    def set_all_configs(self, configs: Dict[int, Dict]):
        """Set configuration for all channels.

        Args:
            configs: Dictionary mapping channel number to configuration
        """
        for ch, config in configs.items():
            if ch in self.channel_rows:
                self.channel_rows[ch].set_config(config)

    def update_reading(self, channel: int, value: float, unit: str = ""):
        """Update the reading display for a channel.

        Args:
            channel: Channel number
            value: Reading value
            unit: Unit string
        """
        if channel in self.channel_rows:
            self.channel_rows[channel].update_reading(value, unit)

    def clear_all_readings(self):
        """Clear all reading displays."""
        for row in self.channel_rows.values():
            row.clear_reading()

    def _enable_all(self):
        """Enable all channels."""
        for row in self.channel_rows.values():
            row.enable_cb.setChecked(True)

    def _disable_all(self):
        """Disable all channels."""
        for row in self.channel_rows.values():
            row.enable_cb.setChecked(False)
