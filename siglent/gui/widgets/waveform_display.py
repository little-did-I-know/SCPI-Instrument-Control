"""Waveform display widget using matplotlib."""

import logging
from typing import Any, Dict, List, Optional

import matplotlib
import numpy as np

matplotlib.use("QtAgg")
# Enable interactive mode for matplotlib
import matplotlib.pyplot as plt

plt.ion()

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class WaveformDisplay(QWidget):
    """Widget for displaying oscilloscope waveforms using matplotlib.

    Features:
    - Multiple channel display with different colors
    - Grid toggle
    - Autoscale
    - Zoom and pan (via matplotlib toolbar)
    - Export to image
    """

    # Channel colors (matching typical oscilloscope colors)
    CHANNEL_COLORS = {
        1: "#FFD700",  # Yellow/Gold
        2: "#00CED1",  # Cyan
        3: "#FF1493",  # Deep Pink/Magenta
        4: "#00FF00",  # Green
    }

    def __init__(self, parent=None):
        """Initialize waveform display widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.waveforms: Dict[int, WaveformData] = {}  # Store waveforms by channel
        self.current_waveforms: List[WaveformData] = []  # Store most recently displayed waveforms
        self.show_grid = True

        # Cursor state
        self.cursor_mode = "off"  # 'off', 'vertical', 'horizontal', 'both'
        self.cursor_lines = {"v1": None, "v2": None, "h1": None, "h2": None}
        self.cursor_positions = {"v1": None, "v2": None, "h1": None, "h2": None}
        self.dragging_cursor = None

        # Reference waveform state
        self.reference_data = None  # Reference waveform data
        self.reference_line = None  # Matplotlib line for reference
        self.show_reference = False  # Whether to show reference overlay
        self.show_difference = False  # Whether to show difference instead of overlay

        # Measurement marker state
        self.measurement_markers = []  # List of MeasurementMarker objects
        self.marker_mode = "off"  # 'off', 'add', 'edit'
        self.selected_marker = None  # Currently selected marker
        self.pending_marker_type = None  # Marker type to add in 'add' mode
        self.pending_marker_channel = None  # Channel for pending marker
        self.dragging_marker_handle = None  # (marker, handle_id) during drag

        self._init_ui()
        logger.info("Waveform display widget initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create matplotlib figure and canvas
        self.figure = Figure(figsize=(10, 6), facecolor="#1a1a1a")
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, facecolor="#0a0a0a")

        # Configure axes
        self._configure_axes()

        # Create navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Create control panel
        control_panel = self._create_control_panel()

        # Add to layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(control_panel)

        # Connect mouse events
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.canvas.mpl_connect("key_press_event", self._on_key_press)

    def _configure_axes(self):
        """Configure matplotlib axes appearance."""
        # Set dark theme colors
        self.ax.set_facecolor("#0a0a0a")
        self.ax.tick_params(colors="#888888", which="both")
        self.ax.spines["bottom"].set_color("#444444")
        self.ax.spines["top"].set_color("#444444")
        self.ax.spines["left"].set_color("#444444")
        self.ax.spines["right"].set_color("#444444")

        # Set labels
        self.ax.set_xlabel("Time (s)", color="#cccccc", fontsize=10)
        self.ax.set_ylabel("Voltage (V)", color="#cccccc", fontsize=10)
        self.ax.set_title("Waveform Display", color="#cccccc", fontsize=12)

        # Enable grid
        self.ax.grid(True, alpha=0.3, color="#444444", linestyle="--", linewidth=0.5)

        # Tight layout
        self.figure.tight_layout()

    def _create_control_panel(self) -> QWidget:
        """Create control panel with buttons.

        Returns:
            Control panel widget
        """
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Grid toggle
        self.grid_checkbox = QCheckBox("Grid")
        self.grid_checkbox.setChecked(self.show_grid)
        self.grid_checkbox.stateChanged.connect(self._on_grid_toggle)
        layout.addWidget(self.grid_checkbox)

        # Autoscale button
        autoscale_btn = QPushButton("Autoscale")
        autoscale_btn.clicked.connect(self._on_autoscale)
        layout.addWidget(autoscale_btn)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)

        # Export button
        export_btn = QPushButton("Export Image...")
        export_btn.clicked.connect(self._on_export)
        layout.addWidget(export_btn)

        # Channel info label
        self.info_label = QLabel("No data")
        self.info_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.info_label, stretch=1)

        return panel

    def plot_waveform(self, waveform: WaveformData, clear_others: bool = False):
        """Plot a waveform on the display.

        Args:
            waveform: WaveformData object to plot
            clear_others: If True, clear other channels before plotting
        """
        if clear_others:
            self.waveforms.clear()

        # Store waveform
        self.waveforms[waveform.channel] = waveform

        # Replot all waveforms
        self._replot()

        logger.info(f"Plotted waveform from channel {waveform.channel}")

    def plot_multiple_waveforms(self, waveforms: List[WaveformData], fast_update: bool = False):
        """Plot multiple waveforms.

        Args:
            waveforms: List of WaveformData objects to plot
            fast_update: If True, use fast update for live view (doesn't clear axes)
        """
        logger.info(f"plot_multiple_waveforms called with {len(waveforms)} waveform(s), fast_update={fast_update}")

        self.waveforms.clear()

        for waveform in waveforms:
            logger.debug(f"Adding waveform from channel {waveform.channel}, {len(waveform.voltage)} samples")
            self.waveforms[waveform.channel] = waveform

        # Store current waveforms for saving
        self.current_waveforms = waveforms

        logger.debug("Calling _replot()...")
        if fast_update:
            self._fast_replot()
        else:
            self._replot()

        logger.info(f"Plotted {len(waveforms)} waveforms successfully")

    def update_waveform(self, waveform: WaveformData):
        """Update existing waveform or add new one.

        Args:
            waveform: WaveformData object to update/add
        """
        self.waveforms[waveform.channel] = waveform
        self._replot()

    def clear_channel(self, channel: int):
        """Clear waveform for a specific channel.

        Args:
            channel: Channel number to clear (1-4)
        """
        if channel in self.waveforms:
            del self.waveforms[channel]
            self._replot()
            logger.info(f"Cleared channel {channel}")

    def clear_all(self):
        """Clear all waveforms."""
        self.waveforms.clear()
        self._replot()
        logger.info("Cleared all waveforms")

    def _fast_replot(self):
        """Fast replot for live view - updates data without clearing axes."""
        logger.debug(f"_fast_replot called, have {len(self.waveforms)} waveform(s)")

        if not self.waveforms:
            return

        # Update existing lines or create new ones
        for channel, waveform in sorted(self.waveforms.items()):
            color = self.CHANNEL_COLORS.get(channel, "#FFFFFF")
            time_data, time_unit = self._convert_time_units(waveform.time)

            # Downsample if necessary for display performance
            time_data, voltage_data = self._downsample_for_display(time_data, waveform.voltage)

            if len(voltage_data) < len(waveform.voltage):
                logger.debug(f"Downsampled CH{channel} from {len(waveform.voltage)} to {len(voltage_data)} points for fast display")

            # Find existing line for this channel
            line_found = False
            for line in self.ax.get_lines():
                if line.get_label() == f"CH{channel}":
                    # Update existing line
                    line.set_data(time_data, voltage_data)
                    line_found = True
                    break

            if not line_found:
                # Create new line
                self.ax.plot(
                    time_data,
                    voltage_data,
                    color=color,
                    linewidth=1.0,
                    label=f"CH{channel}",
                    alpha=0.9,
                )

        # Update axis limits
        self.ax.relim()
        self.ax.autoscale_view()

        # Quick canvas update
        self.canvas.draw_idle()  # Use draw_idle for better performance
        logger.debug("Fast replot complete")

    def _replot(self):
        """Replot all stored waveforms."""
        logger.debug(f"_replot called, have {len(self.waveforms)} waveform(s)")

        # Clear axes
        self.ax.clear()

        # Reconfigure axes
        self._configure_axes()

        if not self.waveforms:
            # No data to plot
            logger.debug("No waveforms to plot, showing placeholder text")
            self.ax.text(
                0.5,
                0.5,
                "No waveform data",
                horizontalalignment="center",
                verticalalignment="center",
                transform=self.ax.transAxes,
                color="#888888",
                fontsize=14,
            )
            self.info_label.setText("No data")
        else:
            # Plot each channel
            logger.debug(f"Plotting {len(self.waveforms)} channel(s)")
            for channel, waveform in sorted(self.waveforms.items()):
                color = self.CHANNEL_COLORS.get(channel, "#FFFFFF")
                label = f"CH{channel}"

                # Convert time to appropriate units
                time_data, time_unit = self._convert_time_units(waveform.time)

                # Downsample if necessary for display performance
                time_data, voltage_data = self._downsample_for_display(time_data, waveform.voltage)

                if len(voltage_data) < len(waveform.voltage):
                    logger.info(f"Downsampled CH{channel} from {len(waveform.voltage)} to {len(voltage_data)} points for display")

                logger.debug(
                    f"Plotting CH{channel}: {len(time_data)} points, time range: {time_data[0]:.3e} to {time_data[-1]:.3e} {time_unit}, voltage range: {voltage_data.min():.3f} to {voltage_data.max():.3f} V"
                )

                # Plot waveform
                self.ax.plot(time_data, voltage_data, color=color, linewidth=1.0, label=label, alpha=0.9)

            # Update x-axis label with appropriate time unit
            self.ax.set_xlabel(f"Time ({time_unit})", color="#cccccc", fontsize=10)

            # Add legend
            legend = self.ax.legend(loc="upper right", framealpha=0.8, facecolor="#1a1a1a", edgecolor="#444444")
            for text in legend.get_texts():
                text.set_color("#cccccc")

            # Update info label
            num_channels = len(self.waveforms)
            total_samples = sum(len(w) for w in self.waveforms.values())
            self.info_label.setText(f"{num_channels} channel(s) | {total_samples} total samples")

        # Plot reference waveform overlay if loaded
        self._plot_reference_overlay()

        # Render measurement markers
        for marker in self.measurement_markers:
            if marker.visible:
                marker.render()

        # Apply grid setting
        self.ax.grid(self.show_grid, alpha=0.3, color="#444444", linestyle="--", linewidth=0.5)

        # Redraw canvas efficiently - use draw_idle() to defer rendering
        # This prevents blocking the GUI thread and allows Qt to optimize repaints
        logger.debug("Scheduling canvas redraw...")
        self.canvas.draw_idle()

        logger.debug("Canvas redraw scheduled")

    def _downsample_for_display(self, time, voltage, max_points=500000):
        """Downsample waveform data for display performance.

        Uses min-max decimation to preserve peaks and valleys in the signal.
        This prevents GUI blocking when plotting millions of points.

        Args:
            time: Time array
            voltage: Voltage array
            max_points: Maximum number of points to display (default 500000)

        Returns:
            Tuple of (downsampled_time, downsampled_voltage)
        """
        n_samples = len(voltage)

        # No downsampling needed if already small enough
        if n_samples <= max_points:
            return time, voltage

        # Calculate downsampling factor
        factor = int(np.ceil(n_samples / max_points))
        logger.debug(f"Downsampling with factor {factor} ({n_samples} -> ~{n_samples // factor} points)")

        # Use min-max decimation: for each block, keep both min and max values
        # This preserves signal peaks and valleys
        n_blocks = n_samples // factor
        downsampled_time = np.zeros(n_blocks * 2)
        downsampled_voltage = np.zeros(n_blocks * 2)

        for i in range(n_blocks):
            start_idx = i * factor
            end_idx = min(start_idx + factor, n_samples)
            block_voltage = voltage[start_idx:end_idx]
            block_time = time[start_idx:end_idx]

            # Find min and max in this block
            min_idx = np.argmin(block_voltage)
            max_idx = np.argmax(block_voltage)

            # Store min and max (in time order to avoid artifacts)
            if min_idx < max_idx:
                downsampled_time[i * 2] = block_time[min_idx]
                downsampled_voltage[i * 2] = block_voltage[min_idx]
                downsampled_time[i * 2 + 1] = block_time[max_idx]
                downsampled_voltage[i * 2 + 1] = block_voltage[max_idx]
            else:
                downsampled_time[i * 2] = block_time[max_idx]
                downsampled_voltage[i * 2] = block_voltage[max_idx]
                downsampled_time[i * 2 + 1] = block_time[min_idx]
                downsampled_voltage[i * 2 + 1] = block_voltage[min_idx]

        return downsampled_time, downsampled_voltage

    def _convert_time_units(self, time: np.ndarray) -> tuple:
        """Convert time array to appropriate units.

        Args:
            time: Time array in seconds

        Returns:
            Tuple of (converted_time, unit_string)
        """
        # Determine appropriate time unit
        max_time = np.max(np.abs(time))

        if max_time < 1e-6:  # Less than 1 microsecond
            return time * 1e9, "ns"
        elif max_time < 1e-3:  # Less than 1 millisecond
            return time * 1e6, "µs"
        elif max_time < 1:  # Less than 1 second
            return time * 1e3, "ms"
        else:
            return time, "s"

    def _on_grid_toggle(self, state):
        """Handle grid toggle.

        Args:
            state: Checkbox state
        """
        self.show_grid = bool(state)
        self.ax.grid(self.show_grid, alpha=0.3, color="#444444", linestyle="--", linewidth=0.5)
        self.canvas.draw_idle()
        logger.debug(f"Grid {'enabled' if self.show_grid else 'disabled'}")

    def _on_autoscale(self):
        """Handle autoscale button click."""
        self.ax.autoscale(enable=True, axis="both", tight=False)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()
        logger.debug("Autoscale applied")

    def _on_clear(self):
        """Handle clear button click."""
        self.clear_all()

    def _on_export(self):
        """Handle export button click."""
        if not self.waveforms:
            logger.warning("No waveform to export")
            return

        # Get filename from user
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Waveform Image",
            "waveform.png",
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Image (*.svg)",
        )

        if filename:
            try:
                self.figure.savefig(filename, dpi=150, facecolor=self.figure.get_facecolor())
                logger.info(f"Exported waveform to {filename}")
            except Exception as e:
                logger.error(f"Failed to export waveform: {e}")

    def set_theme(self, dark: bool = True):
        """Set display theme.

        Args:
            dark: True for dark theme, False for light theme
        """
        if dark:
            # Dark theme (default)
            self.figure.set_facecolor("#1a1a1a")
            self.ax.set_facecolor("#0a0a0a")
            text_color = "#cccccc"
            grid_color = "#444444"
            spine_color = "#444444"
        else:
            # Light theme
            self.figure.set_facecolor("#ffffff")
            self.ax.set_facecolor("#f8f8f8")
            text_color = "#000000"
            grid_color = "#cccccc"
            spine_color = "#000000"

        # Update colors
        self.ax.tick_params(colors=text_color, which="both")
        self.ax.spines["bottom"].set_color(spine_color)
        self.ax.spines["top"].set_color(spine_color)
        self.ax.spines["left"].set_color(spine_color)
        self.ax.spines["right"].set_color(spine_color)
        self.ax.set_xlabel("Time", color=text_color)
        self.ax.set_ylabel("Voltage (V)", color=text_color)
        self.ax.set_title("Waveform Display", color=text_color)
        self.ax.grid(self.show_grid, alpha=0.3, color=grid_color)

        self.canvas.draw_idle()
        logger.info(f"Theme set to {'dark' if dark else 'light'}")

    def toggle_grid(self):
        """Toggle grid display (callable from external sources like keyboard shortcuts)."""
        self.show_grid = not self.show_grid
        self.ax.grid(self.show_grid, alpha=0.3, color="#444444", linestyle="--", linewidth=0.5)
        self.canvas.draw_idle()
        logger.info(f"Grid {'enabled' if self.show_grid else 'disabled'}")

    def reset_zoom(self):
        """Reset zoom to default view (callable from external sources)."""
        self.ax.autoscale(enable=True, axis="both", tight=False)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()
        logger.info("Zoom reset")

    def _on_scroll(self, event):
        """Handle mouse wheel scroll for zooming.

        Args:
            event: Matplotlib scroll event
        """
        if event.inaxes != self.ax:
            return

        # Zoom factor
        if event.button == "up":
            scale_factor = 1.1  # Zoom in
        elif event.button == "down":
            scale_factor = 0.9  # Zoom out
        else:
            return

        # Get current axis limits
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Get mouse position in data coordinates
        xdata = event.xdata
        ydata = event.ydata

        if xdata is None or ydata is None:
            return

        # Determine zoom behavior based on modifier keys
        # Ctrl: X-axis only
        # Shift: Y-axis only
        # No modifier: Both axes
        if event.key == "control":
            # Zoom X-axis only
            new_xlim = self._zoom_axis(xlim, xdata, scale_factor)
            self.ax.set_xlim(new_xlim)
        elif event.key == "shift":
            # Zoom Y-axis only
            new_ylim = self._zoom_axis(ylim, ydata, scale_factor)
            self.ax.set_ylim(new_ylim)
        else:
            # Zoom both axes
            new_xlim = self._zoom_axis(xlim, xdata, scale_factor)
            new_ylim = self._zoom_axis(ylim, ydata, scale_factor)
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)

        self.canvas.draw_idle()

    def _zoom_axis(self, limits, center, scale_factor):
        """Calculate new axis limits for zooming.

        Args:
            limits: Current axis limits (min, max)
            center: Center point for zoom in data coordinates
            scale_factor: Zoom factor (>1 for zoom in, <1 for zoom out)

        Returns:
            Tuple of (new_min, new_max)
        """
        min_val, max_val = limits
        range_val = max_val - min_val

        # Calculate new range
        new_range = range_val / scale_factor

        # Calculate offset from center
        center_offset = center - min_val
        center_fraction = center_offset / range_val if range_val != 0 else 0.5

        # Calculate new limits centered on mouse position
        new_min = center - (new_range * center_fraction)
        new_max = new_min + new_range

        return (new_min, new_max)

    def set_cursor_mode(self, mode: str):
        """Set cursor mode.

        Args:
            mode: Cursor mode ('off', 'vertical', 'horizontal', 'both')
        """
        self.cursor_mode = mode.lower()
        logger.info(f"Cursor mode set to: {self.cursor_mode}")

        # Clear existing cursors when changing modes
        if self.cursor_mode == "off":
            self._clear_all_cursors()

    def _clear_all_cursors(self):
        """Clear all cursor lines."""
        for key in self.cursor_lines:
            if self.cursor_lines[key] is not None:
                self.cursor_lines[key].remove()
                self.cursor_lines[key] = None
                self.cursor_positions[key] = None

        self.canvas.draw_idle()
        logger.debug("All cursors cleared")

    def _on_mouse_press(self, event):
        """Handle mouse button press for marker/cursor placement/dragging.

        Implements priority system:
        1. Marker mode (if active)
        2. Cursor mode (if active)
        3. Default matplotlib pan/zoom

        Args:
            event: Matplotlib mouse event
        """
        if event.inaxes != self.ax:
            return

        # Priority 1: Handle marker mode
        if self.marker_mode != "off":
            handled = self._handle_marker_mouse_press(event)
            if handled:
                return

        # Priority 2: Handle cursor mode
        if self.cursor_mode != "off":
            self._handle_cursor_mouse_press(event)
            return

        # Priority 3: Let matplotlib toolbar handle (pan/zoom)

    def _handle_marker_mouse_press(self, event) -> bool:
        """Handle mouse press in marker mode.

        Args:
            event: Matplotlib mouse event

        Returns:
            True if event was handled, False otherwise
        """
        if event.button == 1:  # Left click
            if self.marker_mode == "add":
                # Place new marker at click position
                # This will be implemented by the panel when it creates specific marker types
                logger.debug(f"Marker placement requested at ({event.xdata}, {event.ydata})")
                return True

            elif self.marker_mode == "edit":
                # Check if clicking on existing marker
                marker = self._find_marker_at_point(event.xdata, event.ydata)
                if marker:
                    # Select marker
                    if self.selected_marker and self.selected_marker != marker:
                        self.selected_marker.set_selected(False)

                    marker.set_selected(True)
                    self.selected_marker = marker
                    self.canvas.draw_idle()
                    logger.debug(f"Selected marker {marker.marker_id}")
                    return True

        elif event.button == 3:  # Right click
            # Remove marker near click
            marker = self._find_marker_at_point(event.xdata, event.ydata)
            if marker:
                self.remove_measurement_marker(marker)
                return True

        return False

    def _handle_cursor_mouse_press(self, event):
        """Handle mouse press in cursor mode.

        Args:
            event: Matplotlib mouse event
        """
        if event.button == 1:  # Left click
            # Check if clicking on existing cursor
            cursor = self._find_cursor_near_point(event.xdata, event.ydata)
            if cursor:
                self.dragging_cursor = cursor
            else:
                # Place new cursor
                self._place_cursor(event.xdata, event.ydata)

        elif event.button == 3:  # Right click
            # Remove cursor near click
            cursor = self._find_cursor_near_point(event.xdata, event.ydata)
            if cursor:
                self._remove_cursor(cursor)

    def _on_mouse_release(self, event):
        """Handle mouse button release.

        Args:
            event: Matplotlib mouse event
        """
        self.dragging_cursor = None

    def _on_mouse_move(self, event):
        """Handle mouse motion for cursor dragging.

        Args:
            event: Matplotlib mouse event
        """
        if self.dragging_cursor and event.inaxes == self.ax:
            self._move_cursor(self.dragging_cursor, event.xdata, event.ydata)

    def _on_key_press(self, event):
        """Handle key press events.

        Args:
            event: Matplotlib key event
        """
        if event.key == "escape":
            self._clear_all_cursors()

    def _place_cursor(self, x: float, y: float):
        """Place cursor at specified position.

        Args:
            x: X coordinate (time)
            y: Y coordinate (voltage)
        """
        if self.cursor_mode in ["vertical", "both"]:
            # Place vertical cursor
            if self.cursor_positions["v1"] is None:
                self._create_vertical_cursor("v1", x)
            elif self.cursor_positions["v2"] is None:
                self._create_vertical_cursor("v2", x)

        if self.cursor_mode in ["horizontal", "both"]:
            # Place horizontal cursor
            if self.cursor_positions["h1"] is None:
                self._create_horizontal_cursor("h1", y)
            elif self.cursor_positions["h2"] is None:
                self._create_horizontal_cursor("h2", y)

    def _create_vertical_cursor(self, cursor_id: str, x: float):
        """Create a vertical cursor line.

        Args:
            cursor_id: Cursor identifier ('v1' or 'v2')
            x: X position
        """
        color = "#FFD700" if cursor_id == "v1" else "#00CED1"  # Yellow or Cyan
        line = self.ax.axvline(x, color=color, linestyle="--", linewidth=2, alpha=0.8, picker=5)
        self.cursor_lines[cursor_id] = line
        self.cursor_positions[cursor_id] = x
        self.canvas.draw_idle()
        logger.debug(f"Created vertical cursor {cursor_id} at x={x}")

    def _create_horizontal_cursor(self, cursor_id: str, y: float):
        """Create a horizontal cursor line.

        Args:
            cursor_id: Cursor identifier ('h1' or 'h2')
            y: Y position
        """
        color = "#FFD700" if cursor_id == "h1" else "#00CED1"  # Yellow or Cyan
        line = self.ax.axhline(y, color=color, linestyle="--", linewidth=2, alpha=0.8, picker=5)
        self.cursor_lines[cursor_id] = line
        self.cursor_positions[cursor_id] = y
        self.canvas.draw_idle()
        logger.debug(f"Created horizontal cursor {cursor_id} at y={y}")

    def _move_cursor(self, cursor_id: str, x: float, y: float):
        """Move an existing cursor.

        Args:
            cursor_id: Cursor identifier
            x: New X position
            y: New Y position
        """
        if cursor_id in ["v1", "v2"]:
            # Move vertical cursor
            if self.cursor_lines[cursor_id]:
                self.cursor_lines[cursor_id].set_xdata([x, x])
                self.cursor_positions[cursor_id] = x
                self.canvas.draw_idle()
        elif cursor_id in ["h1", "h2"]:
            # Move horizontal cursor
            if self.cursor_lines[cursor_id]:
                self.cursor_lines[cursor_id].set_ydata([y, y])
                self.cursor_positions[cursor_id] = y
                self.canvas.draw_idle()

    def _remove_cursor(self, cursor_id: str):
        """Remove a cursor.

        Args:
            cursor_id: Cursor identifier
        """
        if self.cursor_lines[cursor_id]:
            self.cursor_lines[cursor_id].remove()
            self.cursor_lines[cursor_id] = None
            self.cursor_positions[cursor_id] = None
            self.canvas.draw_idle()
            logger.debug(f"Removed cursor {cursor_id}")

    def _find_cursor_near_point(self, x: float, y: float, threshold: float = None) -> Optional[str]:
        """Find cursor near a given point.

        Args:
            x: X coordinate
            y: Y coordinate
            threshold: Distance threshold (auto-calculated if None)

        Returns:
            Cursor identifier if found, None otherwise
        """
        if x is None or y is None:
            return None

        # Auto-calculate threshold based on axis ranges
        if threshold is None:
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            x_threshold = (xlim[1] - xlim[0]) * 0.02  # 2% of X range
            y_threshold = (ylim[1] - ylim[0]) * 0.02  # 2% of Y range
        else:
            x_threshold = threshold
            y_threshold = threshold

        # Check vertical cursors
        for cursor_id in ["v1", "v2"]:
            pos = self.cursor_positions[cursor_id]
            if pos is not None and abs(x - pos) < x_threshold:
                return cursor_id

        # Check horizontal cursors
        for cursor_id in ["h1", "h2"]:
            pos = self.cursor_positions[cursor_id]
            if pos is not None and abs(y - pos) < y_threshold:
                return cursor_id

        return None

    def get_cursor_values(self) -> dict:
        """Get current cursor position values.

        Returns:
            Dictionary with cursor positions
        """
        return {
            "x1": self.cursor_positions.get("v1"),
            "y1": self.cursor_positions.get("h1"),
            "x2": self.cursor_positions.get("v2"),
            "y2": self.cursor_positions.get("h2"),
        }

    # Reference waveform methods

    def set_reference(self, reference_data: dict):
        """Set reference waveform for overlay.

        Args:
            reference_data: Reference data dictionary with 'time' and 'voltage' keys
        """
        self.reference_data = reference_data
        self.show_reference = True
        self._replot()
        logger.info("Reference waveform set")

    def clear_reference(self):
        """Clear reference waveform."""
        self.reference_data = None
        self.show_reference = False
        self.show_difference = False
        self._replot()
        logger.info("Reference waveform cleared")

    def toggle_reference_visibility(self, visible: bool):
        """Toggle reference waveform visibility.

        Args:
            visible: Whether reference should be visible
        """
        self.show_reference = visible
        self._replot()

    def toggle_difference_mode(self, enabled: bool):
        """Toggle difference mode (show waveform - reference).

        Args:
            enabled: Whether to show difference
        """
        self.show_difference = enabled
        self._replot()

    def _plot_reference_overlay(self):
        """Plot reference waveform overlay if loaded."""
        if not self.reference_data or not self.show_reference:
            return

        if not self.waveforms:
            # No live waveforms to compare against
            return

        try:
            ref_time = self.reference_data["time"]
            ref_voltage = self.reference_data["voltage"]

            # Convert time to appropriate units (same as live waveforms)
            time_data, time_unit = self._convert_time_units(ref_time)

            if self.show_difference and len(self.waveforms) > 0:
                # Show difference between first waveform and reference
                first_waveform = next(iter(self.waveforms.values()))

                # Interpolate reference to match live waveform time base
                if len(first_waveform.time) != len(ref_time):
                    ref_voltage_interp = np.interp(first_waveform.time, ref_time, ref_voltage)
                    live_time_data, _ = self._convert_time_units(first_waveform.time)
                    difference = first_waveform.voltage - ref_voltage_interp

                    # Plot difference
                    self.ax.plot(
                        live_time_data,
                        difference,
                        color="#FF1493",
                        linewidth=1.5,
                        label="Difference",
                        linestyle="-",
                        alpha=0.8,
                    )
                else:
                    live_time_data, _ = self._convert_time_units(first_waveform.time)
                    difference = first_waveform.voltage - ref_voltage

                    # Plot difference
                    self.ax.plot(
                        live_time_data,
                        difference,
                        color="#FF1493",
                        linewidth=1.5,
                        label="Difference",
                        linestyle="-",
                        alpha=0.8,
                    )

                # Add zero reference line
                self.ax.axhline(y=0, color="#888888", linestyle=":", linewidth=1, alpha=0.5)

            else:
                # Show reference as overlay
                self.ax.plot(
                    time_data,
                    ref_voltage,
                    color="#FFA500",
                    linewidth=1.5,
                    label="Reference",
                    linestyle="--",
                    alpha=0.7,
                )

            # Update legend
            legend = self.ax.legend(loc="upper right", framealpha=0.8, facecolor="#1a1a1a", edgecolor="#444444")
            for text in legend.get_texts():
                text.set_color("#cccccc")

        except Exception as e:
            logger.error(f"Failed to plot reference overlay: {e}")

    def get_reference_data(self):
        """Get current reference data.

        Returns:
            Reference data dictionary or None
        """
        return self.reference_data

    # Measurement marker methods

    def add_measurement_marker(self, marker) -> None:
        """Add a measurement marker to display.

        Args:
            marker: MeasurementMarker object to add
        """
        self.measurement_markers.append(marker)
        marker.render()
        self.canvas.draw_idle()
        logger.info(f"Added measurement marker {marker.marker_id}")

    def remove_measurement_marker(self, marker) -> None:
        """Remove a measurement marker from display.

        Args:
            marker: MeasurementMarker object to remove
        """
        if marker in self.measurement_markers:
            marker.remove()
            self.measurement_markers.remove(marker)

            if self.selected_marker == marker:
                self.selected_marker = None

            self.canvas.draw_idle()
            logger.info(f"Removed measurement marker {marker.marker_id}")

    def clear_all_markers(self) -> None:
        """Clear all measurement markers."""
        for marker in self.measurement_markers[:]:
            marker.remove()

        self.measurement_markers.clear()
        self.selected_marker = None
        self.canvas.draw_idle()
        logger.info("Cleared all measurement markers")

    def set_marker_mode(self, mode: str, marker_type: str = None, channel: int = None) -> None:
        """Set interaction mode for markers.

        Args:
            mode: Marker mode ('off', 'add', 'edit')
            marker_type: Type of marker to add (required if mode='add')
            channel: Channel for marker (required if mode='add')
        """
        self.marker_mode = mode.lower()
        self.pending_marker_type = marker_type
        self.pending_marker_channel = channel

        logger.info(f"Marker mode set to: {self.marker_mode}")

        if mode == "off":
            # Deselect all markers
            for marker in self.measurement_markers:
                marker.set_selected(False)
            self.selected_marker = None
            self.canvas.draw_idle()

    def get_marker_measurements(self) -> Dict:
        """Get all measurement results from markers.

        Returns:
            Dictionary mapping marker IDs to results
        """
        return {
            marker.marker_id: {
                "type": marker.measurement_type,
                "channel": marker.channel,
                "result": marker.result,
                "unit": marker.unit,
                "enabled": marker.enabled,
            }
            for marker in self.measurement_markers
        }

    def update_all_markers(self) -> None:
        """Update all enabled markers with current waveform data."""
        if not self.current_waveforms:
            return

        for marker in self.measurement_markers:
            if marker.enabled:
                # Find waveform for marker's channel
                waveform = next((w for w in self.current_waveforms if w.channel == marker.channel), None)

                if waveform:
                    marker.update_measurement(waveform)

        # Redraw markers with updated values
        self._render_all_markers()

    def _render_all_markers(self) -> None:
        """Render all visible markers."""
        for marker in self.measurement_markers:
            if marker.visible and marker.is_dirty:
                marker.render()

        self.canvas.draw_idle()

    def _find_marker_at_point(self, x: float, y: float) -> Optional:
        """Find marker near a given point.

        Args:
            x: X coordinate in data coordinates
            y: Y coordinate in data coordinates

        Returns:
            Marker object if found, None otherwise
        """
        if x is None or y is None:
            return None

        # Check all markers in reverse order (top to bottom)
        for marker in reversed(self.measurement_markers):
            if marker.visible and marker.contains_point(x, y):
                return marker

        return None
