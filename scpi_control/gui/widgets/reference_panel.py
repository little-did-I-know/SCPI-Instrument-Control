"""Reference waveform panel for managing and comparing reference waveforms."""

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class ReferencePanel(QWidget):
    """Widget for managing reference waveforms.

    Provides a browser for saved reference waveforms with options to
    load, delete, and view information about each reference.

    Signals:
        load_reference: Emitted when user requests to load a reference (filepath: str)
        save_reference: Emitted when user requests to save current waveform as reference
        delete_reference: Emitted when user deletes a reference (filepath: str)
        show_difference: Emitted when user wants to show difference with reference
    """

    load_reference = pyqtSignal(str)
    save_reference = pyqtSignal()
    delete_reference = pyqtSignal(str)
    show_difference = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize reference panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_references = []
        self.loaded_reference = None

        self._init_ui()
        logger.info("Reference panel initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Save current waveform section
        save_group = self._create_save_group()
        layout.addWidget(save_group)

        # Reference library section
        library_group = self._create_library_group()
        layout.addWidget(library_group)

        # Comparison tools section
        compare_group = self._create_comparison_group()
        layout.addWidget(compare_group)

    def _create_save_group(self) -> QGroupBox:
        """Create save current waveform group.

        Returns:
            Save group box
        """
        group = QGroupBox("Save Current Waveform")
        layout = QVBoxLayout(group)

        info_label = QLabel("Capture the current waveform as a reference for future comparison.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-size: 9pt;")
        layout.addWidget(info_label)

        save_btn = QPushButton("Save as Reference...")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self._on_save_reference)
        layout.addWidget(save_btn)

        return group

    def _create_library_group(self) -> QGroupBox:
        """Create reference library group.

        Returns:
            Library group box
        """
        group = QGroupBox("Reference Library")
        layout = QVBoxLayout(group)

        # Reference list
        self.reference_list = QListWidget()
        self.reference_list.itemDoubleClicked.connect(self._on_load_reference_item)
        layout.addWidget(self.reference_list)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._on_refresh_list)
        button_layout.addWidget(refresh_btn)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._on_load_reference_button)
        button_layout.addWidget(load_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete_reference)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

        # Info display
        self.info_label = QLabel("No reference loaded")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; font-size: 9pt;")
        layout.addWidget(self.info_label)

        return group

    def _create_comparison_group(self) -> QGroupBox:
        """Create comparison tools group.

        Returns:
            Comparison group box
        """
        group = QGroupBox("Comparison Tools")
        layout = QVBoxLayout(group)

        # Show difference toggle
        self.show_diff_btn = QPushButton("Show Difference")
        self.show_diff_btn.setCheckable(True)
        self.show_diff_btn.setChecked(False)
        self.show_diff_btn.setEnabled(False)
        self.show_diff_btn.toggled.connect(self._on_show_difference_toggled)
        layout.addWidget(self.show_diff_btn)

        # Correlation display
        self.correlation_label = QLabel("Correlation: --")
        self.correlation_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.correlation_label)

        # Statistics display
        self.stats_label = QLabel("RMS Difference: --")
        layout.addWidget(self.stats_label)

        # Unload button
        unload_btn = QPushButton("Unload Reference")
        unload_btn.clicked.connect(self._on_unload_reference)
        layout.addWidget(unload_btn)

        return group

    def _on_save_reference(self):
        """Handle save reference button click."""
        logger.info("Save reference requested")
        self.save_reference.emit()

    def _on_refresh_list(self):
        """Handle refresh list button click."""
        # This will be called from main window after updating the list
        logger.info("Refresh reference list requested")

    def _on_load_reference_button(self):
        """Handle load reference button click."""
        selected_items = self.reference_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a reference to load")
            return

        self._on_load_reference_item(selected_items[0])

    def _on_load_reference_item(self, item: QListWidgetItem):
        """Handle double-click on reference item.

        Args:
            item: Selected list item
        """
        # Get filepath from item data
        filepath = item.data(Qt.ItemDataRole.UserRole)

        if filepath:
            logger.info(f"Load reference requested: {filepath}")
            self.load_reference.emit(filepath)

    def _on_delete_reference(self):
        """Handle delete reference button click."""
        selected_items = self.reference_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a reference to delete")
            return

        item = selected_items[0]
        name = item.text().split("\n")[0]  # Get first line (name)
        filepath = item.data(Qt.ItemDataRole.UserRole)

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete reference '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"Delete reference requested: {filepath}")
            self.delete_reference.emit(filepath)

    def _on_show_difference_toggled(self, checked: bool):
        """Handle show difference toggle.

        Args:
            checked: Whether difference should be shown
        """
        logger.info(f"Show difference toggled: {checked}")
        self.show_difference.emit(checked)

    def _on_unload_reference(self):
        """Handle unload reference button click."""
        self.loaded_reference = None
        self.info_label.setText("No reference loaded")
        self.show_diff_btn.setEnabled(False)
        self.show_diff_btn.setChecked(False)
        self.correlation_label.setText("Correlation: --")
        self.stats_label.setText("RMS Difference: --")
        logger.info("Reference unloaded")

    def update_reference_list(self, references: list):
        """Update the reference list display.

        Args:
            references: List of reference info dictionaries
        """
        self.reference_list.clear()
        self.current_references = references

        for ref in references:
            # Create display text
            name = ref.get("name", "Unknown")
            channel = ref.get("channel", "Unknown")
            timestamp = ref.get("timestamp", "")

            # Format timestamp
            if timestamp:
                try:
                    from datetime import datetime

                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = "Unknown time"
            else:
                time_str = "Unknown time"

            # Format file size
            file_size = ref.get("file_size", 0)
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            # Create item text
            item_text = f"{name}\n{channel} | {time_str} | {size_str}"

            # Create list item
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, ref.get("filepath"))

            self.reference_list.addItem(item)

        logger.info(f"Reference list updated with {len(references)} items")

    def set_loaded_reference(self, reference_data: Dict[str, Any]):
        """Update display when a reference is loaded.

        Args:
            reference_data: Loaded reference data
        """
        self.loaded_reference = reference_data

        # Update info label
        metadata = reference_data.get("metadata", {})
        name = metadata.get("name", "Unknown")
        channel = metadata.get("channel", "Unknown")
        num_samples = metadata.get("num_samples", 0)
        time_span = metadata.get("time_span", 0.0)

        # Format time span
        if time_span < 1e-6:
            time_str = f"{time_span * 1e9:.2f} ns"
        elif time_span < 1e-3:
            time_str = f"{time_span * 1e6:.2f} µs"
        elif time_span < 1:
            time_str = f"{time_span * 1e3:.2f} ms"
        else:
            time_str = f"{time_span:.2f} s"

        info_text = f"<b>Loaded:</b> {name}<br>" f"<b>Channel:</b> {channel}<br>" f"<b>Samples:</b> {num_samples}<br>" f"<b>Time Span:</b> {time_str}"

        self.info_label.setText(info_text)

        # Enable comparison tools
        self.show_diff_btn.setEnabled(True)

        logger.info(f"Reference loaded: {name}")

    def update_comparison_stats(self, correlation: Optional[float], rms_diff: Optional[float]):
        """Update comparison statistics display.

        Args:
            correlation: Correlation coefficient (0.0 to 1.0)
            rms_diff: RMS difference value
        """
        if correlation is not None:
            # Color code correlation
            if correlation > 0.95:
                color = "green"
            elif correlation > 0.8:
                color = "orange"
            else:
                color = "red"

            self.correlation_label.setText(f"Correlation: <span style='color: {color}; font-weight: bold;'>{correlation:.4f}</span>")
        else:
            self.correlation_label.setText("Correlation: --")

        if rms_diff is not None:
            # Format RMS difference with appropriate units
            if abs(rms_diff) < 1e-3:
                diff_str = f"{rms_diff * 1e6:.3f} µV"
            elif abs(rms_diff) < 1:
                diff_str = f"{rms_diff * 1e3:.3f} mV"
            else:
                diff_str = f"{rms_diff:.3f} V"

            self.stats_label.setText(f"RMS Difference: {diff_str}")
        else:
            self.stats_label.setText("RMS Difference: --")

    def clear_comparison_stats(self):
        """Clear comparison statistics display."""
        self.correlation_label.setText("Correlation: --")
        self.stats_label.setText("RMS Difference: --")
