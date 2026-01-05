"""Timebase control widget for oscilloscope GUI."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from siglent import Oscilloscope

logger = logging.getLogger(__name__)


class TimebaseControl(QWidget):
    """Widget for controlling oscilloscope timebase (horizontal) settings."""

    # Standard time/div values
    TIME_SCALES = [
        1e-9,  # 1 ns
        2e-9,  # 2 ns
        5e-9,  # 5 ns
        10e-9,  # 10 ns
        20e-9,  # 20 ns
        50e-9,  # 50 ns
        100e-9,  # 100 ns
        200e-9,  # 200 ns
        500e-9,  # 500 ns
        1e-6,  # 1 µs
        2e-6,  # 2 µs
        5e-6,  # 5 µs
        10e-6,  # 10 µs
        20e-6,  # 20 µs
        50e-6,  # 50 µs
        100e-6,  # 100 µs
        200e-6,  # 200 µs
        500e-6,  # 500 µs
        1e-3,  # 1 ms
        2e-3,  # 2 ms
        5e-3,  # 5 ms
        10e-3,  # 10 ms
        20e-3,  # 20 ms
        50e-3,  # 50 ms
        100e-3,  # 100 ms
        200e-3,  # 200 ms
        500e-3,  # 500 ms
        1.0,  # 1 s
        2.0,  # 2 s
        5.0,  # 5 s
        10.0,  # 10 s
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize timebase control widget.

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

        # Timebase settings group
        settings_group = QGroupBox("Horizontal Settings")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setColumnStretch(1, 1)

        # Row 0: Time/div
        settings_layout.addWidget(QLabel("Time/div:"), 0, 0)
        time_scale_combo = QComboBox()
        for scale in self.TIME_SCALES:
            time_scale_combo.addItem(self._format_time_scale(scale), scale)
        time_scale_combo.setCurrentIndex(15)  # Default to 100 µs
        time_scale_combo.currentIndexChanged.connect(self._on_time_scale_changed)
        settings_layout.addWidget(time_scale_combo, 0, 1)
        self.widgets["time_scale"] = time_scale_combo

        # Row 1: Delay (offset)
        settings_layout.addWidget(QLabel("Delay:"), 1, 0)
        delay_spin = QDoubleSpinBox()
        delay_spin.setDecimals(9)
        delay_spin.setMinimum(-10.0)
        delay_spin.setMaximum(10.0)
        delay_spin.setValue(0.0)
        delay_spin.setSuffix(" s")
        delay_spin.setSingleStep(1e-6)
        delay_spin.valueChanged.connect(self._on_delay_changed)
        settings_layout.addWidget(delay_spin, 1, 1)
        self.widgets["delay"] = delay_spin

        # Row 2: Sample rate (read-only display)
        settings_layout.addWidget(QLabel("Sample Rate:"), 2, 0)
        sample_rate_label = QLabel("---")
        settings_layout.addWidget(sample_rate_label, 2, 1)
        self.widgets["sample_rate"] = sample_rate_label

        # Row 3: Memory depth (read-only display)
        settings_layout.addWidget(QLabel("Memory Depth:"), 3, 0)
        memory_depth_label = QLabel("---")
        settings_layout.addWidget(memory_depth_label, 3, 1)
        self.widgets["memory_depth"] = memory_depth_label

        layout.addWidget(settings_group)

        # Quick action buttons
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout(actions_group)

        refresh_btn = QPushButton("Refresh Settings")
        refresh_btn.clicked.connect(self._on_refresh)
        actions_layout.addWidget(refresh_btn)

        zoom_in_btn = QPushButton("Zoom In (Faster Time)")
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        actions_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("Zoom Out (Slower Time)")
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        actions_layout.addWidget(zoom_out_btn)

        reset_delay_btn = QPushButton("Reset Delay to 0")
        reset_delay_btn.clicked.connect(self._on_reset_delay)
        actions_layout.addWidget(reset_delay_btn)

        layout.addWidget(actions_group)

        # Info label
        info_label = QLabel("<b>Timebase Info:</b><br>" "• Time/div controls horizontal zoom<br>" "• Delay shifts the waveform left/right<br>" "• Sample rate depends on time/div setting")
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
            self._refresh_settings()

    def _format_time_scale(self, value: float) -> str:
        """Format time scale for display.

        Args:
            value: Time scale in seconds

        Returns:
            Formatted string
        """
        if value >= 1.0:
            return f"{value:.0f} s"
        elif value >= 1e-3:
            return f"{value*1e3:.0f} ms"
        elif value >= 1e-6:
            return f"{value*1e6:.0f} µs"
        else:
            return f"{value*1e9:.0f} ns"

    def _refresh_settings(self):
        """Refresh timebase settings from oscilloscope."""
        if not self.scope:
            return

        try:
            # Query time scale (TDIV)
            tdiv_str = self.scope.query("TDIV?")
            # Response may include echo like "TDIV 1.0E-06S"
            if " " in tdiv_str:
                tdiv_str = tdiv_str.split(" ", 1)[1]
            tdiv_str = tdiv_str.replace("S", "").strip()
            tdiv = float(tdiv_str)

            # Find matching index
            for i, scale in enumerate(self.TIME_SCALES):
                if abs(scale - tdiv) < 1e-12:
                    self.widgets["time_scale"].blockSignals(True)
                    self.widgets["time_scale"].setCurrentIndex(i)
                    self.widgets["time_scale"].blockSignals(False)
                    break

            # Query time delay (TRDL)
            try:
                trdl_str = self.scope.query("TRDL?")
                # Response may include echo like "TRDL 0.0E+00S"
                if " " in trdl_str:
                    trdl_str = trdl_str.split(" ", 1)[1]
                trdl_str = trdl_str.replace("S", "").strip()
                trdl = float(trdl_str)
                self.widgets["delay"].blockSignals(True)
                self.widgets["delay"].setValue(trdl)
                self.widgets["delay"].blockSignals(False)
            except Exception:
                pass

            # Query sample rate (SARA?)
            try:
                sara_str = self.scope.query("SARA?")
                sara = float(sara_str.strip())
                self.widgets["sample_rate"].setText(self._format_sample_rate(sara))
            except Exception:
                self.widgets["sample_rate"].setText("---")

            # Query memory depth (MSIZ?)
            try:
                msiz_str = self.scope.query("MSIZ?")
                self.widgets["memory_depth"].setText(msiz_str.strip())
            except Exception:
                self.widgets["memory_depth"].setText("---")

        except Exception as e:
            logger.warning(f"Could not refresh timebase settings: {e}")

    def _format_sample_rate(self, rate: float) -> str:
        """Format sample rate for display.

        Args:
            rate: Sample rate in Sa/s

        Returns:
            Formatted string
        """
        if rate >= 1e9:
            return f"{rate/1e9:.2f} GSa/s"
        elif rate >= 1e6:
            return f"{rate/1e6:.2f} MSa/s"
        elif rate >= 1e3:
            return f"{rate/1e3:.2f} kSa/s"
        else:
            return f"{rate:.0f} Sa/s"

    def _on_time_scale_changed(self, index: int):
        """Handle time scale change.

        Args:
            index: Combo box index
        """
        if not self.scope:
            return

        try:
            scale = self.TIME_SCALES[index]
            self.scope.write(f"TDIV {scale}")
            logger.info(f"Time/div: {self._format_time_scale(scale)}")

            # Refresh sample rate and memory depth
            self._refresh_settings()

        except Exception as e:
            logger.error(f"Failed to set time scale: {e}")

    def _on_delay_changed(self, delay: float):
        """Handle delay change.

        Args:
            delay: Delay value in seconds
        """
        if not self.scope:
            return

        try:
            self.scope.write(f"TRDL {delay}")
            logger.info(f"Time delay: {delay} s")
        except Exception as e:
            logger.error(f"Failed to set time delay: {e}")

    def _on_refresh(self):
        """Handle refresh button."""
        self._refresh_settings()
        logger.info("Refreshed timebase settings")

    def _on_zoom_in(self):
        """Zoom in (decrease time/div)."""
        current_index = self.widgets["time_scale"].currentIndex()
        if current_index > 0:
            self.widgets["time_scale"].setCurrentIndex(current_index - 1)

    def _on_zoom_out(self):
        """Zoom out (increase time/div)."""
        current_index = self.widgets["time_scale"].currentIndex()
        if current_index < len(self.TIME_SCALES) - 1:
            self.widgets["time_scale"].setCurrentIndex(current_index + 1)

    def _on_reset_delay(self):
        """Reset delay to 0."""
        self.widgets["delay"].setValue(0.0)
