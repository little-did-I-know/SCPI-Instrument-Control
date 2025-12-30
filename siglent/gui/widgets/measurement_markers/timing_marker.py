"""Timing measurement markers (Rise Time, Fall Time, Pulse Width, Duty Cycle)."""

import logging
from typing import Optional, Tuple

import numpy as np

from siglent.gui.widgets.measurement_marker import MeasurementMarker
from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class TimingMarker(MeasurementMarker):
    """Marker for timing measurements.

    Supports: RISE, FALL, WID (positive width), NWID (negative width), DUTY (duty cycle)

    Visual representation:
    - For RISE/FALL: Vertical gate with horizontal threshold lines (10% and 90%)
    - For WID/NWID: Two vertical gates with shaded region between
    - For DUTY: Two gates showing positive pulse width and total period
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
        """Initialize timing marker.

        Args:
            marker_id: Unique identifier
            measurement_type: RISE, FALL, WID, NWID, DUTY
            channel: Channel number
            ax: Matplotlib axes
            canvas: Qt canvas
            color: Marker color (magenta for rise/fall, green for width/duty)
        """
        # Determine default color based on type
        if color is None:
            if measurement_type in ["RISE", "FALL"]:
                color = "#FF1493"  # Magenta
            else:  # WID, NWID, DUTY
                color = "#00FF00"  # Green

        super().__init__(marker_id, measurement_type, channel, ax, canvas, color)

        self.unit = "s" if measurement_type != "DUTY" else "%"

        # Initialize gates
        if measurement_type in ["RISE", "FALL"]:
            self.gates = {"start_x": 0.0, "end_x": 0.0}
        else:  # WID, NWID, DUTY
            self.gates = {"start_x": 0.0, "end_x": 0.0}

        # Store threshold levels for rise/fall
        self.threshold_10: Optional[float] = None
        self.threshold_90: Optional[float] = None

    def render(self) -> None:
        """Draw timing marker on axes."""
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

        alpha = self.DEFAULT_SELECTED_ALPHA if self.selected else self.DEFAULT_ALPHA

        # Draw vertical gates
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

        # Type-specific rendering
        if self.measurement_type in ["RISE", "FALL"] and self.threshold_10 is not None and self.threshold_90 is not None:
            # Draw horizontal threshold lines
            xlim = self.ax.get_xlim()
            x_start_norm = (start_x - xlim[0]) / (xlim[1] - xlim[0])
            x_end_norm = (end_x - xlim[0]) / (xlim[1] - xlim[0])

            thresh_10_line = self.ax.axhline(
                self.threshold_10,
                xmin=x_start_norm,
                xmax=x_end_norm,
                color=self.color,
                linestyle=":",
                linewidth=1.5,
                alpha=alpha * 0.7,
            )
            self.artists.append(thresh_10_line)

            thresh_90_line = self.ax.axhline(
                self.threshold_90,
                xmin=x_start_norm,
                xmax=x_end_norm,
                color=self.color,
                linestyle=":",
                linewidth=1.5,
                alpha=alpha * 0.7,
            )
            self.artists.append(thresh_90_line)

        elif self.measurement_type in ["WID", "NWID", "DUTY"]:
            # Draw shaded region between gates
            ylim = self.ax.get_ylim()
            fill = self.ax.fill_between([start_x, end_x], ylim[0], ylim[1], color=self.color, alpha=0.15)
            self.artists.append(fill)

        # Draw label
        mid_x = (start_x + end_x) / 2
        ylim = self.ax.get_ylim()
        y_range = ylim[1] - ylim[0]
        label_y = ylim[1] - y_range * 0.05

        self._draw_label(mid_x, label_y)

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

        if "center_x" in kwargs and "width" in kwargs:
            center = kwargs["center_x"]
            width = kwargs["width"]
            self.gates["start_x"] = center - width / 2
            self.gates["end_x"] = center + width / 2

        self.is_dirty = True
        self.last_waveform_hash = None

    def calculate_measurement(self, waveform: WaveformData) -> Optional[float]:
        """Calculate timing measurement from waveform data.

        Args:
            waveform: Waveform data to measure

        Returns:
            Timing measurement result, or None if calculation fails
        """
        try:
            gate_time, gate_voltage = self._extract_gate_data(waveform)

            if len(gate_time) < 5:
                return None

            if self.measurement_type == "RISE":
                return self._calculate_rise_time(gate_time, gate_voltage)

            elif self.measurement_type == "FALL":
                return self._calculate_fall_time(gate_time, gate_voltage)

            elif self.measurement_type == "WID":
                return self._calculate_positive_width(gate_time, gate_voltage)

            elif self.measurement_type == "NWID":
                return self._calculate_negative_width(gate_time, gate_voltage)

            elif self.measurement_type == "DUTY":
                return self._calculate_duty_cycle(gate_time, gate_voltage)

            else:
                logger.warning(f"Unknown timing measurement type: {self.measurement_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to calculate {self.measurement_type}: {e}")
            return None

    def _calculate_rise_time(self, time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
        """Calculate rise time (10% to 90%).

        Args:
            time: Time array
            voltage: Voltage array

        Returns:
            Rise time in seconds
        """
        # Calculate amplitude and thresholds
        v_min = np.min(voltage)
        v_max = np.max(voltage)
        v_range = v_max - v_min

        if v_range == 0:
            return None

        self.threshold_10 = v_min + 0.1 * v_range
        self.threshold_90 = v_min + 0.9 * v_range

        # Find crossing times
        t_10 = self._find_threshold_crossing(time, voltage, self.threshold_10, rising=True)
        t_90 = self._find_threshold_crossing(time, voltage, self.threshold_90, rising=True)

        if t_10 is None or t_90 is None:
            return None

        return float(t_90 - t_10)

    def _calculate_fall_time(self, time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
        """Calculate fall time (90% to 10%).

        Args:
            time: Time array
            voltage: Voltage array

        Returns:
            Fall time in seconds
        """
        v_min = np.min(voltage)
        v_max = np.max(voltage)
        v_range = v_max - v_min

        if v_range == 0:
            return None

        self.threshold_90 = v_min + 0.9 * v_range
        self.threshold_10 = v_min + 0.1 * v_range

        # Find crossing times
        t_90 = self._find_threshold_crossing(time, voltage, self.threshold_90, rising=False)
        t_10 = self._find_threshold_crossing(time, voltage, self.threshold_10, rising=False)

        if t_90 is None or t_10 is None:
            return None

        return float(t_10 - t_90)

    def _calculate_positive_width(self, time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
        """Calculate positive pulse width.

        Args:
            time: Time array
            voltage: Voltage array

        Returns:
            Pulse width in seconds
        """
        # Find 50% threshold
        v_min = np.min(voltage)
        v_max = np.max(voltage)
        threshold = (v_min + v_max) / 2

        # Find rising and falling edges
        t_rising = self._find_threshold_crossing(time, voltage, threshold, rising=True)
        t_falling = self._find_threshold_crossing(time, voltage, threshold, rising=False)

        if t_rising is None or t_falling is None or t_falling <= t_rising:
            return None

        return float(t_falling - t_rising)

    def _calculate_negative_width(self, time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
        """Calculate negative pulse width.

        Args:
            time: Time array
            voltage: Voltage array

        Returns:
            Pulse width in seconds
        """
        # Find 50% threshold
        v_min = np.min(voltage)
        v_max = np.max(voltage)
        threshold = (v_min + v_max) / 2

        # Find falling and rising edges
        t_falling = self._find_threshold_crossing(time, voltage, threshold, rising=False)
        t_rising_next = self._find_threshold_crossing(
            time[time > t_falling] if t_falling else time,
            voltage[time > t_falling] if t_falling else voltage,
            threshold,
            rising=True,
        )

        if t_falling is None or t_rising_next is None or t_rising_next <= t_falling:
            return None

        return float(t_rising_next - t_falling)

    def _calculate_duty_cycle(self, time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
        """Calculate duty cycle.

        Args:
            time: Time array
            voltage: Voltage array

        Returns:
            Duty cycle as percentage (0-100)
        """
        # Calculate positive width and period
        positive_width = self._calculate_positive_width(time, voltage)

        if positive_width is None:
            return None

        # Estimate period
        total_time = time[-1] - time[0]

        if total_time <= 0:
            return None

        duty_cycle = (positive_width / total_time) * 100

        return float(duty_cycle)

    def _find_threshold_crossing(self, time: np.ndarray, voltage: np.ndarray, threshold: float, rising: bool = True) -> Optional[float]:
        """Find time when waveform crosses threshold.

        Args:
            time: Time array
            voltage: Voltage array
            threshold: Threshold voltage
            rising: True for rising edge, False for falling edge

        Returns:
            Time of crossing, or None if not found
        """
        for i in range(len(voltage) - 1):
            if rising:
                if voltage[i] <= threshold < voltage[i + 1]:
                    # Linear interpolation
                    frac = (threshold - voltage[i]) / (voltage[i + 1] - voltage[i])
                    return time[i] + frac * (time[i + 1] - time[i])
            else:  # falling
                if voltage[i] >= threshold > voltage[i + 1]:
                    # Linear interpolation
                    frac = (voltage[i] - threshold) / (voltage[i] - voltage[i + 1])
                    return time[i] + frac * (time[i + 1] - time[i])

        return None

    def auto_place(self, waveform: WaveformData, x_hint: Optional[float] = None) -> None:
        """Automatically place marker gates.

        Args:
            waveform: Waveform data to analyze
            x_hint: Optional X position hint
        """
        try:
            if self.measurement_type in ["RISE", "FALL"]:
                # Find edge near hint or in middle
                if x_hint is not None:
                    center = x_hint
                else:
                    center = np.mean(waveform.time)

                # Set gates around edge with margin
                time_span = waveform.time[-1] - waveform.time[0]
                margin = time_span * 0.05  # 5% margin

                self.gates["start_x"] = center - margin
                self.gates["end_x"] = center + margin

            else:  # WID, NWID, DUTY
                # Use a reasonable portion of waveform
                time_span = waveform.time[-1] - waveform.time[0]

                if x_hint is not None:
                    center = x_hint
                else:
                    center = np.mean(waveform.time)

                width = time_span * 0.3  # 30% of visible timespan

                self.gates["start_x"] = center - width / 2
                self.gates["end_x"] = center + width / 2

            logger.debug(f"Auto-placed timing marker")
            self.is_dirty = True

        except Exception as e:
            logger.error(f"Failed to auto-place timing marker: {e}")
