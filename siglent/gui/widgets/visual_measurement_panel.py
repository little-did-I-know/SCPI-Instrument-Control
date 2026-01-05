"""Visual measurement panel for interactive waveform measurements.

This module provides the UI panel for managing visual measurement markers
on waveforms. Users can add measurement markers of different types, adjust
their positions, and see real-time measurement results.

Features:
    - 15+ measurement types (frequency, voltage, timing)
    - Interactive marker placement and adjustment
    - Save/load measurement configurations
    - Export results to CSV/JSON
    - Auto-update mode with configurable refresh rate
    - Batch measurement support

Supported Measurement Types:
    - Frequency/Period: FREQ, PER
    - Voltage: PKPK, AMPL, MAX, MIN, RMS, MEAN, TOP, BASE
    - Timing: RISE, FALL, WID, NWID, DUTY

Architecture:
    The panel acts as a controller for visual markers on the waveform display.
    It creates marker objects and adds them to the display widget, managing
    their lifecycle and updating their measurements.

Example:
    >>> panel = VisualMeasurementPanel(waveform_display)
    >>> panel.marker_added.connect(on_marker_added)
    >>> # User clicks "Add Marker" button
    >>> # Marker appears on waveform with live measurements
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget

from siglent.gui.widgets.measurement_markers import FrequencyMarker, TimingMarker, VoltageMarker
from siglent.measurement_config import MeasurementConfigSet, MeasurementMarkerConfig

if TYPE_CHECKING:
    from siglent.gui.widgets.waveform_display import WaveformDisplay

logger = logging.getLogger(__name__)


class VisualMeasurementPanel(QWidget):
    """Panel for controlling visual measurement markers.

    Provides UI for:
    - Adding/removing markers
    - Enabling/disabling markers
    - Updating measurements
    - Saving/loading configurations
    - Exporting results

    Signals:
        marker_added: Emitted when a marker is added
        marker_removed: Emitted when a marker is removed
        measurements_updated: Emitted when measurements are updated
    """

    marker_added = pyqtSignal(object)  # MeasurementMarker
    marker_removed = pyqtSignal(object)  # MeasurementMarker
    measurements_updated = pyqtSignal()

    # Measurement type options
    MEASUREMENT_TYPES = {
        "Frequency": ("FREQ", FrequencyMarker),
        "Period": ("PER", FrequencyMarker),
        "Peak-to-Peak": ("PKPK", VoltageMarker),
        "Amplitude": ("AMPL", VoltageMarker),
        "Maximum": ("MAX", VoltageMarker),
        "Minimum": ("MIN", VoltageMarker),
        "RMS": ("RMS", VoltageMarker),
        "Mean": ("MEAN", VoltageMarker),
        "Top": ("TOP", VoltageMarker),
        "Base": ("BASE", VoltageMarker),
        "Rise Time": ("RISE", TimingMarker),
        "Fall Time": ("FALL", TimingMarker),
        "Positive Width": ("WID", TimingMarker),
        "Negative Width": ("NWID", TimingMarker),
        "Duty Cycle": ("DUTY", TimingMarker),
    }

    def __init__(self, waveform_display: "WaveformDisplay", parent: Optional[QWidget] = None):
        """Initialize visual measurement panel.

        Args:
            waveform_display: WaveformDisplay widget to control
            parent: Parent widget
        """
        super().__init__(parent)

        self.waveform_display = waveform_display
        self.marker_counter = 0  # For generating unique marker IDs
        self.auto_update_enabled = False

        # Auto-update timer
        self.auto_update_timer = QTimer()
        self.auto_update_timer.timeout.connect(self._on_auto_update)
        self.auto_update_timer.setInterval(1000)  # 1 second

        self._init_ui()
        logger.info("Visual measurement panel initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Add marker controls
        add_group = self._create_add_marker_group()
        layout.addWidget(add_group)

        # Active markers list
        markers_group = self._create_markers_list_group()
        layout.addWidget(markers_group)

        # Control buttons
        control_group = self._create_control_group()
        layout.addWidget(control_group)

        # File operations
        file_group = self._create_file_operations_group()
        layout.addWidget(file_group)

        layout.addStretch()

    def _create_add_marker_group(self) -> QGroupBox:
        """Create controls for adding markers.

        Returns:
            Group box with add marker controls
        """
        group = QGroupBox("Add Marker")
        layout = QVBoxLayout(group)

        # Measurement type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))

        self.type_combo = QComboBox()
        self.type_combo.addItems(sorted(self.MEASUREMENT_TYPES.keys()))
        type_layout.addWidget(self.type_combo, stretch=1)

        layout.addLayout(type_layout)

        # Channel selector
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("Channel:"))

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["CH1", "CH2", "CH3", "CH4"])
        channel_layout.addWidget(self.channel_combo, stretch=1)

        layout.addLayout(channel_layout)

        # Add button
        add_btn = QPushButton("Add Marker")
        add_btn.clicked.connect(self._on_add_marker)
        layout.addWidget(add_btn)

        return group

    def _create_markers_list_group(self) -> QGroupBox:
        """Create active markers list.

        Returns:
            Group box with markers list
        """
        group = QGroupBox("Active Markers")
        layout = QVBoxLayout(group)

        self.markers_list = QListWidget()
        self.markers_list.itemChanged.connect(self._on_marker_item_changed)
        layout.addWidget(self.markers_list)

        # Remove button
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove_marker)
        layout.addWidget(remove_btn)

        return group

    def _create_control_group(self) -> QGroupBox:
        """Create measurement control buttons.

        Returns:
            Group box with control buttons
        """
        group = QGroupBox("Measurement Controls")
        layout = QVBoxLayout(group)

        # Update now button
        update_btn = QPushButton("Update All Measurements")
        update_btn.clicked.connect(self._on_update_measurements)
        layout.addWidget(update_btn)

        # Auto-update toggle
        self.auto_update_checkbox = QCheckBox("Auto Update (1s interval)")
        self.auto_update_checkbox.stateChanged.connect(self._on_auto_update_toggle)
        layout.addWidget(self.auto_update_checkbox)

        # Clear all button
        clear_btn = QPushButton("Clear All Markers")
        clear_btn.clicked.connect(self._on_clear_all)
        layout.addWidget(clear_btn)

        return group

    def _create_file_operations_group(self) -> QGroupBox:
        """Create file operation buttons.

        Returns:
            Group box with file operation buttons
        """
        group = QGroupBox("Configuration")
        layout = QVBoxLayout(group)

        # Save configuration button
        save_btn = QPushButton("Save Configuration...")
        save_btn.clicked.connect(self._on_save_config)
        layout.addWidget(save_btn)

        # Load configuration button
        load_btn = QPushButton("Load Configuration...")
        load_btn.clicked.connect(self._on_load_config)
        layout.addWidget(load_btn)

        # Export results button
        export_btn = QPushButton("Export Results...")
        export_btn.clicked.connect(self._on_export_results)
        layout.addWidget(export_btn)

        return group

    def _on_add_marker(self):
        """Handle add marker button click."""
        try:
            # Get selected type and channel
            type_name = self.type_combo.currentText()
            channel_text = self.channel_combo.currentText()  # 'CH1', 'CH2', etc.
            channel = int(channel_text[2:])  # Extract number

            if type_name not in self.MEASUREMENT_TYPES:
                logger.error(f"Unknown measurement type: {type_name}")
                return

            mtype, marker_class = self.MEASUREMENT_TYPES[type_name]

            # Generate marker ID
            self.marker_counter += 1
            marker_id = f"M{self.marker_counter}"

            # Create marker
            marker = marker_class(
                marker_id=marker_id,
                measurement_type=mtype,
                channel=channel,
                ax=self.waveform_display.ax,
                canvas=self.waveform_display.canvas,
            )

            # Auto-place marker if waveform data available
            if self.waveform_display.current_waveforms:
                waveform = next(
                    (w for w in self.waveform_display.current_waveforms if w.channel == channel),
                    None,
                )
                if waveform:
                    marker.auto_place(waveform)
                    marker.update_measurement(waveform)

            # Add to display
            self.waveform_display.add_measurement_marker(marker)

            # Add to list
            self._add_marker_to_list(marker)

            # Enable edit mode
            self.waveform_display.set_marker_mode("edit")

            # Emit signal
            self.marker_added.emit(marker)

            logger.info(f"Added {type_name} marker {marker_id} on CH{channel}")

        except Exception as e:
            logger.error(f"Failed to add marker: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add marker: {e}")

    def _add_marker_to_list(self, marker):
        """Add marker to the list widget.

        Args:
            marker: MeasurementMarker to add
        """
        # Create list item
        item = QListWidgetItem()
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if marker.enabled else Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, marker)  # Store marker reference

        # Set text
        self._update_marker_item_text(item, marker)

        self.markers_list.addItem(item)

    def _update_marker_item_text(self, item: QListWidgetItem, marker):
        """Update list item text with current marker state.

        Args:
            item: List widget item
            marker: MeasurementMarker
        """
        # Format: "M1: CH1 Frequency = 125.3 kHz"
        type_name = next(
            (k for k, v in self.MEASUREMENT_TYPES.items() if v[0] == marker.measurement_type),
            marker.measurement_type,
        )

        if marker.result is not None:
            value_str = marker._format_value(marker.result, marker.unit)
        else:
            value_str = "---"

        text = f"{marker.marker_id}: CH{marker.channel} {type_name} = {value_str}"
        item.setText(text)

    def _on_marker_item_changed(self, item: QListWidgetItem):
        """Handle marker list item check state change.

        Args:
            item: List widget item that changed
        """
        marker = item.data(Qt.ItemDataRole.UserRole)
        if marker:
            # Update marker enabled state
            marker.enabled = item.checkState() == Qt.CheckState.Checked
            marker.set_visible(marker.enabled)
            self.waveform_display.canvas.draw()

    def _on_remove_marker(self):
        """Handle remove marker button click."""
        current_item = self.markers_list.currentItem()
        if not current_item:
            return

        marker = current_item.data(Qt.ItemDataRole.UserRole)
        if marker:
            # Remove from display
            self.waveform_display.remove_measurement_marker(marker)

            # Remove from list
            row = self.markers_list.row(current_item)
            self.markers_list.takeItem(row)

            # Emit signal
            self.marker_removed.emit(marker)

            logger.info(f"Removed marker {marker.marker_id}")

    def _on_update_measurements(self):
        """Handle update measurements button click."""
        self.waveform_display.update_all_markers()
        self._refresh_marker_list()
        self.measurements_updated.emit()
        logger.debug("Updated all measurements")

    def _refresh_marker_list(self):
        """Refresh marker list with current values."""
        for i in range(self.markers_list.count()):
            item = self.markers_list.item(i)
            marker = item.data(Qt.ItemDataRole.UserRole)
            if marker:
                self._update_marker_item_text(item, marker)

    def _on_auto_update_toggle(self, state):
        """Handle auto-update checkbox toggle.

        Args:
            state: Checkbox state
        """
        self.auto_update_enabled = bool(state)

        if self.auto_update_enabled:
            self.auto_update_timer.start()
            logger.info("Auto-update enabled")
        else:
            self.auto_update_timer.stop()
            logger.info("Auto-update disabled")

    def _on_auto_update(self):
        """Handle auto-update timer timeout."""
        if self.auto_update_enabled:
            self._on_update_measurements()

    def _on_clear_all(self):
        """Handle clear all markers button click."""
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Clear All Markers",
            "Are you sure you want to remove all markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.waveform_display.clear_all_markers()
            self.markers_list.clear()
            logger.info("Cleared all markers")

    def _on_save_config(self):
        """Handle save configuration button click."""
        try:
            # Get default config directory
            config_set = MeasurementConfigSet(name="temp", created_at=datetime.now())
            default_dir = str(config_set.get_default_config_dir())

            # Show file dialog
            filename, _ = QFileDialog.getSaveFileName(self, "Save Measurement Configuration", default_dir, "JSON Files (*.json)")

            if not filename:
                return

            # Ensure .json extension
            if not filename.endswith(".json"):
                filename += ".json"

            # Create configuration from current markers
            markers = []
            for i in range(self.markers_list.count()):
                item = self.markers_list.item(i)
                marker = item.data(Qt.ItemDataRole.UserRole)
                if marker:
                    config = marker.get_config()
                    markers.append(
                        MeasurementMarkerConfig(
                            id=config["id"],
                            measurement_type=config["type"],
                            channel=config["channel"],
                            enabled=config["enabled"],
                            gates=config["gates"],
                            visual_style={"color": config["color"]},
                            result=config["result"],
                            unit=config["unit"],
                        )
                    )

            # Create config set
            config_name = Path(filename).stem
            config_set = MeasurementConfigSet(name=config_name, created_at=datetime.now(), markers=markers)

            # Save to file
            config_set.save_to_file(filename)

            QMessageBox.information(self, "Success", f"Configuration saved to {filename}")
            logger.info(f"Saved configuration to {filename}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")

    def _on_load_config(self):
        """Handle load configuration button click."""
        try:
            # Get default config directory
            config_set = MeasurementConfigSet(name="temp", created_at=datetime.now())
            default_dir = str(config_set.get_default_config_dir())

            # Show file dialog
            filename, _ = QFileDialog.getOpenFileName(self, "Load Measurement Configuration", default_dir, "JSON Files (*.json)")

            if not filename:
                return

            # Load configuration
            config_set = MeasurementConfigSet.load_from_file(filename)

            # Clear existing markers
            self._on_clear_all()

            # Create markers from configuration
            for marker_config in config_set.markers:
                # Determine marker class
                marker_class = None
                for type_name, (mtype, mclass) in self.MEASUREMENT_TYPES.items():
                    if mtype == marker_config.measurement_type:
                        marker_class = mclass
                        break

                if marker_class is None:
                    logger.warning(f"Unknown marker type: {marker_config.measurement_type}")
                    continue

                # Create marker
                marker = marker_class(
                    marker_id=marker_config.id,
                    measurement_type=marker_config.measurement_type,
                    channel=marker_config.channel,
                    ax=self.waveform_display.ax,
                    canvas=self.waveform_display.canvas,
                    color=marker_config.visual_style.get("color"),
                )

                # Set configuration
                marker.set_config(
                    {
                        "enabled": marker_config.enabled,
                        "gates": marker_config.gates,
                        "color": marker_config.visual_style.get("color"),
                        "result": marker_config.result,
                        "unit": marker_config.unit,
                    }
                )

                # Add to display
                self.waveform_display.add_measurement_marker(marker)

                # Add to list
                self._add_marker_to_list(marker)

            # Update marker counter
            max_id = max([int(m.id[1:]) for m in config_set.markers if m.id.startswith("M")], default=0)
            self.marker_counter = max_id

            QMessageBox.information(self, "Success", f"Loaded {len(config_set.markers)} markers from {filename}")
            logger.info(f"Loaded configuration from {filename}")

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")

    def _on_export_results(self):
        """Handle export results button click."""
        try:
            # Show file dialog
            filename, _ = QFileDialog.getSaveFileName(self, "Export Measurement Results", "", "CSV Files (*.csv);;JSON Files (*.json)")

            if not filename:
                return

            # Determine format from extension
            if filename.endswith(".csv"):
                self._export_csv(filename)
            elif filename.endswith(".json"):
                self._export_json(filename)
            else:
                # Default to CSV
                filename += ".csv"
                self._export_csv(filename)

            QMessageBox.information(self, "Success", f"Results exported to {filename}")
            logger.info(f"Exported results to {filename}")

        except Exception as e:
            logger.error(f"Failed to export results: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export results: {e}")

    def _export_csv(self, filename: str):
        """Export results to CSV file.

        Args:
            filename: Output filename
        """
        import csv

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Marker ID", "Type", "Channel", "Value", "Unit", "Enabled"])

            for i in range(self.markers_list.count()):
                item = self.markers_list.item(i)
                marker = item.data(Qt.ItemDataRole.UserRole)
                if marker:
                    writer.writerow(
                        [
                            marker.marker_id,
                            marker.measurement_type,
                            marker.channel,
                            marker.result if marker.result is not None else "",
                            marker.unit or "",
                            "Yes" if marker.enabled else "No",
                        ]
                    )

    def _export_json(self, filename: str):
        """Export results to JSON file.

        Args:
            filename: Output filename
        """
        import json

        results = {"timestamp": datetime.now().isoformat(), "measurements": []}

        for i in range(self.markers_list.count()):
            item = self.markers_list.item(i)
            marker = item.data(Qt.ItemDataRole.UserRole)
            if marker:
                results["measurements"].append(
                    {
                        "marker_id": marker.marker_id,
                        "type": marker.measurement_type,
                        "channel": marker.channel,
                        "value": marker.result,
                        "unit": marker.unit,
                        "enabled": marker.enabled,
                    }
                )

        with open(filename, "w") as f:
            json.dump(results, f, indent=2)
