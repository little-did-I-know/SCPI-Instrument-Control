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
    error_occurred(str): Emitted on acquisition errors

Example:
    >>> worker = LiveViewWorker(scope)
    >>> worker.waveforms_ready.connect(display.plot_multiple_waveforms)
    >>> worker.error_occurred.connect(handle_error)
    >>> worker.start()
    >>> # ... later ...
    >>> worker.stop()
"""

import logging
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class LiveViewWorker(QThread):
    """Background thread worker for acquiring waveforms without blocking GUI.

    Signals:
        waveforms_ready: Emitted when waveforms are acquired (List[WaveformData])
        error_occurred: Emitted when an error occurs (str)
    """

    waveforms_ready = pyqtSignal(list)  # List[WaveformData]
    error_occurred = pyqtSignal(str)  # error message

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
                self.error_occurred.emit(str(e))

            # Sleep for update interval
            self.msleep(self.update_interval)

        logger.info("Live view worker thread stopped")

    def _acquire_waveforms(self) -> List[WaveformData]:
        """Acquire waveforms from enabled channels.

        Returns:
            List of acquired waveforms
        """
        if not self.scope or not self.scope.is_connected:
            return []

        waveforms = []
        supported_channels = self.scope.supported_channels if hasattr(self.scope, "supported_channels") else range(1, 5)

        for ch_num in supported_channels:
            try:
                channel = getattr(self.scope, f"channel{ch_num}", None)
                if channel is None:
                    continue

                # Check if channel is enabled
                if channel.enabled:
                    logger.debug(f"Worker acquiring waveform from channel {ch_num}")
                    waveform = self.scope.get_waveform(ch_num)
                    if waveform:
                        waveforms.append(waveform)
                        logger.debug(f"Worker got {len(waveform.voltage)} samples from CH{ch_num}")

            except Exception as e:
                logger.debug(f"Worker error acquiring CH{ch_num}: {e}")
                continue

        return waveforms

    def stop(self):
        """Stop the worker thread."""
        logger.info("Stopping live view worker...")
        self.running = False
        self.wait(2000)  # Wait up to 2 seconds for thread to finish
