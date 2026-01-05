"""Trigger control widget for oscilloscope GUI."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from siglent import Oscilloscope

logger = logging.getLogger(__name__)


class TriggerControl(QWidget):
    """Widget for controlling oscilloscope trigger settings."""

    # Trigger modes
    TRIGGER_MODES = ["AUTO", "NORMAL", "SINGLE", "STOP"]

    # Trigger sources
    TRIGGER_SOURCES = ["C1", "C2", "C3", "C4", "EX", "LINE"]

    # Trigger slopes
    TRIGGER_SLOPES = ["POS", "NEG"]

    # Trigger coupling
    TRIGGER_COUPLING = ["DC", "AC", "HFREJ", "LFREJ"]

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize trigger control widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.scope: Optional[Oscilloscope] = None
        self.widgets = {}
        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Trigger settings group
        settings_group = QGroupBox("Trigger Settings")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setColumnStretch(1, 1)

        # Row 0: Trigger mode
        settings_layout.addWidget(QLabel("Mode:"), 0, 0)
        mode_combo = QComboBox()
        mode_combo.addItems(self.TRIGGER_MODES)
        mode_combo.setCurrentText("AUTO")
        mode_combo.currentTextChanged.connect(self._on_mode_changed)
        settings_layout.addWidget(mode_combo, 0, 1)
        self.widgets["mode"] = mode_combo

        # Row 1: Trigger source
        settings_layout.addWidget(QLabel("Source:"), 1, 0)
        source_combo = QComboBox()
        source_combo.addItems(self.TRIGGER_SOURCES)
        source_combo.setCurrentText("C1")
        source_combo.currentTextChanged.connect(self._on_source_changed)
        settings_layout.addWidget(source_combo, 1, 1)
        self.widgets["source"] = source_combo

        # Row 2: Trigger slope
        settings_layout.addWidget(QLabel("Slope:"), 2, 0)
        slope_combo = QComboBox()
        slope_combo.addItems(self.TRIGGER_SLOPES)
        slope_combo.setCurrentText("POS")
        slope_combo.currentTextChanged.connect(self._on_slope_changed)
        settings_layout.addWidget(slope_combo, 2, 1)
        self.widgets["slope"] = slope_combo

        # Row 3: Trigger level
        settings_layout.addWidget(QLabel("Level:"), 3, 0)
        level_spin = QDoubleSpinBox()
        level_spin.setDecimals(3)
        level_spin.setMinimum(-10.0)
        level_spin.setMaximum(10.0)
        level_spin.setValue(0.0)
        level_spin.setSuffix(" V")
        level_spin.setSingleStep(0.1)
        level_spin.valueChanged.connect(self._on_level_changed)
        settings_layout.addWidget(level_spin, 3, 1)
        self.widgets["level"] = level_spin

        # Row 4: Trigger coupling
        settings_layout.addWidget(QLabel("Coupling:"), 4, 0)
        coupling_combo = QComboBox()
        coupling_combo.addItems(self.TRIGGER_COUPLING)
        coupling_combo.setCurrentText("DC")
        coupling_combo.currentTextChanged.connect(self._on_coupling_changed)
        settings_layout.addWidget(coupling_combo, 4, 1)
        self.widgets["coupling"] = coupling_combo

        # Row 5: Holdoff
        settings_layout.addWidget(QLabel("Holdoff:"), 5, 0)
        holdoff_spin = QDoubleSpinBox()
        holdoff_spin.setDecimals(6)
        holdoff_spin.setMinimum(0.0)
        holdoff_spin.setMaximum(10.0)
        holdoff_spin.setValue(0.0)
        holdoff_spin.setSuffix(" s")
        holdoff_spin.setSingleStep(0.000001)
        holdoff_spin.valueChanged.connect(self._on_holdoff_changed)
        settings_layout.addWidget(holdoff_spin, 5, 1)
        self.widgets["holdoff"] = holdoff_spin

        layout.addWidget(settings_group)

        # Quick action buttons
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout(actions_group)

        force_btn = QPushButton("Force Trigger")
        force_btn.clicked.connect(self._on_force_trigger)
        actions_layout.addWidget(force_btn)

        set_50_btn = QPushButton("Set Level to 50%")
        set_50_btn.clicked.connect(self._on_set_level_50)
        actions_layout.addWidget(set_50_btn)

        layout.addWidget(actions_group)

        # Info label
        info_label = QLabel(
            "<b>Trigger Mode Info:</b><br>"
            "<b>AUTO:</b> Always triggers (free-run if no signal)<br>"
            "<b>NORMAL:</b> Triggers only on valid events<br>"
            "<b>SINGLE:</b> Triggers once then stops<br>"
            "<b>STOP:</b> Stops acquisition"
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
        if scope:
            self._refresh_trigger_settings()

    def _refresh_trigger_settings(self):
        """Refresh trigger settings from oscilloscope."""
        if not self.scope:
            return

        try:
            # Block signals while updating
            for widget in self.widgets.values():
                widget.blockSignals(True)

            # Update values
            self.widgets["mode"].setCurrentText(self.scope.trigger.mode)
            self.widgets["source"].setCurrentText(self.scope.trigger.source)
            self.widgets["slope"].setCurrentText(self.scope.trigger.slope)
            self.widgets["level"].setValue(self.scope.trigger.level)
            self.widgets["coupling"].setCurrentText(self.scope.trigger.coupling)

            try:
                holdoff = self.scope.trigger.holdoff
                self.widgets["holdoff"].setValue(holdoff)
            except Exception:
                pass  # Holdoff might not be supported

        except Exception as e:
            logger.warning(f"Could not refresh trigger settings: {e}")

        finally:
            # Unblock signals
            for widget in self.widgets.values():
                widget.blockSignals(False)

    def _on_mode_changed(self, mode: str):
        """Handle trigger mode change.

        Args:
            mode: Trigger mode
        """
        if not self.scope:
            return

        try:
            self.scope.trigger.mode = mode
            logger.info(f"Trigger mode: {mode}")
        except Exception as e:
            logger.error(f"Failed to set trigger mode: {e}")

    def _on_source_changed(self, source: str):
        """Handle trigger source change.

        Args:
            source: Trigger source
        """
        if not self.scope:
            return

        try:
            self.scope.trigger.source = source
            logger.info(f"Trigger source: {source}")
        except Exception as e:
            logger.error(f"Failed to set trigger source: {e}")

    def _on_slope_changed(self, slope: str):
        """Handle trigger slope change.

        Args:
            slope: Trigger slope
        """
        if not self.scope:
            return

        try:
            self.scope.trigger.slope = slope
            logger.info(f"Trigger slope: {slope}")
        except Exception as e:
            logger.error(f"Failed to set trigger slope: {e}")

    def _on_level_changed(self, level: float):
        """Handle trigger level change.

        Args:
            level: Trigger level in V
        """
        if not self.scope:
            return

        try:
            self.scope.trigger.level = level
            logger.info(f"Trigger level: {level} V")
        except Exception as e:
            logger.error(f"Failed to set trigger level: {e}")

    def _on_coupling_changed(self, coupling: str):
        """Handle trigger coupling change.

        Args:
            coupling: Trigger coupling
        """
        if not self.scope:
            return

        try:
            self.scope.trigger.coupling = coupling
            logger.info(f"Trigger coupling: {coupling}")
        except Exception as e:
            logger.error(f"Failed to set trigger coupling: {e}")

    def _on_holdoff_changed(self, holdoff: float):
        """Handle trigger holdoff change.

        Args:
            holdoff: Holdoff time in seconds
        """
        if not self.scope:
            return

        try:
            self.scope.trigger.holdoff = holdoff
            logger.info(f"Trigger holdoff: {holdoff} s")
        except Exception as e:
            logger.error(f"Failed to set trigger holdoff: {e}")

    def _on_force_trigger(self):
        """Handle force trigger button."""
        if not self.scope:
            return

        try:
            self.scope.trigger.force()
            logger.info("Forced trigger")
        except Exception as e:
            logger.error(f"Failed to force trigger: {e}")

    def _on_set_level_50(self):
        """Set trigger level to 50% of signal."""
        if not self.scope:
            return

        try:
            # This is a simplified version - a more sophisticated implementation
            # would read the actual signal amplitude and set to 50%
            # For now, just set to 0V
            self.scope.trigger.level = 0.0
            self.widgets["level"].setValue(0.0)
            logger.info("Set trigger level to 0V (50%)")
        except Exception as e:
            logger.error(f"Failed to set trigger level: {e}")
