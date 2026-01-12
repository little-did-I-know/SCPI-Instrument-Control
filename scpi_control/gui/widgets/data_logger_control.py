"""Main Data Logger control widget.

This module provides the main container widget that combines channel
configuration, scan settings, real-time data view, and AI analysis panel.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from scpi_control.data_logger import DataLogger

from ..daq_worker import DAQWorker
from .daq_ai_panel import DAQAIPanel
from .daq_channel_config import DAQChannelConfig
from .daq_data_view import DAQDataView
from .daq_scan_config import DAQScanConfig

logger = logging.getLogger(__name__)


class DataLoggerControl(QWidget):
    """Main Data Logger control widget.

    Combines channel configuration, scan settings, data visualization,
    and AI analysis into a unified interface.

    Signals:
        connection_changed: Emitted when connection state changes
        error_occurred: Emitted when an error occurs
    """

    connection_changed = pyqtSignal(bool)  # connected state
    error_occurred = pyqtSignal(dict)  # error info

    def __init__(self, parent=None):
        """Initialize the Data Logger control widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.daq: Optional[DataLogger] = None
        self.worker: Optional[DAQWorker] = None
        self.start_time: Optional[datetime] = None
        self.ai_panel: Optional[DAQAIPanel] = None

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """Set up the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Left panel - Configuration
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        # Connection status
        self.connection_frame = QFrame()
        self.connection_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        conn_layout = QHBoxLayout(self.connection_frame)
        conn_layout.setContentsMargins(8, 4, 8, 4)

        self.connection_indicator = QLabel("\u25cf")  # Circle
        self.connection_indicator.setStyleSheet("color: #ff4444; font-size: 16px;")
        conn_layout.addWidget(self.connection_indicator)

        self.connection_label = QLabel("Not Connected")
        self.connection_label.setStyleSheet("font-weight: bold;")
        conn_layout.addWidget(self.connection_label)
        conn_layout.addStretch()

        left_layout.addWidget(self.connection_frame)

        # Channel configuration
        self.channel_config = DAQChannelConfig()
        self.channel_config.config_changed.connect(self._on_channel_config_changed)
        left_layout.addWidget(self.channel_config, stretch=2)

        # Scan configuration
        self.scan_config = DAQScanConfig()
        self.scan_config.start_requested.connect(self._on_start_requested)
        self.scan_config.stop_requested.connect(self._on_stop_requested)
        left_layout.addWidget(self.scan_config, stretch=1)

        # Right panel - Data View (with splitter for future AI panel)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Data view (chart and table)
        self.data_view = DAQDataView()
        self.data_view.data_cleared.connect(self._on_data_cleared)
        right_splitter.addWidget(self.data_view)

        # AI Analysis panel
        self.ai_panel = DAQAIPanel()
        self.ai_panel.set_data_providers(
            data_provider=self.data_view.get_data_for_analysis,
            channels_provider=self.channel_config.get_enabled_channels,
            configs_provider=self.channel_config.get_all_configs,
        )
        right_splitter.addWidget(self.ai_panel)

        # Set splitter sizes (80% data view, 20% AI panel)
        right_splitter.setSizes([800, 200])

        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_splitter)

        # Set splitter sizes (25% config, 75% data)
        main_splitter.setSizes([300, 900])

        main_layout.addWidget(main_splitter)

    def _setup_timer(self):
        """Set up the elapsed time update timer."""
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)  # Update every second
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)

    def set_daq(self, daq: Optional[DataLogger]):
        """Set the DataLogger instance.

        Args:
            daq: DataLogger instance or None to disconnect
        """
        # Stop any running acquisition
        if self.worker:
            self._stop_acquisition()

        self.daq = daq

        if daq and daq.is_connected:
            self._update_connection_status(True)
            self._initialize_channels()
        else:
            self._update_connection_status(False)

    def _update_connection_status(self, connected: bool):
        """Update connection status display.

        Args:
            connected: Whether DAQ is connected
        """
        if connected:
            self.connection_indicator.setStyleSheet("color: #4caf50; font-size: 16px;")
            model = self.daq.model_capability.model_name if self.daq else "Unknown"
            self.connection_label.setText(f"Connected: {model}")
        else:
            self.connection_indicator.setStyleSheet("color: #ff4444; font-size: 16px;")
            self.connection_label.setText("Not Connected")

        self.connection_changed.emit(connected)

    def _initialize_channels(self):
        """Initialize channel configuration from connected DAQ."""
        if not self.daq:
            return

        try:
            channels = self.daq.model_capability.get_all_channels()
            self.channel_config.set_available_channels(channels)
            self.data_view.set_channels(channels[:8])  # Default to first 8 channels
            logger.info(f"Initialized {len(channels)} channels")
        except Exception as e:
            logger.error(f"Failed to initialize channels: {e}")
            self._emit_error("initialization", e)

    def _on_channel_config_changed(self, configs: Dict[int, Dict]):
        """Handle channel configuration change.

        Args:
            configs: Channel configurations
        """
        enabled_channels = self.channel_config.get_enabled_channels()
        self.data_view.set_channels(enabled_channels)

        # If running, update worker config
        if self.worker and self.worker.isRunning():
            # Note: Hot config update would require worker restart
            logger.info(f"Channel config changed: {len(enabled_channels)} channels enabled")

    def _on_start_requested(self):
        """Handle start logging request."""
        if not self.daq or not self.daq.is_connected:
            QMessageBox.warning(
                self,
                "Not Connected",
                "Please connect to a DAQ instrument first.",
            )
            return

        enabled_channels = self.channel_config.get_enabled_channels()
        if not enabled_channels:
            QMessageBox.warning(
                self,
                "No Channels Selected",
                "Please enable at least one channel for scanning.",
            )
            return

        self._start_acquisition(enabled_channels)

    def _on_stop_requested(self):
        """Handle stop logging request."""
        self._stop_acquisition()

    def _start_acquisition(self, channels: List[int]):
        """Start data acquisition.

        Args:
            channels: List of channels to scan
        """
        if self.worker and self.worker.isRunning():
            return

        # Get scan config
        scan_config = self.scan_config.get_config()

        # Create worker config
        config = {
            "channels": channels,
            "interval": scan_config["interval"],
            "duration": scan_config["duration"],
            "trigger_source": scan_config["trigger_source"],
        }

        # Create and start worker
        self.worker = DAQWorker(self.daq, config, parent=self)
        self.worker.readings_ready.connect(self._on_readings_ready)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.status_update.connect(self._on_status_update)
        self.worker.scan_complete.connect(self._on_scan_complete)
        self.worker.finished.connect(self._on_worker_finished)

        # Clear previous data and start
        self.data_view.clear_data()
        self.scan_config.reset_statistics()
        self.start_time = datetime.now()

        self.worker.start()
        self.scan_config.set_running(True)
        self.elapsed_timer.start()

        logger.info(f"Started acquisition: {len(channels)} channels, interval={scan_config['interval']}s")

    def _stop_acquisition(self):
        """Stop data acquisition."""
        if self.worker:
            self.worker.stop()
            self.worker = None

        self.scan_config.set_running(False)
        self.elapsed_timer.stop()
        logger.info("Acquisition stopped")

    def _on_readings_ready(self, readings: list):
        """Handle new readings from worker.

        Args:
            readings: List of Reading objects
        """
        self.data_view.update_readings(readings)

        # Update channel config with latest readings
        for reading in readings:
            if reading.channel:
                self.channel_config.update_reading(
                    reading.channel,
                    reading.value,
                    reading.unit or "",
                )

    def _on_worker_error(self, error_info: dict):
        """Handle worker error.

        Args:
            error_info: Error information dictionary
        """
        logger.error(f"Worker error: {error_info.get('message', 'Unknown error')}")
        self.error_occurred.emit(error_info)

    def _on_status_update(self, status: str):
        """Handle worker status update.

        Args:
            status: Status message
        """
        self.scan_config.update_status(status)

    def _on_scan_complete(self, scan_count: int):
        """Handle scan completion.

        Args:
            scan_count: Total number of scans completed
        """
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.scan_config.update_statistics(scan_count, elapsed)

    def _on_worker_finished(self):
        """Handle worker thread finished."""
        self.scan_config.set_running(False)
        self.elapsed_timer.stop()
        logger.info("Worker thread finished")

    def _on_data_cleared(self):
        """Handle data cleared event."""
        self.channel_config.clear_all_readings()
        self.scan_config.reset_statistics()
        self.start_time = None

    def _update_elapsed_time(self):
        """Update elapsed time display."""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            scan_count = int(self.scan_config.scan_count_label.text())
            self.scan_config.update_statistics(scan_count, elapsed)

    def _emit_error(self, operation: str, error: Exception):
        """Emit structured error information.

        Args:
            operation: The operation that failed
            error: The exception that occurred
        """
        error_info = {
            "type": type(error).__name__,
            "message": f"Data Logger {operation} error: {str(error)}",
            "details": str(error),
            "context": {"operation": f"daq_{operation}"},
            "timestamp": datetime.now(),
        }
        self.error_occurred.emit(error_info)

    def get_data_for_analysis(self) -> List[Dict]:
        """Get collected data for AI analysis.

        Returns:
            List of data dictionaries
        """
        return self.data_view.get_data_for_analysis()

    def closeEvent(self, event):
        """Handle widget close event."""
        self._stop_acquisition()
        super().closeEvent(event)
