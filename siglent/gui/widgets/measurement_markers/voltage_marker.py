"""Voltage measurement markers (Vpp, Amplitude, Max, Min, RMS, Mean)."""

import logging
from typing import Optional

import numpy as np

from siglent.gui.widgets.measurement_marker import MeasurementMarker
from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class VoltageMarker(MeasurementMarker):
    """Marker for voltage measurements.

    Supports: PKPK, AMPL, MAX, MIN, RMS, MEAN, CRMS, CMEAN, TOP, BASE

    Visual representation:
    - Vertical gate (two vertical lines) defining measurement region
    - Horizontal line(s) at measured value(s)
    - Vertical bracket showing span (for PKPK/AMPL)
    - Label with voltage value
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
        """Initialize voltage marker.

        Args:
            marker_id: Unique identifier
            measurement_type: PKPK, AMPL, MAX, MIN, RMS, MEAN, etc.
            channel: Channel number
            ax: Matplotlib axes
            canvas: Qt canvas
            color: Marker color (defaults to yellow/gold)
        """
        super().__init__(marker_id, measurement_type, channel, ax, canvas, color or "#FFD700")

        self.unit = "V"

        # Initialize gates
        self.gates = {"start_x": 0.0, "end_x": 0.0}

        # Store intermediate values for display
        self.max_value: Optional[float] = None
        self.min_value: Optional[float] = None

    def render(self) -> None:
        """Draw voltage marker on axes."""
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
        ylim = self.ax.get_ylim()

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

        # Draw horizontal lines and brackets based on measurement type
        if self.measurement_type in ["PKPK", "AMPL"] and self.max_value is not None and self.min_value is not None:
            # Draw lines at max and min
            max_line = self.ax.axhline(
                self.max_value,
                xmin=(start_x - self.ax.get_xlim()[0]) / (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]),
                xmax=(end_x - self.ax.get_xlim()[0]) / (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]),
                color=self.color,
                linestyle="-",
                linewidth=1.5,
                alpha=alpha,
            )
            self.artists.append(max_line)

            min_line = self.ax.axhline(
                self.min_value,
                xmin=(start_x - self.ax.get_xlim()[0]) / (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]),
                xmax=(end_x - self.ax.get_xlim()[0]) / (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]),
                color=self.color,
                linestyle="-",
                linewidth=1.5,
                alpha=alpha,
            )
            self.artists.append(min_line)

            # Draw vertical bracket on left side
            bracket_x = start_x - (end_x - start_x) * 0.05
            bracket = self.ax.plot(
                [bracket_x, bracket_x],
                [self.min_value, self.max_value],
                color=self.color,
                linestyle="-",
                linewidth=2,
                alpha=alpha,
                marker="|",
                markersize=8,
            )[0]
            self.artists.append(bracket)

        elif self.result is not None:
            # Single horizontal line for other voltage measurements
            h_line = self.ax.axhline(
                self.result,
                xmin=(start_x - self.ax.get_xlim()[0]) / (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]),
                xmax=(end_x - self.ax.get_xlim()[0]) / (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]),
                color=self.color,
                linestyle="-",
                linewidth=2,
                alpha=alpha,
            )
            self.artists.append(h_line)

        # Draw label
        mid_x = (start_x + end_x) / 2
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
        """Calculate voltage measurement from waveform data.

        Args:
            waveform: Waveform data to measure

        Returns:
            Voltage measurement result, or None if calculation fails
        """
        try:
            # Extract data within gates
            _, gate_voltage = self._extract_gate_data(waveform)

            if len(gate_voltage) == 0:
                return None

            # Calculate based on measurement type
            if self.measurement_type == "PKPK":
                self.max_value = float(np.max(gate_voltage))
                self.min_value = float(np.min(gate_voltage))
                return self.max_value - self.min_value

            elif self.measurement_type == "AMPL":
                self.max_value = float(np.max(gate_voltage))
                self.min_value = float(np.min(gate_voltage))
                return (self.max_value - self.min_value) / 2

            elif self.measurement_type == "MAX":
                return float(np.max(gate_voltage))

            elif self.measurement_type == "MIN":
                return float(np.min(gate_voltage))

            elif self.measurement_type == "TOP":
                # Top value (typically 90% percentile)
                return float(np.percentile(gate_voltage, 90))

            elif self.measurement_type == "BASE":
                # Base value (typically 10% percentile)
                return float(np.percentile(gate_voltage, 10))

            elif self.measurement_type == "MEAN":
                return float(np.mean(gate_voltage))

            elif self.measurement_type == "CMEAN":
                # Cycle mean - same as mean for our purposes
                return float(np.mean(gate_voltage))

            elif self.measurement_type == "RMS":
                return float(np.sqrt(np.mean(gate_voltage**2)))

            elif self.measurement_type == "CRMS":
                # Cycle RMS
                # Remove DC component for true AC RMS
                ac_voltage = gate_voltage - np.mean(gate_voltage)
                return float(np.sqrt(np.mean(ac_voltage**2)))

            else:
                logger.warning(f"Unknown voltage measurement type: {self.measurement_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to calculate {self.measurement_type}: {e}")
            return None

    def auto_place(self, waveform: WaveformData, x_hint: Optional[float] = None) -> None:
        """Automatically place marker gates.

        Args:
            waveform: Waveform data to analyze
            x_hint: Optional X position hint
        """
        try:
            # Use a reasonable portion of the waveform
            time_span = waveform.time[-1] - waveform.time[0]

            if x_hint is not None:
                # Center on hint
                center = x_hint
            else:
                # Center on middle of waveform
                center = np.mean(waveform.time)

            # Default gate width: 20% of visible timespan
            width = time_span * 0.2

            self.gates["start_x"] = center - width / 2
            self.gates["end_x"] = center + width / 2

            logger.debug(f"Auto-placed voltage marker at center={center:.6e}, width={width:.6e}")
            self.is_dirty = True

        except Exception as e:
            logger.error(f"Failed to auto-place voltage marker: {e}")
