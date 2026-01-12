"""Real-time data visualization widget for DAQ/Data Logger.

This module provides a PyQtGraph-based real-time chart and data table
for displaying DAQ readings.

Features:
    - Multi-channel time series chart with auto-scrolling
    - Data table with timestamps and channel values
    - Rolling buffer with configurable size
    - CSV export functionality
    - Pause/resume display updates
"""

import csv
import logging
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Try to import PyQtGraph for high-performance plotting
try:
    import pyqtgraph as pg

    PYQTGRAPH_AVAILABLE = True
    logger.info("PyQtGraph available for DAQ data view")
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    logger.warning("PyQtGraph not available, DAQ chart will be disabled")

# Channel colors (matching oscilloscope style)
CHANNEL_COLORS = {
    101: "#FFD700",  # Gold
    102: "#00CED1",  # Cyan
    103: "#FF1493",  # Hot Pink
    104: "#00FF00",  # Green
    105: "#FF6347",  # Tomato
    106: "#9370DB",  # Medium Purple
    107: "#20B2AA",  # Light Sea Green
    108: "#FF8C00",  # Dark Orange
}


def get_channel_color(channel: int) -> str:
    """Get color for a channel number."""
    if channel in CHANNEL_COLORS:
        return CHANNEL_COLORS[channel]
    # Generate a color based on channel number
    colors = list(CHANNEL_COLORS.values())
    return colors[channel % len(colors)]


