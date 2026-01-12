"""Background worker for DAQ/Data Logger acquisition.

This module provides a QThread-based worker that continuously acquires
readings from the Data Logger without blocking the GUI thread.

Thread Safety:
    - Uses Qt signals/slots for thread-safe communication
    - Worker runs in separate thread via QThread
    - GUI thread only handles display updates
    - No shared mutable state between threads

Signals:
    readings_ready(list): Emitted when new readings are acquired
    error_occurred(dict): Emitted on acquisition errors with structured error info
    status_update(str): Emitted for status updates during acquisition
    scan_complete(int): Emitted when a scan completes with scan count

Example:
    >>> worker = DAQWorker(daq, config)
    >>> worker.readings_ready.connect(data_view.update_readings)
    >>> worker.error_occurred.connect(handle_error)
    >>> worker.start()
    >>> # ... later ...
    >>> worker.stop()
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Union

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class DAQWorker(QThread):
    """Background thread worker for acquiring DAQ readings without blocking GUI.

    Signals:
        readings_ready: Emitted when readings are acquired (List[Reading])
        error_occurred: Emitted when an error occurs (dict with error details)
        status_update: Emitted for status messages (str)
        scan_complete: Emitted when scan completes (int scan_count)
    """

    readings_ready = pyqtSignal(list)  # List[Reading]
    error_occurred = pyqtSignal(dict)  # error info dictionary
    status_update = pyqtSignal(str)  # status message for user feedback
    scan_complete = pyqtSignal(int)  # scan count

    def __init__(
        self,
        daq,
        config: Optional[Dict] = None,
        parent=None,
    ):
        """Initialize DAQ worker.

        Args:
            daq: DataLogger instance
            config: Scan configuration dictionary with keys:
                - channels: List of channel numbers to scan
                - interval: Time between scans in seconds (default: 1.0)
                - duration: Total duration in seconds (None for infinite)
                - trigger_source: Trigger source (default: 'IMM')
            parent: Parent QObject
        """
        super().__init__(parent)
        self.daq = daq
        self.config = config or {}
        self.running = False
        self.scan_count = 0

        # Extract configuration
        self.channels = self.config.get("channels", [101, 102, 103])
        self.scan_interval = self.config.get("interval", 1.0)
        self.duration = self.config.get("duration", None)
        self.trigger_source = self.config.get("trigger_source", "IMM")

    def run(self):
        """Thread run method - continuously acquires readings."""
        self.running = True
        self.scan_count = 0
        start_time = datetime.now()

        logger.info(f"DAQ worker started: channels={self.channels}, " f"interval={self.scan_interval}s, duration={self.duration}")

        # Configure the DAQ for scanning
        try:
            self._configure_daq()
        except Exception as e:
            self._emit_error("configuration", e)
            self.running = False
            return

        while self.running:
            try:
                # Check duration limit
                if self.duration is not None:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= self.duration:
                        logger.info(f"DAQ worker: duration limit reached ({self.duration}s)")
                        self.status_update.emit(f"Logging complete: {self.scan_count} scans")
                        break

                # Acquire readings
                readings = self._acquire_readings()

                if readings:
                    self.scan_count += 1
                    self.readings_ready.emit(readings)
                    self.scan_complete.emit(self.scan_count)

                    # Update status
                    channels_str = ", ".join([f"CH{r.channel}" for r in readings if r.channel])
                    self.status_update.emit(f"Scan {self.scan_count}: {len(readings)} readings from {channels_str}")

            except Exception as e:
                self._emit_error("acquisition", e)

            # Sleep for scan interval (convert to milliseconds)
            self.msleep(int(self.scan_interval * 1000))

        logger.info(f"DAQ worker stopped: {self.scan_count} total scans")

    def _configure_daq(self):
        """Configure the DAQ for the scan operation."""
        if not self.daq or not self.daq.is_connected:
            raise RuntimeError("DAQ not connected")

        self.status_update.emit("Configuring DAQ...")

        # Set up scan list
        if self.channels:
            self.daq.set_scan_list(self.channels)

        # Configure trigger
        self.daq.set_trigger_source(self.trigger_source)
        self.daq.set_trigger_count(1)  # Single trigger per scan cycle

        self.status_update.emit("DAQ configured, starting acquisition...")

    def _acquire_readings(self) -> List:
        """Acquire readings from configured channels.

        Returns:
            List of Reading objects
        """
        if not self.daq or not self.daq.is_connected:
            self.status_update.emit("Not connected")
            return []

        try:
            # Use read() which initiates a scan and returns readings
            readings = self.daq.read()
            return readings

        except Exception as e:
            logger.warning(f"DAQ acquisition error: {e}")
            raise

    def _emit_error(self, operation: str, error: Exception):
        """Emit structured error information.

        Args:
            operation: The operation that failed
            error: The exception that occurred
        """
        logger.error(f"DAQ worker error during {operation}: {error}", exc_info=True)

        error_info = {
            "type": type(error).__name__,
            "message": f"DAQ {operation} error: {str(error)}",
            "details": str(error),
            "context": {
                "operation": f"daq_{operation}",
                "scan_interval": f"{self.scan_interval}s",
                "channels": str(self.channels),
                "scan_count": self.scan_count,
            },
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now(),
        }
        self.error_occurred.emit(error_info)

    def stop(self):
        """Stop the worker thread."""
        logger.info("Stopping DAQ worker...")
        self.running = False
        self.wait(2000)  # Wait up to 2 seconds for thread to finish

    def update_config(self, config: Dict):
        """Update the scan configuration.

        Note: This should be called when the worker is stopped.

        Args:
            config: New configuration dictionary
        """
        self.config = config
        self.channels = config.get("channels", self.channels)
        self.scan_interval = config.get("interval", self.scan_interval)
        self.duration = config.get("duration", self.duration)
        self.trigger_source = config.get("trigger_source", self.trigger_source)
