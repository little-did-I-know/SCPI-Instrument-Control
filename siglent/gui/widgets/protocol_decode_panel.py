"""Protocol decode panel for analyzing digital communication protocols."""

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ProtocolDecodePanel(QWidget):
    """Widget for protocol decode configuration and display.

    Provides protocol selection, parameter configuration, and
    decoded event display in a table format.

    Signals:
        decode_requested: Emitted when user requests decode (protocol: str, params: dict, channel_map: dict)
        export_requested: Emitted when user wants to export events
    """

    decode_requested = pyqtSignal(str, dict, dict)
    export_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize protocol decode panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_protocol = None
        self.decoded_events = []

        self._init_ui()
        logger.info("Protocol decode panel initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Protocol selection
        protocol_group = self._create_protocol_group()
        layout.addWidget(protocol_group)

        # Channel assignment
        channel_group = self._create_channel_group()
        layout.addWidget(channel_group)

        # Parameters
        params_group = self._create_parameters_group()
        layout.addWidget(params_group)

        # Decode button
        decode_btn = QPushButton("Decode Protocol")
        decode_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        decode_btn.clicked.connect(self._on_decode)
        layout.addWidget(decode_btn)

        # Events table
        events_group = self._create_events_group()
        layout.addWidget(events_group)

    def _create_protocol_group(self) -> QGroupBox:
        """Create protocol selection group.

        Returns:
            Protocol group box
        """
        group = QGroupBox("Protocol")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Type:"))

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["I2C", "SPI", "UART"])
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)
        layout.addWidget(self.protocol_combo)

        layout.addStretch()

        return group

    def _create_channel_group(self) -> QGroupBox:
        """Create channel assignment group.

        Returns:
            Channel group box
        """
        group = QGroupBox("Channel Assignment")
        self.channel_layout = QGridLayout(group)

        # Will be populated when protocol is selected
        self._update_channel_assignments()

        return group

    def _create_parameters_group(self) -> QGroupBox:
        """Create parameters group.

        Returns:
            Parameters group box
        """
        group = QGroupBox("Parameters")
        self.params_layout = QGridLayout(group)

        # Threshold (common to all protocols)
        self.params_layout.addWidget(QLabel("Threshold (V):"), 0, 0)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.1, 5.0)
        self.threshold_spin.setValue(1.4)
        self.threshold_spin.setSingleStep(0.1)
        self.threshold_spin.setDecimals(2)
        self.params_layout.addWidget(self.threshold_spin, 0, 1)

        # Protocol-specific parameters will be added here
        self.protocol_param_widgets = {}

        # Update for initial protocol
        self._update_protocol_parameters()

        return group

    def _create_events_group(self) -> QGroupBox:
        """Create decoded events table group.

        Returns:
            Events group box
        """
        group = QGroupBox("Decoded Events")
        layout = QVBoxLayout(group)

        # Events table
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(5)
        self.events_table.setHorizontalHeaderLabels(["Time (s)", "Type", "Data", "Description", "Status"])
        self.events_table.setAlternatingRowColors(True)
        layout.addWidget(self.events_table)

        # Buttons
        button_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear_events)
        button_layout.addWidget(clear_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._on_export_events)
        button_layout.addWidget(export_btn)

        button_layout.addStretch()

        # Event count label
        self.event_count_label = QLabel("0 events")
        button_layout.addWidget(self.event_count_label)

        layout.addLayout(button_layout)

        return group

    def _on_protocol_changed(self, protocol: str):
        """Handle protocol selection change.

        Args:
            protocol: Selected protocol name
        """
        self.current_protocol = protocol
        self._update_channel_assignments()
        self._update_protocol_parameters()
        logger.info(f"Protocol changed to: {protocol}")

    def _update_channel_assignments(self):
        """Update channel assignment controls based on selected protocol."""
        # Clear existing widgets
        for i in reversed(range(self.channel_layout.count())):
            self.channel_layout.itemAt(i).widget().setParent(None)

        protocol = self.protocol_combo.currentText()

        # Define required channels for each protocol
        channel_requirements = {
            "I2C": ["SDA", "SCL"],
            "SPI": ["SCK", "MOSI", "MISO", "CS"],
            "UART": ["TX", "RX"],
        }

        channels = channel_requirements.get(protocol, [])

        # Create channel assignment combos
        self.channel_combos = {}

        for i, ch_name in enumerate(channels):
            self.channel_layout.addWidget(QLabel(f"{ch_name}:"), i, 0)

            combo = QComboBox()
            combo.addItems(["C1", "C2", "C3", "C4"])
            combo.setCurrentIndex(i if i < 4 else 0)
            self.channel_layout.addWidget(combo, i, 1)

            self.channel_combos[ch_name] = combo

    def _update_protocol_parameters(self):
        """Update protocol-specific parameter controls."""
        # Remove existing protocol-specific widgets
        for widget in self.protocol_param_widgets.values():
            widget.setParent(None)
        self.protocol_param_widgets.clear()

        protocol = self.protocol_combo.currentText()
        row = 1  # Start after threshold

        if protocol == "I2C":
            # Address bits
            self.params_layout.addWidget(QLabel("Address bits:"), row, 0)
            addr_bits_combo = QComboBox()
            addr_bits_combo.addItems(["7", "10"])
            self.params_layout.addWidget(addr_bits_combo, row, 1)
            self.protocol_param_widgets["address_bits"] = addr_bits_combo

        elif protocol == "SPI":
            # CPOL
            self.params_layout.addWidget(QLabel("CPOL:"), row, 0)
            cpol_combo = QComboBox()
            cpol_combo.addItems(["0", "1"])
            self.params_layout.addWidget(cpol_combo, row, 1)
            self.protocol_param_widgets["cpol"] = cpol_combo
            row += 1

            # CPHA
            self.params_layout.addWidget(QLabel("CPHA:"), row, 0)
            cpha_combo = QComboBox()
            cpha_combo.addItems(["0", "1"])
            self.params_layout.addWidget(cpha_combo, row, 1)
            self.protocol_param_widgets["cpha"] = cpha_combo
            row += 1

            # Bits per word
            self.params_layout.addWidget(QLabel("Bits/word:"), row, 0)
            bits_spin = QSpinBox()
            bits_spin.setRange(4, 16)
            bits_spin.setValue(8)
            self.params_layout.addWidget(bits_spin, row, 1)
            self.protocol_param_widgets["bits_per_word"] = bits_spin
            row += 1

            # Bit order
            self.params_layout.addWidget(QLabel("Bit order:"), row, 0)
            bit_order_combo = QComboBox()
            bit_order_combo.addItems(["MSB", "LSB"])
            self.params_layout.addWidget(bit_order_combo, row, 1)
            self.protocol_param_widgets["bit_order"] = bit_order_combo
            row += 1

            # CS active low
            cs_check = QCheckBox("CS active low")
            cs_check.setChecked(True)
            self.params_layout.addWidget(cs_check, row, 0, 1, 2)
            self.protocol_param_widgets["cs_active_low"] = cs_check

        elif protocol == "UART":
            # Baud rate
            self.params_layout.addWidget(QLabel("Baud rate:"), row, 0)
            baud_combo = QComboBox()
            baud_combo.addItems(["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
            baud_combo.setCurrentText("9600")
            self.params_layout.addWidget(baud_combo, row, 1)
            self.protocol_param_widgets["baud_rate"] = baud_combo
            row += 1

            # Data bits
            self.params_layout.addWidget(QLabel("Data bits:"), row, 0)
            data_bits_combo = QComboBox()
            data_bits_combo.addItems(["5", "6", "7", "8", "9"])
            data_bits_combo.setCurrentText("8")
            self.params_layout.addWidget(data_bits_combo, row, 1)
            self.protocol_param_widgets["data_bits"] = data_bits_combo
            row += 1

            # Parity
            self.params_layout.addWidget(QLabel("Parity:"), row, 0)
            parity_combo = QComboBox()
            parity_combo.addItems(["none", "even", "odd", "mark", "space"])
            self.params_layout.addWidget(parity_combo, row, 1)
            self.protocol_param_widgets["parity"] = parity_combo
            row += 1

            # Stop bits
            self.params_layout.addWidget(QLabel("Stop bits:"), row, 0)
            stop_bits_combo = QComboBox()
            stop_bits_combo.addItems(["1", "1.5", "2"])
            self.params_layout.addWidget(stop_bits_combo, row, 1)
            self.protocol_param_widgets["stop_bits"] = stop_bits_combo
            row += 1

            # Idle high
            idle_check = QCheckBox("Idle state high")
            idle_check.setChecked(True)
            self.params_layout.addWidget(idle_check, row, 0, 1, 2)
            self.protocol_param_widgets["idle_high"] = idle_check

    def _on_decode(self):
        """Handle decode button click."""
        protocol = self.protocol_combo.currentText()

        # Get channel mapping
        channel_map = {}
        for ch_name, combo in self.channel_combos.items():
            channel_map[ch_name] = combo.currentText()

        # Get parameters
        params = {"threshold": self.threshold_spin.value()}

        if protocol == "I2C":
            params["address_bits"] = int(self.protocol_param_widgets["address_bits"].currentText())
        elif protocol == "SPI":
            params["cpol"] = int(self.protocol_param_widgets["cpol"].currentText())
            params["cpha"] = int(self.protocol_param_widgets["cpha"].currentText())
            params["bits_per_word"] = self.protocol_param_widgets["bits_per_word"].value()
            params["bit_order"] = self.protocol_param_widgets["bit_order"].currentText()
            params["cs_active_low"] = self.protocol_param_widgets["cs_active_low"].isChecked()
        elif protocol == "UART":
            params["baud_rate"] = int(self.protocol_param_widgets["baud_rate"].currentText())
            params["data_bits"] = int(self.protocol_param_widgets["data_bits"].currentText())
            params["parity"] = self.protocol_param_widgets["parity"].currentText()
            params["stop_bits"] = float(self.protocol_param_widgets["stop_bits"].currentText())
            params["idle_high"] = self.protocol_param_widgets["idle_high"].isChecked()

        logger.info(f"Decode requested: {protocol} with params {params}, channels {channel_map}")
        self.decode_requested.emit(protocol, params, channel_map)

    def _on_clear_events(self):
        """Handle clear events button click."""
        self.events_table.setRowCount(0)
        self.decoded_events.clear()
        self.event_count_label.setText("0 events")
        logger.info("Events cleared")

    def _on_export_events(self):
        """Handle export events button click."""
        if not self.decoded_events:
            QMessageBox.warning(self, "No Data", "No events to export")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Export Events", "", "CSV Files (*.csv);;All Files (*)")

        if filename:
            self.export_requested.emit()
            logger.info(f"Export requested: {filename}")

    def display_events(self, events: list):
        """Display decoded events in table.

        Args:
            events: List of DecodedEvent objects
        """
        self.decoded_events = events
        self.events_table.setRowCount(len(events))

        for i, event in enumerate(events):
            # Timestamp
            time_item = QTableWidgetItem(f"{event.timestamp:.6f}")
            self.events_table.setItem(i, 0, time_item)

            # Event type
            type_item = QTableWidgetItem(event.event_type.value)
            self.events_table.setItem(i, 1, type_item)

            # Data
            data_str = str(event.data) if event.data is not None else ""
            data_item = QTableWidgetItem(data_str)
            self.events_table.setItem(i, 2, data_item)

            # Description
            desc_item = QTableWidgetItem(event.description)
            self.events_table.setItem(i, 3, desc_item)

            # Status
            status_item = QTableWidgetItem("✓" if event.valid else "✗")
            if not event.valid:
                status_item.setBackground(QColor(255, 200, 200))
            self.events_table.setItem(i, 4, status_item)

        # Resize columns to content
        self.events_table.resizeColumnsToContents()

        # Update count
        self.event_count_label.setText(f"{len(events)} events")

        logger.info(f"Displayed {len(events)} events")

    def get_events(self) -> list:
        """Get current decoded events.

        Returns:
            List of decoded events
        """
        return self.decoded_events
