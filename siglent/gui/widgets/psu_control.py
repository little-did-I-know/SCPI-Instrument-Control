"""Power supply control widget for GUI."""

import logging
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from siglent import PowerSupply

logger = logging.getLogger(__name__)


class PSUControl(QWidget):
    """Widget for controlling power supply outputs."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize PSU control widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.psu: Optional[PowerSupply] = None
        self.output_widgets = {}
        self.output_groups = {}  # Store group boxes for show/hide
        self.update_timer: Optional[QTimer] = None
        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create controls for all possible outputs (1-3)
        # Visibility will be adjusted based on model capability
        for output_num in range(1, 4):  # Outputs 1-3
            output_group = self._create_output_group(output_num)
            layout.addWidget(output_group)
            self.output_groups[output_num] = output_group

        # Safety: All Outputs OFF button
        all_off_btn = QPushButton("⚠ All Outputs OFF (Safety)")
        all_off_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #DC143C;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #B22222;
            }
        """
        )
        all_off_btn.clicked.connect(self._on_all_off)
        layout.addWidget(all_off_btn)

        layout.addStretch()

    def _create_output_group(self, output_num: int) -> QGroupBox:
        """Create control group for a single output.

        Args:
            output_num: Output number (1-3)

        Returns:
            Output control group widget
        """
        # Output colors
        colors = {
            1: "#FFD700",  # Yellow/Gold
            2: "#00CED1",  # Cyan
            3: "#FF1493",  # Deep Pink/Magenta
        }

        group = QGroupBox(f"Output {output_num}")
        group.setStyleSheet(f"QGroupBox::title {{ color: {colors[output_num]}; font-weight: bold; }}")
        layout = QGridLayout(group)
        layout.setColumnStretch(1, 1)

        widgets = {}

        # Row 0: Enable checkbox
        enable_cb = QCheckBox("Enable Output")
        enable_cb.setStyleSheet("font-weight: bold;")
        enable_cb.toggled.connect(lambda checked: self._on_output_enabled(output_num, checked))
        layout.addWidget(enable_cb, 0, 0, 1, 3)
        widgets["enable"] = enable_cb

        # Row 1: Voltage setpoint
        layout.addWidget(QLabel("Voltage:"), 1, 0)
        voltage_spin = QDoubleSpinBox()
        voltage_spin.setDecimals(3)
        voltage_spin.setMinimum(0.0)
        voltage_spin.setMaximum(30.0)  # Will be updated based on model
        voltage_spin.setValue(0.0)
        voltage_spin.setSuffix(" V")
        voltage_spin.setSingleStep(0.1)
        voltage_spin.valueChanged.connect(lambda val: self._on_voltage_changed(output_num, val))
        layout.addWidget(voltage_spin, 1, 1, 1, 2)
        widgets["voltage"] = voltage_spin

        # Row 2: Current limit
        layout.addWidget(QLabel("Current:"), 2, 0)
        current_spin = QDoubleSpinBox()
        current_spin.setDecimals(3)
        current_spin.setMinimum(0.0)
        current_spin.setMaximum(3.0)  # Will be updated based on model
        current_spin.setValue(0.0)
        current_spin.setSuffix(" A")
        current_spin.setSingleStep(0.01)
        current_spin.valueChanged.connect(lambda val: self._on_current_changed(output_num, val))
        layout.addWidget(current_spin, 2, 1, 1, 2)
        widgets["current"] = current_spin

        # Separator
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #444;")
        layout.addWidget(separator, 3, 0, 1, 3)

        # Row 4: Measured voltage (read-only)
        layout.addWidget(QLabel("Measured V:"), 4, 0)
        voltage_display = QLabel("0.000 V")
        voltage_display.setStyleSheet("font-weight: bold; color: #00FF00;")
        layout.addWidget(voltage_display, 4, 1, 1, 2)
        widgets["voltage_display"] = voltage_display

        # Row 5: Measured current (read-only)
        layout.addWidget(QLabel("Measured I:"), 5, 0)
        current_display = QLabel("0.000 A")
        current_display.setStyleSheet("font-weight: bold; color: #00FF00;")
        layout.addWidget(current_display, 5, 1, 1, 2)
        widgets["current_display"] = current_display

        # Row 6: Measured power (read-only)
        layout.addWidget(QLabel("Power:"), 6, 0)
        power_display = QLabel("0.000 W")
        power_display.setStyleSheet("font-weight: bold; color: #00FF00;")
        layout.addWidget(power_display, 6, 1, 1, 2)
        widgets["power_display"] = power_display

        # Row 7: Operating mode (CV/CC)
        layout.addWidget(QLabel("Mode:"), 7, 0)
        mode_display = QLabel("---")
        mode_display.setStyleSheet("font-weight: bold; color: #FFD700;")
        layout.addWidget(mode_display, 7, 1, 1, 2)
        widgets["mode_display"] = mode_display

        self.output_widgets[output_num] = widgets
        return group

    def set_psu(self, psu: Optional[PowerSupply]):
        """Set PSU instance and configure UI.

        Args:
            psu: PowerSupply instance or None to disconnect
        """
        # Stop existing update timer
        if self.update_timer:
            self.update_timer.stop()
            self.update_timer = None

        self.psu = psu

        if psu and psu.model_capability:
            logger.info(f"Configuring UI for {psu.model_capability.model_name}")

            # Show/hide outputs based on model
            for output_num in range(1, 4):
                group = self.output_groups[output_num]
                if output_num <= psu.model_capability.num_outputs:
                    group.setVisible(True)

                    # Update ranges from spec
                    spec = psu.model_capability.output_specs[output_num - 1]
                    widgets = self.output_widgets[output_num]

                    # Update voltage range
                    widgets["voltage"].setMaximum(spec.max_voltage)
                    widgets["voltage"].setSingleStep(spec.voltage_resolution * 10)

                    # Update current range
                    widgets["current"].setMaximum(spec.max_current)
                    widgets["current"].setSingleStep(spec.current_resolution * 10)

                    # Read and set current values
                    try:
                        output = getattr(psu, f"output{output_num}")
                        widgets["voltage"].setValue(output.voltage)
                        widgets["current"].setValue(output.current)
                        widgets["enable"].setChecked(output.enabled)
                    except Exception as e:
                        logger.error(f"Failed to read output {output_num} state: {e}")
                else:
                    group.setVisible(False)

            # Start measurement update timer
            self._start_measurement_updates()

        else:
            # No PSU connected - hide all outputs
            for group in self.output_groups.values():
                group.setVisible(False)

    def _start_measurement_updates(self):
        """Start timer to periodically update measurements."""
        if not self.psu:
            return

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_measurements)
        self.update_timer.start(1000)  # Update every second
        logger.info("Started PSU measurement updates (1s interval)")

    def _update_measurements(self):
        """Update measurement displays."""
        if not self.psu:
            return

        for output_num in range(1, self.psu.model_capability.num_outputs + 1):
            try:
                output = getattr(self.psu, f"output{output_num}")
                widgets = self.output_widgets[output_num]

                # Read measurements
                v = output.measure_voltage()
                i = output.measure_current()
                p = output.measure_power()

                # Update displays
                widgets["voltage_display"].setText(f"{v:.3f} V")
                widgets["current_display"].setText(f"{i:.3f} A")
                widgets["power_display"].setText(f"{p:.2f} W")

                # Update mode
                try:
                    mode = output.get_mode()
                    widgets["mode_display"].setText(mode)

                    # Color code based on mode
                    if "CV" in mode.upper():
                        widgets["mode_display"].setStyleSheet("font-weight: bold; color: #00FF00;")  # Green for CV
                    elif "CC" in mode.upper():
                        widgets["mode_display"].setStyleSheet("font-weight: bold; color: #FFA500;")  # Orange for CC
                except Exception:
                    widgets["mode_display"].setText("---")

            except Exception as e:
                logger.error(f"Failed to update output {output_num} measurements: {e}")

    # Event handlers

    def _on_output_enabled(self, output_num: int, checked: bool):
        """Handle output enable/disable.

        Args:
            output_num: Output number
            checked: True if enabled, False if disabled
        """
        if not self.psu:
            return

        try:
            output = getattr(self.psu, f"output{output_num}")
            output.enabled = checked
            logger.info(f"Output {output_num} {'enabled' if checked else 'disabled'}")
        except Exception as e:
            logger.error(f"Failed to set output {output_num} enable state: {e}")

    def _on_voltage_changed(self, output_num: int, voltage: float):
        """Handle voltage setpoint change.

        Args:
            output_num: Output number
            voltage: Voltage setpoint in volts
        """
        if not self.psu:
            return

        try:
            output = getattr(self.psu, f"output{output_num}")
            output.voltage = voltage
            logger.debug(f"Output {output_num} voltage set to {voltage}V")
        except Exception as e:
            logger.error(f"Failed to set output {output_num} voltage: {e}")

    def _on_current_changed(self, output_num: int, current: float):
        """Handle current limit change.

        Args:
            output_num: Output number
            current: Current limit in amps
        """
        if not self.psu:
            return

        try:
            output = getattr(self.psu, f"output{output_num}")
            output.current = current
            logger.debug(f"Output {output_num} current limit set to {current}A")
        except Exception as e:
            logger.error(f"Failed to set output {output_num} current: {e}")

    def _on_all_off(self):
        """Handle all outputs off (safety feature)."""
        if not self.psu:
            logger.warning("No PSU connected")
            return

        try:
            logger.warning("Safety: Turning off all PSU outputs")
            self.psu.all_outputs_off()

            # Update UI checkboxes
            for output_num in range(1, self.psu.model_capability.num_outputs + 1):
                widgets = self.output_widgets[output_num]
                widgets["enable"].setChecked(False)

        except Exception as e:
            logger.error(f"Failed to turn off all outputs: {e}")
