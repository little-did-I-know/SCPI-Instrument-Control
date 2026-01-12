"""Scan configuration widget for DAQ/Data Logger.

This module provides a widget for configuring scan parameters including
interval, duration, and trigger settings.
"""

import logging
from typing import Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Trigger sources
TRIGGER_SOURCES = [
    ("Immediate", "IMM"),
    ("Bus/Software", "BUS"),
    ("External", "EXT"),
]


class DAQScanConfig(QWidget):
    """Scan configuration panel for DAQ.

    Signals:
        config_changed: Emitted when configuration changes
        start_requested: Emitted when start button is clicked
        stop_requested: Emitted when stop button is clicked
    """

    config_changed = pyqtSignal(dict)
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the scan configuration widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._is_running = False
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Scan Settings Group
        scan_group = QGroupBox("Scan Settings")
        scan_layout = QFormLayout()
        scan_layout.setSpacing(8)

        # Scan interval
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSingleStep(0.1)
        self.interval_spin.setToolTip("Time between scan cycles")
        self.interval_spin.valueChanged.connect(self._on_config_changed)
        scan_layout.addRow("Interval:", self.interval_spin)

        # Duration
        duration_layout = QHBoxLayout()
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 86400)  # Up to 24 hours
        self.duration_spin.setValue(0)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setToolTip("Total logging duration (0 = infinite)")
        self.duration_spin.valueChanged.connect(self._on_config_changed)
        duration_layout.addWidget(self.duration_spin)

        self.infinite_label = QLabel("(0 = infinite)")
        self.infinite_label.setStyleSheet("color: #888888; font-size: 10px;")
        duration_layout.addWidget(self.infinite_label)
        duration_layout.addStretch()

        scan_layout.addRow("Duration:", duration_layout)

        # Trigger source
        self.trigger_combo = QComboBox()
        for display_name, _ in TRIGGER_SOURCES:
            self.trigger_combo.addItem(display_name)
        self.trigger_combo.setToolTip("Trigger source for scan initiation")
        self.trigger_combo.currentIndexChanged.connect(self._on_config_changed)
        scan_layout.addRow("Trigger:", self.trigger_combo)

        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # Statistics Group
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout()
        stats_layout.setSpacing(4)

        self.scan_count_label = QLabel("0")
        self.scan_count_label.setStyleSheet("font-weight: bold;")
        stats_layout.addRow("Scans:", self.scan_count_label)

        self.elapsed_label = QLabel("0:00:00")
        self.elapsed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addRow("Elapsed:", self.elapsed_label)

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: #888888;")
        stats_layout.addRow("Status:", self.status_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.start_btn = QPushButton("Start Logging")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #c62828;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def _on_config_changed(self):
        """Emit configuration changed signal."""
        self.config_changed.emit(self.get_config())

    def _on_start_clicked(self):
        """Handle start button click."""
        self.start_requested.emit()

    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.stop_requested.emit()

    def get_config(self) -> Dict:
        """Get the current scan configuration.

        Returns:
            Dictionary with scan configuration
        """
        trigger_idx = self.trigger_combo.currentIndex()
        _, trigger_id = TRIGGER_SOURCES[trigger_idx]

        duration = self.duration_spin.value()
        if duration == 0:
            duration = None  # Infinite

        return {
            "interval": self.interval_spin.value(),
            "duration": duration,
            "trigger_source": trigger_id,
        }

    def set_config(self, config: Dict):
        """Set the scan configuration.

        Args:
            config: Configuration dictionary
        """
        if "interval" in config:
            self.interval_spin.setValue(config["interval"])

        if "duration" in config:
            duration = config["duration"]
            self.duration_spin.setValue(duration if duration is not None else 0)

        if "trigger_source" in config:
            trigger_id = config["trigger_source"]
            for i, (_, tid) in enumerate(TRIGGER_SOURCES):
                if tid == trigger_id:
                    self.trigger_combo.setCurrentIndex(i)
                    break

    def set_running(self, running: bool):
        """Set the running state and update UI accordingly.

        Args:
            running: Whether acquisition is running
        """
        self._is_running = running
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

        # Disable config changes while running
        self.interval_spin.setEnabled(not running)
        self.duration_spin.setEnabled(not running)
        self.trigger_combo.setEnabled(not running)

        if running:
            self.status_label.setText("Running")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            self.status_label.setText("Idle")
            self.status_label.setStyleSheet("color: #888888;")

    def update_statistics(self, scan_count: int, elapsed_seconds: float):
        """Update the statistics display.

        Args:
            scan_count: Number of scans completed
            elapsed_seconds: Elapsed time in seconds
        """
        self.scan_count_label.setText(str(scan_count))

        # Format elapsed time as H:MM:SS
        hours = int(elapsed_seconds // 3600)
        minutes = int((elapsed_seconds % 3600) // 60)
        seconds = int(elapsed_seconds % 60)
        self.elapsed_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}")

    def update_status(self, status: str):
        """Update the status label.

        Args:
            status: Status message to display
        """
        self.status_label.setText(status)

    def reset_statistics(self):
        """Reset statistics to initial values."""
        self.scan_count_label.setText("0")
        self.elapsed_label.setText("0:00:00")
        if not self._is_running:
            self.status_label.setText("Idle")
            self.status_label.setStyleSheet("color: #888888;")
