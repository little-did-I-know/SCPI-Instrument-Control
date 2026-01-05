"""Background worker for live view waveform acquisition.

This module provides a QThread-based worker that continuously acquires
waveforms from the oscilloscope without blocking the GUI thread.

The worker solves a critical performance issue: SCPI queries take 100-500ms
each, and querying multiple channels every 200ms would freeze the GUI.
By running acquisition in a background thread, the GUI remains responsive
while waveforms are continuously updated.

Thread Safety:
    - Uses Qt signals/slots for thread-safe communication
    - Worker runs in separate thread via QThread
    - GUI thread only handles display updates (<1ms)
    - No shared mutable state between threads

Signals:
    waveforms_ready(list): Emitted when new waveforms are acquired
    error_occurred(dict): Emitted on acquisition errors with structured error info
    status_update(str): Emitted for status updates during acquisition

Example:
    >>> worker = LiveViewWorker(scope)
    >>> worker.waveforms_ready.connect(display.plot_multiple_waveforms)
    >>> worker.error_occurred.connect(handle_error)
    >>> worker.start()
    >>> # ... later ...
    >>> worker.stop()
"""

import logging
import traceback
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from siglent.gui.utils.validators import WaveformValidator
from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class LiveViewWorker(QThread):
    """Background thread worker for acquiring waveforms without blocking GUI.

    Signals:
        waveforms_ready: Emitted when waveforms are acquired (List[WaveformData])
        error_occurred: Emitted when an error occurs (dict with error details)
        status_update: Emitted for status messages (str)
    """

    waveforms_ready = pyqtSignal(list)  # List[WaveformData]
    error_occurred = pyqtSignal(dict)  # error info dictionary
    status_update = pyqtSignal(str)  # status message for user feedback

    def __init__(self, scope, parent=None):
        """Initialize live view worker.

        Args:
            scope: Oscilloscope instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.scope = scope
        self.running = False
        self.update_interval = 200  # ms

    def run(self):
        """Thread run method - continuously acquires waveforms."""
        self.running = True
        logger.info("Live view worker thread started")

        while self.running:
            try:
                # Acquire waveforms from enabled channels
                waveforms = self._acquire_waveforms()

                if waveforms:
                    # Emit signal with waveforms
                    self.waveforms_ready.emit(waveforms)
                else:
                    logger.debug("No waveforms acquired in this cycle")

            except Exception as e:
                logger.error(f"Error in live view worker: {e}", exc_info=True)

                # Create structured error info for detailed error dialog
                error_info = {
                    "type": type(e).__name__,
                    "message": f"Live view error: {str(e)}",
                    "details": str(e),
                    "context": {
                        "operation": "live_view_acquisition",
                        "update_interval": f"{self.update_interval}ms",
                    },
                    "traceback": traceback.format_exc(),
                    "timestamp": datetime.now(),
                }
                self.error_occurred.emit(error_info)

            # Sleep for update interval
            self.msleep(self.update_interval)

        logger.info("Live view worker thread stopped")

    def _acquire_waveforms(self) -> List[WaveformData]:
        """Acquire waveforms from enabled channels.

        Returns:
            List of validated waveforms (only valid waveforms are included)
        """
        if not self.scope or not self.scope.is_connected:
            logger.debug("Worker: scope not connected")
            self.status_update.emit("Not connected")
            return []

        waveforms = []
        valid_waveforms = []
        supported_channels = self.scope.supported_channels if hasattr(self.scope, "supported_channels") else range(1, 5)

        # Emit status: checking channels
        self.status_update.emit("Checking enabled channels...")

        enabled_channels = []
        for ch_num in supported_channels:
            try:
                channel = getattr(self.scope, f"channel{ch_num}", None)
                if channel is not None and channel.enabled:
                    enabled_channels.append(ch_num)
            except Exception:
                continue

        if not enabled_channels:
            self.status_update.emit("No enabled channels")
            return []

        # Acquire from each enabled channel
        for ch_num in enabled_channels:
            try:
                self.status_update.emit(f"Acquiring CH{ch_num}...")
                logger.debug(f"Worker acquiring waveform from channel {ch_num}")
                waveform = self.scope.get_waveform(ch_num)
                if waveform:
                    waveforms.append(waveform)
                    logger.debug(f"Worker got {len(waveform.voltage)} samples from CH{ch_num}")

            except Exception as e:
                # Log at WARNING level so users can see acquisition errors
                logger.warning(f"Worker error acquiring CH{ch_num}: {e}")
                self.status_update.emit(f"Error on CH{ch_num}: {str(e)[:40]}")
                continue

        # Validate all acquired waveforms before emitting
        if waveforms:
            self.status_update.emit("Validating waveforms...")
            valid_waveforms, invalid_info = WaveformValidator.validate_multiple(waveforms)

            # Log validation results at WARNING level (visible to users)
            for channel, issues in invalid_info:
                logger.warning(f"Worker: Invalid waveform CH{channel}: {'; '.join(issues)}")

            if valid_waveforms:
                logger.info(f"Worker: Successfully acquired {len(valid_waveforms)} valid waveform(s)")
                # Emit status with channel info
                channels_str = ", ".join([f"CH{w.channel}" for w in valid_waveforms])
                samples_str = ", ".join([f"{len(w.voltage):,}" for w in valid_waveforms])
                self.status_update.emit(f"Live view: {channels_str} ({samples_str} samples)")
            else:
                logger.error(f"Worker: All {len(waveforms)} acquired waveform(s) failed validation")
                self.status_update.emit("All waveforms invalid")

        return valid_waveforms

    def stop(self):
        """Stop the worker thread."""
        logger.info("Stopping live view worker...")
        self.running = False
        self.wait(2000)  # Wait up to 2 seconds for thread to finish
