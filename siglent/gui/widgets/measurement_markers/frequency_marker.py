"""Frequency/Period measurement marker."""

import logging
from typing import Optional

import numpy as np
from scipy import signal

from siglent.gui.widgets.measurement_marker import MeasurementMarker
from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class FrequencyMarker(MeasurementMarker):
    """Marker for frequency and period measurements.

    Visual representation:
    - Two vertical dashed lines spanning one cycle
    - Curved arc connecting the lines at top
    - Label showing frequency or period value
    - Draggable handles at line positions
    """

    def __init__(
        self,
        marker_id: str,
        measurement_type: str,
        channel: int,
        ax,
        canvas,
        color: Optional[str] = None,
    ):
        """Initialize frequency marker.

        Args:
            marker_id: Unique identifier
            measurement_type: 'FREQ' or 'PER'
            channel: Channel number
            ax: Matplotlib axes
            canvas: Qt canvas
            color: Marker color (defaults to cyan)
        """
        super().__init__(marker_id, measurement_type, channel, ax, canvas, color or "#00CED1")

        # Set unit based on measurement type
        self.unit = "Hz" if measurement_type == "FREQ" else "s"

        # Initialize gates (will be set when placed)
        self.gates = {"start_x": 0.0, "end_x": 0.0}

    def render(self) -> None:
        """Draw frequency marker on axes."""
        # Remove old artists
        for artist in self.artists:
            try:
                artist.remove()
            except Exception:
                pass
        self.artists.clear()

        if not self.gates.get("start_x") or not self.gates.get("end_x"):
            return

        start_x = self.gates["start_x"]
        end_x = self.gates["end_x"]

        ylim = self.ax.get_ylim()
        y_range = ylim[1] - ylim[0]

        # Draw vertical gates
        alpha = self.DEFAULT_SELECTED_ALPHA if self.selected else self.DEFAULT_ALPHA

        line1 = self.ax.axvline(
            start_x,
            color=self.color,
            linestyle=self.DEFAULT_LINE_STYLE,
            linewidth=self.DEFAULT_LINE_WIDTH,
            alpha=alpha,
            picker=5,
        )
        self.artists.append(line1)

        line2 = self.ax.axvline(
            end_x,
            color=self.color,
            linestyle=self.DEFAULT_LINE_STYLE,
            linewidth=self.DEFAULT_LINE_WIDTH,
            alpha=alpha,
            picker=5,
        )
        self.artists.append(line2)

        # Draw arc connecting the gates at top
        arc_y = ylim[1] - y_range * 0.05  # 5% from top
        mid_x = (start_x + end_x) / 2

        # Create arc using a simple line
        arc_line = self.ax.plot(
            [start_x, mid_x, end_x],
            [arc_y, arc_y + y_range * 0.02, arc_y],
            color=self.color,
            linestyle="-",
            linewidth=self.DEFAULT_LINE_WIDTH,
            alpha=alpha,
        )[0]
        self.artists.append(arc_line)

        # Draw label at top center
        label_x = mid_x
        label_y = arc_y + y_range * 0.04

        self._draw_label(label_x, label_y)

        self.is_dirty = False

    def update_position(self, **kwargs) -> None:
        """Update marker gate positions.

        Args:
            **kwargs: Can include 'start_x', 'end_x', or 'center_x' with 'width'
        """
        if "start_x" in kwargs:
            self.gates["start_x"] = kwargs["start_x"]
        if "end_x" in kwargs:
            self.gates["end_x"] = kwargs["end_x"]

        # Alternative: specify center and width
        if "center_x" in kwargs and "width" in kwargs:
            center = kwargs["center_x"]
            width = kwargs["width"]
            self.gates["start_x"] = center - width / 2
            self.gates["end_x"] = center + width / 2

        self.is_dirty = True
        self.last_waveform_hash = None  # Force recalculation

    def calculate_measurement(self, waveform: WaveformData) -> Optional[float]:
        """Calculate frequency or period from waveform data.

        Args:
            waveform: Waveform data to measure

        Returns:
            Frequency in Hz or period in seconds, or None if calculation fails
        """
        try:
            # Extract data within gates
            gate_time, gate_voltage = self._extract_gate_data(waveform)

            if len(gate_time) < 10:
                logger.warning("Insufficient data points in gate region")
                return None

            # Find period using zero-crossings or peak detection
            period = self._estimate_period(gate_time, gate_voltage)

            if period is None or period <= 0:
                return None

            if self.measurement_type == "FREQ":
                return 1.0 / period
            else:  # PER
                return period

        except Exception as e:
            logger.error(f"Failed to calculate {self.measurement_type}: {e}")
            return None

    def _estimate_period(self, time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
        """Estimate period from time and voltage data.

        Args:
            time: Time array
            voltage: Voltage array

        Returns:
            Estimated period in seconds, or None if estimation fails
        """
        # Method 1: Zero-crossing detection
        try:
            # Remove DC offset
            voltage_ac = voltage - np.mean(voltage)

            # Find zero crossings with positive slope
            zero_crossings = []
            for i in range(len(voltage_ac) - 1):
                if voltage_ac[i] <= 0 and voltage_ac[i + 1] > 0:
                    # Linear interpolation for more accurate crossing time
                    t_cross = time[i] - voltage_ac[i] * (time[i + 1] - time[i]) / (voltage_ac[i + 1] - voltage_ac[i])
                    zero_crossings.append(t_cross)

            if len(zero_crossings) >= 2:
                # Average period between crossings
                periods = np.diff(zero_crossings)
                return float(np.mean(periods))

        except Exception as e:
            logger.debug(f"Zero-crossing method failed: {e}")

        # Method 2: Peak detection
        try:
            peaks, _ = signal.find_peaks(voltage, distance=len(voltage) // 10)

            if len(peaks) >= 2:
                peak_times = time[peaks]
                periods = np.diff(peak_times)
                return float(np.mean(periods))

        except Exception as e:
            logger.debug(f"Peak detection method failed: {e}")

        # Method 3: Simple estimate from gate width
        # Assume user set gates to span one cycle
        return float(time[-1] - time[0])

    def auto_place(self, waveform: WaveformData, x_hint: Optional[float] = None) -> None:
        """Automatically place marker gates to span one cycle.

        Args:
            waveform: Waveform data to analyze
            x_hint: Optional X position hint (will search near this point)
        """
        try:
            # Estimate period from entire waveform or region near hint
            if x_hint is not None:
                # Find data near hint
                mask = np.abs(waveform.time - x_hint) < (waveform.time[-1] - waveform.time[0]) * 0.2
                search_time = waveform.time[mask]
                search_voltage = waveform.voltage[mask]
            else:
                # Use middle portion of waveform
                mid_idx = len(waveform.time) // 2
                quarter_len = len(waveform.time) // 4
                search_time = waveform.time[mid_idx - quarter_len : mid_idx + quarter_len]
                search_voltage = waveform.voltage[mid_idx - quarter_len : mid_idx + quarter_len]

            # Estimate period
            period = self._estimate_period(search_time, search_voltage)

            if period is not None and period > 0:
                # Center gates on hint or middle
                center = x_hint if x_hint is not None else np.mean(waveform.time)
                self.gates["start_x"] = center - period / 2
                self.gates["end_x"] = center + period / 2

                logger.debug(f"Auto-placed frequency marker with period {period:.6e} s")
                self.is_dirty = True

        except Exception as e:
            logger.error(f"Failed to auto-place frequency marker: {e}")