class DAQDataView(QWidget):
    """Real-time data visualization and table for DAQ readings.

    Signals:
        data_cleared: Emitted when data is cleared
        export_requested: Emitted when export is requested
    """

    data_cleared = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the data view widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Data storage
        self.data_buffer: List[Dict] = []  # List of {timestamp, readings}
        self.max_points = 1000  # Maximum points to display/store
        self.channels: List[int] = []  # Active channels
        self.start_time: Optional[datetime] = None
        self.paused = False

        # PyQtGraph components
        self.plot_widget: Optional[pg.PlotWidget] = None
        self.traces: Dict[int, pg.PlotDataItem] = {}  # channel -> trace

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for chart and table
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Chart area
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setBackground("#1e1e1e")
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setLabel("left", "Value")
            self.plot_widget.setLabel("bottom", "Time (s)")
            self.plot_widget.addLegend()
            splitter.addWidget(self.plot_widget)
        else:
            # Placeholder if PyQtGraph not available
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            from PyQt6.QtWidgets import QLabel

            label = QLabel("PyQtGraph not installed. Install with: pip install pyqtgraph")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder_layout.addWidget(label)
            splitter.addWidget(placeholder)

        # Data table
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #2d2d2d;
                alternate-background-color: #353535;
                color: #ffffff;
                gridline-color: #404040;
            }
            QHeaderView::section {
                background-color: #404040;
                color: #ffffff;
                padding: 4px;
                border: 1px solid #505050;
            }
        """
        )
        splitter.addWidget(self.data_table)

        # Set splitter sizes (70% chart, 30% table)
        splitter.setSizes([700, 300])
        layout.addWidget(splitter)

        # Button bar
        button_bar = QHBoxLayout()

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        button_bar.addWidget(self.pause_btn)

        self.clear_btn = QPushButton("Clear Data")
        self.clear_btn.clicked.connect(self.clear_data)
        button_bar.addWidget(self.clear_btn)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self._on_export_clicked)
        button_bar.addWidget(self.export_btn)

        button_bar.addStretch()

        # Data info label
        from PyQt6.QtWidgets import QLabel

        self.info_label = QLabel("No data")
        button_bar.addWidget(self.info_label)

        layout.addLayout(button_bar)

    def set_channels(self, channels: List[int]):
        """Set the active channels for display.

        Args:
            channels: List of channel numbers
        """
        self.channels = channels

        # Update table columns
        headers = ["Time (s)"] + [f"CH{ch}" for ch in channels]
        self.data_table.setColumnCount(len(headers))
        self.data_table.setHorizontalHeaderLabels(headers)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Create traces for each channel
        if self.plot_widget:
            # Clear existing traces
            for trace in self.traces.values():
                self.plot_widget.removeItem(trace)
            self.traces.clear()

            # Create new traces
            for ch in channels:
                color = get_channel_color(ch)
                pen = pg.mkPen(color=color, width=2)
                trace = self.plot_widget.plot([], [], pen=pen, name=f"CH{ch}")
                self.traces[ch] = trace

    def update_readings(self, readings: List):
        """Update the display with new readings.

        Args:
            readings: List of Reading objects from DataLogger
        """
        if self.paused:
            return

        if not readings:
            return

        # Initialize start time on first reading
        if self.start_time is None:
            self.start_time = datetime.now()

        # Calculate relative timestamp
        elapsed = (datetime.now() - self.start_time).total_seconds()

        # Store readings
        reading_dict = {
            "timestamp": elapsed,
            "readings": {r.channel: r.value for r in readings if r.channel},
        }
        self.data_buffer.append(reading_dict)

        # Trim buffer if needed
        if len(self.data_buffer) > self.max_points:
            self.data_buffer = self.data_buffer[-self.max_points :]

        # Update chart
        self._update_chart()

        # Update table
        self._update_table(elapsed, readings)

        # Update info label
        self.info_label.setText(f"Points: {len(self.data_buffer)} | " f"Time: {elapsed:.1f}s | " f"Channels: {len(self.channels)}")

    def _update_chart(self):
        """Update the PyQtGraph chart with buffered data."""
        if not self.plot_widget or not self.data_buffer:
            return

        # Extract time series for each channel
        times = [d["timestamp"] for d in self.data_buffer]

        for ch in self.channels:
            if ch in self.traces:
                values = [d["readings"].get(ch, float("nan")) for d in self.data_buffer]
                self.traces[ch].setData(times, values)

    def _update_table(self, timestamp: float, readings: List):
        """Update the data table with new readings.

        Args:
            timestamp: Relative timestamp
            readings: List of Reading objects
        """
        # Add new row at top
        self.data_table.insertRow(0)

        # Set timestamp
        time_item = QTableWidgetItem(f"{timestamp:.3f}")
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data_table.setItem(0, 0, time_item)

        # Set channel values
        reading_dict = {r.channel: r for r in readings if r.channel}
        for i, ch in enumerate(self.channels):
            if ch in reading_dict:
                value = reading_dict[ch].value
                unit = reading_dict[ch].unit or ""
                text = f"{value:.6f} {unit}".strip()
            else:
                text = "---"

            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.data_table.setItem(0, i + 1, item)

        # Limit table rows
        max_rows = 100
        while self.data_table.rowCount() > max_rows:
            self.data_table.removeRow(self.data_table.rowCount() - 1)

    def clear_data(self):
        """Clear all data."""
        self.data_buffer.clear()
        self.start_time = None

        # Clear chart
        if self.plot_widget:
            for trace in self.traces.values():
                trace.setData([], [])

        # Clear table
        self.data_table.setRowCount(0)

        self.info_label.setText("Data cleared")
        self.data_cleared.emit()

    def _on_pause_clicked(self, checked: bool):
        """Handle pause button click."""
        self.paused = checked
        self.pause_btn.setText("Resume" if checked else "Pause")

    def _on_export_clicked(self):
        """Handle export button click."""
        if not self.data_buffer:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data to CSV",
            f"daq_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)",
        )

        if filename:
            self.export_to_csv(filename)

    def export_to_csv(self, filename: str):
        """Export data buffer to CSV file.

        Args:
            filename: Output file path
        """
        try:
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)

                # Header
                headers = ["Time (s)"] + [f"CH{ch}" for ch in self.channels]
                writer.writerow(headers)

                # Data rows
                for data in self.data_buffer:
                    row = [f"{data['timestamp']:.6f}"]
                    for ch in self.channels:
                        value = data["readings"].get(ch, "")
                        row.append(f"{value:.6f}" if value != "" else "")
                    writer.writerow(row)

            logger.info(f"Exported {len(self.data_buffer)} readings to {filename}")
            self.info_label.setText(f"Exported to {filename}")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.info_label.setText(f"Export failed: {e}")

    def get_data_for_analysis(self) -> List[Dict]:
        """Get the data buffer for AI analysis.

        Returns:
            Copy of the data buffer
        """
        return self.data_buffer.copy()

    def set_max_points(self, max_points: int):
        """Set the maximum number of points to store.

        Args:
            max_points: Maximum points in buffer
        """
        self.max_points = max_points
        # Trim if needed
        if len(self.data_buffer) > max_points:
            self.data_buffer = self.data_buffer[-max_points:]
