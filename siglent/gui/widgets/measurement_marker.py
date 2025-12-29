"""Base classes for visual measurement markers on waveform display.

This module provides the abstract base class and common functionality for
all measurement markers. Markers are visual overlays on waveforms that
allow users to measure signal properties interactively.

Architecture:
    MeasurementMarker is an abstract base class using the ABC pattern.
    Concrete implementations (FrequencyMarker, VoltageMarker, TimingMarker)
    inherit from it and implement measurement-specific rendering and calculations.

Key Concepts:
    - Gates: Visual regions that define where measurements are taken
    - Handles: Draggable elements for adjusting gate positions
    - Labels: Text displays showing measurement results
    - State: enabled, visible, selected flags control marker behavior

Visual Elements:
    Each marker renders multiple matplotlib artists:
    - Line2D objects for gates and boundaries
    - Text objects for labels and values
    - Patches (rectangles, boxes) for highlighting
    - Handles for interaction points

Subclass Requirements:
    Concrete markers must implement:
    - render(): Draw the marker on the axes
    - update_position(): Handle position changes
    - calculate_measurement(): Compute measurement from waveform data

Example:
    >>> class MyMarker(MeasurementMarker):
    ...     def render(self):
    ...         # Draw marker visualization
    ...         pass
    ...     def calculate_measurement(self, waveform):
    ...         # Compute measurement
    ...         return value
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING
import logging

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.text import Text

from siglent.waveform import WaveformData

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

logger = logging.getLogger(__name__)


class MeasurementMarker(ABC):
    """Abstract base class for measurement markers.

    Provides common functionality for visual markers on waveform display,
    including rendering, positioning, and interaction.

    Attributes:
        marker_id: Unique identifier for this marker
        measurement_type: Type of measurement (FREQ, PKPK, RISE, etc.)
        channel: Channel number (1-4)
        ax: Matplotlib axes to draw on
        canvas: Qt canvas for redrawing
        enabled: Whether marker is currently active
        visible: Whether marker is currently visible
        selected: Whether marker is currently selected
        color: Marker color
        result: Cached measurement result
        unit: Measurement unit
    """

    # Default visual styling
    DEFAULT_LINE_WIDTH = 2
    DEFAULT_LINE_STYLE = "--"
    DEFAULT_ALPHA = 0.8
    DEFAULT_SELECTED_ALPHA = 1.0
    HANDLE_SIZE = 8  # pixels
    LABEL_FONTSIZE = 9
    LABEL_PADDING = 4

    def __init__(self, marker_id: str, measurement_type: str, channel: int, ax: "Axes", canvas: "FigureCanvasQTAgg", color: Optional[str] = None):
        """Initialize measurement marker.

        Args:
            marker_id: Unique identifier
            measurement_type: Type of measurement
            channel: Channel number
            ax: Matplotlib axes
            canvas: Qt canvas
            color: Marker color (None for default)
        """
        self.marker_id = marker_id
        self.measurement_type = measurement_type
        self.channel = channel
        self.ax = ax
        self.canvas = canvas

        self.enabled = True
        self.visible = True
        self.selected = False

        self.color = color or self._get_default_color()
        self.result: Optional[float] = None
        self.unit: Optional[str] = None

        # Matplotlib artists (lines, patches, text)
        self.artists: List[Any] = []
        self.label_artist: Optional[Text] = None

        # Gate positions (in data coordinates)
        self.gates: Dict[str, float] = {}

        # For change detection
        self.is_dirty = True
        self.last_waveform_hash: Optional[int] = None

        logger.debug(f"Created {measurement_type} marker {marker_id} for CH{channel}")

    @abstractmethod
    def render(self) -> None:
        """Draw marker on axes.

        Must be implemented by subclasses to draw specific marker visualization.
        """
        pass

    @abstractmethod
    def update_position(self, **kwargs) -> None:
        """Update marker position/gates.

        Args:
            **kwargs: Position parameters (varies by marker type)

        Must be implemented by subclasses to handle gate position updates.
        """
        pass

    @abstractmethod
    def calculate_measurement(self, waveform: WaveformData) -> Optional[float]:
        """Calculate measurement from waveform data.

        Args:
            waveform: Waveform data to measure

        Returns:
            Measurement value or None if calculation fails

        Must be implemented by subclasses to perform specific calculation.
        """
        pass

    def contains_point(self, x: float, y: float, threshold_data: Optional[float] = None) -> bool:
        """Check if point is near marker for selection.

        Args:
            x: X coordinate in data coordinates
            y: Y coordinate in data coordinates
            threshold_data: Distance threshold in data coordinates (auto-calculated if None)

        Returns:
            True if point is near marker
        """
        if threshold_data is None:
            xlim = self.ax.get_xlim()
            threshold_data = (xlim[1] - xlim[0]) * 0.02  # 2% of X range

        # Check proximity to any gate position
        for gate_pos in self.gates.values():
            if isinstance(gate_pos, (int, float)):
                if abs(x - gate_pos) < threshold_data:
                    return True

        return False

    def remove(self) -> None:
        """Remove marker from display."""
        for artist in self.artists:
            try:
                artist.remove()
            except Exception as e:
                logger.warning(f"Failed to remove artist: {e}")

        if self.label_artist:
            try:
                self.label_artist.remove()
            except Exception as e:
                logger.warning(f"Failed to remove label: {e}")

        self.artists.clear()
        self.label_artist = None

        logger.debug(f"Removed marker {self.marker_id}")

    def set_visible(self, visible: bool) -> None:
        """Set marker visibility.

        Args:
            visible: Whether marker should be visible
        """
        self.visible = visible

        for artist in self.artists:
            artist.set_visible(visible)

        if self.label_artist:
            self.label_artist.set_visible(visible)

        self.is_dirty = True

    def set_selected(self, selected: bool) -> None:
        """Set marker selection state.

        Args:
            selected: Whether marker is selected
        """
        self.selected = selected
        self.is_dirty = True

        # Update alpha based on selection
        alpha = self.DEFAULT_SELECTED_ALPHA if selected else self.DEFAULT_ALPHA

        for artist in self.artists:
            if hasattr(artist, "set_alpha"):
                artist.set_alpha(alpha)

        # Add white outline if selected
        if selected:
            for artist in self.artists:
                if isinstance(artist, Line2D):
                    artist.set_markeredgecolor("white")
                    artist.set_markeredgewidth(2)

    def update_measurement(self, waveform: WaveformData) -> None:
        """Update measurement from waveform data.

        Args:
            waveform: Waveform data to measure
        """
        if not self.enabled or waveform.channel != self.channel:
            return

        # Check if recalculation needed
        waveform_hash = hash((id(waveform), tuple(sorted(self.gates.items()))))

        if waveform_hash == self.last_waveform_hash:
            return  # Use cached result

        # Recalculate
        try:
            self.result = self.calculate_measurement(waveform)
            self.last_waveform_hash = waveform_hash
            self.is_dirty = True

            logger.debug(f"Marker {self.marker_id} measurement updated: {self.result} {self.unit}")

        except Exception as e:
            logger.error(f"Failed to calculate measurement for {self.marker_id}: {e}")
            self.result = None

    def _create_label_text(self) -> str:
        """Create label text for marker.

        Returns:
            Formatted label string
        """
        if self.result is None:
            value_str = "---"
        else:
            value_str = self._format_value(self.result, self.unit)

        return f"{self.marker_id}: {self.measurement_type} = {value_str}"

    def _format_value(self, value: float, unit: Optional[str] = None) -> str:
        """Format measurement value with appropriate prefix.

        Args:
            value: Value to format
            unit: Unit string (V, s, Hz, etc.)

        Returns:
            Formatted string with SI prefix
        """
        if value is None:
            return "---"

        abs_value = abs(value)

        # Determine appropriate SI prefix
        if abs_value == 0:
            prefix = ""
            scale = 1
        elif abs_value >= 1e9:
            prefix = "G"
            scale = 1e9
        elif abs_value >= 1e6:
            prefix = "M"
            scale = 1e6
        elif abs_value >= 1e3:
            prefix = "k"
            scale = 1e3
        elif abs_value >= 1:
            prefix = ""
            scale = 1
        elif abs_value >= 1e-3:
            prefix = "m"
            scale = 1e-3
        elif abs_value >= 1e-6:
            prefix = "µ"
            scale = 1e-6
        elif abs_value >= 1e-9:
            prefix = "n"
            scale = 1e-9
        else:
            prefix = "p"
            scale = 1e-12

        scaled_value = value / scale

        # Format with appropriate precision
        if abs(scaled_value) >= 100:
            formatted = f"{scaled_value:.1f}"
        elif abs(scaled_value) >= 10:
            formatted = f"{scaled_value:.2f}"
        else:
            formatted = f"{scaled_value:.3f}"

        return f"{formatted} {prefix}{unit}" if unit else f"{formatted} {prefix}"

    def _draw_label(self, x: float, y: float) -> None:
        """Draw measurement label at specified position.

        Args:
            x: X position in data coordinates
            y: Y position in data coordinates
        """
        # Remove old label if exists
        if self.label_artist:
            try:
                self.label_artist.remove()
            except Exception:
                pass

        # Create label text
        label_text = self._create_label_text()

        # Create text with background box
        bbox_props = dict(boxstyle=f"round,pad={self.LABEL_PADDING}", facecolor="#000000DD", edgecolor=self.color if self.selected else "#444444", linewidth=2 if self.selected else 1)

        self.label_artist = self.ax.text(x, y, label_text, fontsize=self.LABEL_FONTSIZE, color=self.color, bbox=bbox_props, verticalalignment="top", horizontalalignment="left", zorder=100)  # Draw on top

    def _get_default_color(self) -> str:
        """Get default color based on measurement type.

        Returns:
            Color string
        """
        # Color scheme matching oscilloscope conventions
        color_map = {
            "FREQ": "#00CED1",  # Cyan
            "PER": "#00CED1",  # Cyan
            "PKPK": "#FFD700",  # Yellow/Gold
            "AMPL": "#FFD700",  # Yellow/Gold
            "MAX": "#FFD700",  # Yellow/Gold
            "MIN": "#FFD700",  # Yellow/Gold
            "RMS": "#FFD700",  # Yellow/Gold
            "MEAN": "#FFD700",  # Yellow/Gold
            "RISE": "#FF1493",  # Magenta
            "FALL": "#FF1493",  # Magenta
            "WID": "#00FF00",  # Green
            "NWID": "#00FF00",  # Green
            "DUTY": "#00FF00",  # Green
        }

        return color_map.get(self.measurement_type, "#FFFFFF")  # White default

    def get_config(self) -> Dict[str, Any]:
        """Get marker configuration for saving.

        Returns:
            Configuration dictionary
        """
        return {"id": self.marker_id, "type": self.measurement_type, "channel": self.channel, "enabled": self.enabled, "gates": self.gates.copy(), "color": self.color, "result": self.result, "unit": self.unit}

    def set_config(self, config: Dict[str, Any]) -> None:
        """Load marker configuration.

        Args:
            config: Configuration dictionary
        """
        self.enabled = config.get("enabled", True)
        self.gates = config.get("gates", {}).copy()
        self.color = config.get("color", self._get_default_color())
        self.result = config.get("result")
        self.unit = config.get("unit")
        self.is_dirty = True

    def _extract_gate_data(self, waveform: WaveformData) -> Tuple[np.ndarray, np.ndarray]:
        """Extract waveform data within gate region.

        Args:
            waveform: Full waveform data

        Returns:
            Tuple of (time_array, voltage_array) within gates

        Raises:
            ValueError: If gates are not properly defined
        """
        if "start_x" not in self.gates or "end_x" not in self.gates:
            raise ValueError("Gates not properly defined (missing start_x or end_x)")

        start_x = self.gates["start_x"]
        end_x = self.gates["end_x"]

        # Create mask for data within gates
        mask = (waveform.time >= start_x) & (waveform.time <= end_x)

        if not np.any(mask):
            raise ValueError("No data points within gate region")

        return waveform.time[mask], waveform.voltage[mask]
