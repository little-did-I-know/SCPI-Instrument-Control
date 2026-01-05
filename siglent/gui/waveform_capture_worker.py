"""Background worker for single waveform capture.

This module provides a QThread-based worker that acquires waveforms from
the oscilloscope without blocking the GUI thread.

The worker solves the GUI freeze issue: SCPI queries take 100-500ms per channel,
and with network timeouts up to 5 seconds, the GUI would completely freeze during
capture. By running acquisition in a background thread, the GUI remains responsive
and can show progress updates and allow cancellation.

Thread Safety:
    - Uses Qt signals/slots for thread-safe communication
    - Worker runs in separate thread via QThread
    - GUI thread only handles display updates
    - No shared mutable state between threads

Signals:
    progress_update(str, int): Emitted for progress updates (message, percentage)
    waveforms_ready(list): Emitted when waveforms are acquired
    capture_complete(int): Emitted when capture completes (number of waveforms)
    error_occurred(str): Emitted on acquisition errors
"""

import logging
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from siglent.gui.utils.validators import WaveformValidator
from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class WaveformCaptureWorker(QThread):
    """Background thread worker for capturing waveforms without blocking GUI.

    Signals:
        progress_update: Emitted for progress (message: str, percentage: int)
        waveforms_ready: Emitted when waveforms are acquired (List[WaveformData])
        capture_complete: Emitted when capture completes (waveform_count: int)
        error_occurred: Emitted when an error occurs (str)
    """

    progress_update = pyqtSignal(str, int)  # message, percentage
    waveforms_ready = pyqtSignal(list)  # List[WaveformData]
    capture_complete = pyqtSignal(int)  # number of waveforms captured
    error_occurred = pyqtSignal(str)  # error message

    def __init__(self, scope, enabled_channels: List[int], parent=None):
        """Initialize waveform capture worker.

        Args:
            scope: Oscilloscope instance
            enabled_channels: List of channel numbers to capture from
            parent: Parent QObject
        """
        super().__init__(parent)
        self.scope = scope
        self.enabled_channels = enabled_channels
        self._cancelled = False

    def run(self):
        """Thread run method - captures waveforms from enabled channels."""
        logger.info(f"Capture worker started for channels: {self.enabled_channels}")

        waveforms = []
        errors = []
        total_channels = len(self.enabled_channels)

        for idx, ch_num in enumerate(self.enabled_channels):
            if self._cancelled:
                logger.info("Capture cancelled by user")
                self.error_occurred.emit("Capture cancelled")
                return

            # Update progress
            percentage = int((idx / total_channels) * 100)
            self.progress_update.emit(f"Downloading CH{ch_num} data from scope...", percentage)
            logger.info(f"Capturing waveform from channel {ch_num}...")

            try:
                # This may take several seconds for large waveforms (e.g., 5M samples)
                waveform = self.scope.get_waveform(ch_num)
                if waveform:
                    logger.info(f"Got waveform from CH{ch_num}: {len(waveform.voltage)} samples, " f"voltage range: {waveform.voltage.min():.3f} to {waveform.voltage.max():.3f} V")
                    waveforms.append(waveform)
                else:
                    error_msg = f"CH{ch_num}: No data returned"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            except Exception as e:
                error_msg = f"CH{ch_num}: {str(e)}"
                logger.error(f"Failed to capture from channel {ch_num}: {e}", exc_info=True)
                errors.append(error_msg)

        # Final progress update
        self.progress_update.emit("Validating waveforms...", 100)

        # Validate all captured waveforms before emitting
        if waveforms:
            valid_waveforms, invalid_info = WaveformValidator.validate_multiple(waveforms)

            # Log validation results
            for channel, issues in invalid_info:
                logger.warning(f"Capture worker: Invalid waveform CH{channel}: {'; '.join(issues)}")
                errors.append(f"CH{channel} validation failed: {'; '.join(issues)}")

            if valid_waveforms:
                logger.info(f"Capture complete: {len(valid_waveforms)} valid waveform(s) captured")
                self.waveforms_ready.emit(valid_waveforms)
                self.capture_complete.emit(len(valid_waveforms))
            else:
                error_msg = f"All {len(waveforms)} captured waveform(s) failed validation."
                if errors:
                    error_msg += "\n\nErrors:\n" + "\n".join(errors[:3])  # Show first 3 errors
                logger.error(f"Capture failed: {error_msg}")
                self.error_occurred.emit(error_msg)
        else:
            error_msg = "Could not capture waveforms."
            if errors:
                error_msg += "\n\nErrors:\n" + "\n".join(errors[:3])  # Show first 3 errors
            logger.error(f"Capture failed: {error_msg}")
            self.error_occurred.emit(error_msg)

        logger.info("Capture worker thread finished")

    def cancel(self):
        """Cancel the capture operation."""
        logger.info("Cancelling capture...")
        self._cancelled = True
