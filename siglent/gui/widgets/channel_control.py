"""Channel control widget for oscilloscope GUI."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from siglent import Oscilloscope
from siglent.channel import Channel

logger = logging.getLogger(__name__)


class ChannelControl(QWidget):
    """Widget for controlling oscilloscope channels."""

    # Standard voltage scales (V/div)
    VOLTAGE_SCALES = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]

    # Coupling modes
    COUPLING_MODES = ["DC", "AC", "GND"]

    # Probe ratios
    PROBE_RATIOS = [
        0.01,
        0.02,
        0.05,
        0.1,
        0.2,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
        20.0,
        50.0,
        100.0,
        200.0,
        500.0,
        1000.0,
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize channel control widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.scope: Optional[Oscilloscope] = None
        self.channel_widgets = {}
        self.channel_groups = {}  # Store group boxes for show/hide
        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create controls for all possible channels (1-4)
        # Visibility will be adjusted based on model capability
        for ch_num in range(1, 5):  # Channels 1-4
            channel_group = self._create_channel_group(ch_num)
            layout.addWidget(channel_group)
            self.channel_groups[ch_num] = channel_group

        layout.addStretch()

    def _create_channel_group(self, channel_num: int) -> QGroupBox:
        """Create control group for a single channel.

        Args:
            channel_num: Channel number (1-4)

        Returns:
            Channel control group widget
        """
        # Channel colors matching waveform display
        colors = {
            1: "#FFD700",  # Yellow/Gold
            2: "#00CED1",  # Cyan
            3: "#FF1493",  # Deep Pink/Magenta
            4: "#00FF00",  # Green
        }

        group = QGroupBox(f"Channel {channel_num}")
        group.setStyleSheet(f"QGroupBox::title {{ color: {colors[channel_num]}; font-weight: bold; }}")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        widgets = {}

        # Row 0: Enable checkbox and auto-scale button
        enable_cb = QCheckBox("Enable")
        enable_cb.toggled.connect(lambda checked: self._on_channel_enabled(channel_num, checked))
        layout.addWidget(enable_cb, 0, 0, 1, 2)
        widgets["enable"] = enable_cb

        auto_scale_btn = QPushButton("Auto Scale")
        auto_scale_btn.clicked.connect(lambda: self._on_auto_scale(channel_num))
        layout.addWidget(auto_scale_btn, 0, 2)

        # Row 1: Voltage scale
        layout.addWidget(QLabel("V/div:"), 1, 0)
        scale_spin = QDoubleSpinBox()
        scale_spin.setDecimals(3)
        scale_spin.setMinimum(0.001)
        scale_spin.setMaximum(10.0)
        scale_spin.setValue(1.0)
        scale_spin.setSuffix(" V")
        scale_spin.valueChanged.connect(lambda val: self._on_scale_changed(channel_num, val))
        layout.addWidget(scale_spin, 1, 1, 1, 2)
        widgets["scale"] = scale_spin

        # Row 2: Coupling
        layout.addWidget(QLabel("Coupling:"), 2, 0)
        coupling_combo = QComboBox()
        coupling_combo.addItems(self.COUPLING_MODES)
        coupling_combo.currentTextChanged.connect(lambda val: self._on_coupling_changed(channel_num, val))
        layout.addWidget(coupling_combo, 2, 1, 1, 2)
        widgets["coupling"] = coupling_combo

        # Row 3: Offset
        layout.addWidget(QLabel("Offset:"), 3, 0)
        offset_spin = QDoubleSpinBox()
        offset_spin.setDecimals(3)
        offset_spin.setMinimum(-10.0)
        offset_spin.setMaximum(10.0)
        offset_spin.setValue(0.0)
        offset_spin.setSuffix(" V")
        offset_spin.setSingleStep(0.1)
        offset_spin.valueChanged.connect(lambda val: self._on_offset_changed(channel_num, val))
        layout.addWidget(offset_spin, 3, 1, 1, 2)
        widgets["offset"] = offset_spin

        # Row 4: Probe ratio
        layout.addWidget(QLabel("Probe:"), 4, 0)
        probe_combo = QComboBox()
        probe_combo.addItems([f"{p}X" for p in self.PROBE_RATIOS])
        probe_combo.setCurrentText("10X")
        probe_combo.currentTextChanged.connect(lambda val: self._on_probe_changed(channel_num, val))
        layout.addWidget(probe_combo, 4, 1, 1, 2)
        widgets["probe"] = probe_combo

        # Row 5: Bandwidth limit
        bw_cb = QCheckBox("Bandwidth Limit (20MHz)")
        bw_cb.toggled.connect(lambda checked: self._on_bw_limit_changed(channel_num, checked))
        layout.addWidget(bw_cb, 5, 0, 1, 3)
        widgets["bw_limit"] = bw_cb

        self.channel_widgets[channel_num] = widgets

        return group

    def set_scope(self, scope: Optional[Oscilloscope]):
        """Set the oscilloscope instance.

        Updates channel visibility based on model capability and refreshes controls.

        Args:
            scope: Oscilloscope instance
        """
        self.scope = scope
        if scope and scope.model_capability:
            # Show/hide channels based on model capability
            num_channels = scope.model_capability.num_channels
            logger.info(f"Configuring GUI for {num_channels} channels")

            for ch_num in range(1, 5):
                group = self.channel_groups.get(ch_num)
                if group:
                    if ch_num <= num_channels:
                        group.setVisible(True)
                        group.setEnabled(True)
                    else:
                        group.setVisible(False)
                        group.setEnabled(False)

            self._refresh_all_channels()
        elif scope:
            # Scope connected but no capability info - show all channels
            logger.warning("Scope connected but model capability not available, showing all channels")
            for ch_num in range(1, 5):
                group = self.channel_groups.get(ch_num)
                if group:
                    group.setVisible(True)
                    group.setEnabled(True)
            self._refresh_all_channels()
        else:
            # No scope - hide all channels
            for ch_num in range(1, 5):
                group = self.channel_groups.get(ch_num)
                if group:
                    group.setVisible(False)
                    group.setEnabled(False)

    def _refresh_all_channels(self):
        """Refresh all channel controls from oscilloscope.

        Only refreshes channels that are available on the connected model.
        """
        if not self.scope:
            return

        # Get supported channels from oscilloscope
        supported_channels = self.scope.supported_channels if hasattr(self.scope, "supported_channels") else range(1, 5)

        for ch_num in supported_channels:
            try:
                channel = getattr(self.scope, f"channel{ch_num}", None)
                if channel:
                    self._refresh_channel(ch_num, channel)
            except Exception as e:
                logger.warning(f"Could not refresh channel {ch_num}: {e}")

    def _refresh_channel(self, ch_num: int, channel: Channel):
        """Refresh channel controls from oscilloscope.

        Args:
            ch_num: Channel number
            channel: Channel instance
        """
        widgets = self.channel_widgets.get(ch_num)
        if not widgets:
            return

        try:
            # Block signals while updating to avoid triggering changes
            for widget in widgets.values():
                widget.blockSignals(True)

            # Update values
            widgets["enable"].setChecked(channel.enabled)
            widgets["scale"].setValue(channel.voltage_scale)
            widgets["coupling"].setCurrentText(channel.coupling)
            widgets["offset"].setValue(channel.voltage_offset)

            probe_text = f"{channel.probe_ratio}X"
            idx = widgets["probe"].findText(probe_text)
            if idx >= 0:
                widgets["probe"].setCurrentIndex(idx)

            widgets["bw_limit"].setChecked(channel.bandwidth_limit == "ON")

        finally:
            # Unblock signals
            for widget in widgets.values():
                widget.blockSignals(False)

    def _on_channel_enabled(self, ch_num: int, enabled: bool):
        """Handle channel enable/disable.

        Args:
            ch_num: Channel number
            enabled: Enable state
        """
        if not self.scope:
            return

        try:
            channel = getattr(self.scope, f"channel{ch_num}")
            if enabled:
                channel.enable()
                logger.info(f"Enabled channel {ch_num}")
            else:
                channel.disable()
                logger.info(f"Disabled channel {ch_num}")
        except Exception as e:
            logger.error(f"Failed to set channel {ch_num} enable state: {e}")

    def _on_scale_changed(self, ch_num: int, scale: float):
        """Handle voltage scale change.

        Args:
            ch_num: Channel number
            scale: Voltage scale in V/div
        """
        if not self.scope:
            return

        try:
            channel = getattr(self.scope, f"channel{ch_num}")
            channel.voltage_scale = scale
            logger.info(f"Channel {ch_num} scale: {scale} V/div")
        except Exception as e:
            logger.error(f"Failed to set channel {ch_num} scale: {e}")

    def _on_coupling_changed(self, ch_num: int, coupling: str):
        """Handle coupling mode change.

        Args:
            ch_num: Channel number
            coupling: Coupling mode (DC/AC/GND)
        """
        if not self.scope:
            return

        try:
            channel = getattr(self.scope, f"channel{ch_num}")
            channel.coupling = coupling
            logger.info(f"Channel {ch_num} coupling: {coupling}")
        except Exception as e:
            logger.error(f"Failed to set channel {ch_num} coupling: {e}")

    def _on_offset_changed(self, ch_num: int, offset: float):
        """Handle offset change.

        Args:
            ch_num: Channel number
            offset: Voltage offset in V
        """
        if not self.scope:
            return

        try:
            channel = getattr(self.scope, f"channel{ch_num}")
            channel.voltage_offset = offset
            logger.info(f"Channel {ch_num} offset: {offset} V")
        except Exception as e:
            logger.error(f"Failed to set channel {ch_num} offset: {e}")

    def _on_probe_changed(self, ch_num: int, probe_text: str):
        """Handle probe ratio change.

        Args:
            ch_num: Channel number
            probe_text: Probe ratio text (e.g., "10X")
        """
        if not self.scope:
            return

        try:
            # Extract number from text
            probe_ratio = float(probe_text.replace("X", ""))
            channel = getattr(self.scope, f"channel{ch_num}")
            channel.probe_ratio = probe_ratio
            logger.info(f"Channel {ch_num} probe ratio: {probe_ratio}X")
        except Exception as e:
            logger.error(f"Failed to set channel {ch_num} probe ratio: {e}")

    def _on_bw_limit_changed(self, ch_num: int, enabled: bool):
        """Handle bandwidth limit change.

        Args:
            ch_num: Channel number
            enabled: Bandwidth limit state
        """
        if not self.scope:
            return

        try:
            channel = getattr(self.scope, f"channel{ch_num}")
            channel.bandwidth_limit = "ON" if enabled else "OFF"
            logger.info(f"Channel {ch_num} BW limit: {'ON' if enabled else 'OFF'}")
        except Exception as e:
            logger.error(f"Failed to set channel {ch_num} BW limit: {e}")

    def _on_auto_scale(self, ch_num: int):
        """Handle auto-scale button.

        Args:
            ch_num: Channel number
        """
        if not self.scope:
            return

        try:
            channel = getattr(self.scope, f"channel{ch_num}")
            # Enable channel if not already enabled
            if not channel.enabled:
                channel.enable()
                widgets = self.channel_widgets.get(ch_num)
                if widgets:
                    widgets["enable"].blockSignals(True)
                    widgets["enable"].setChecked(True)
                    widgets["enable"].blockSignals(False)

            # Run auto setup for the scope
            self.scope.auto_setup()

            # Refresh this channel's settings
            self._refresh_channel(ch_num, channel)

            logger.info(f"Auto-scaled channel {ch_num}")
        except Exception as e:
            logger.error(f"Failed to auto-scale channel {ch_num}: {e}")
