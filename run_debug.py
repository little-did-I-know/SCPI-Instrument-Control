#!/usr/bin/env python
"""Run Siglent GUI with debug logging enabled."""

import logging
import sys

# Configure logging to show EVERYTHING
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)8s] %(name)s - %(message)s',
    datefmt='%H:%M:%S'
)

# Reduce noise from some libraries
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def main():
    """Run the GUI with debug logging."""
    logger.info("=" * 80)
    logger.info("Starting Siglent GUI with DEBUG logging")
    logger.info("=" * 80)
    logger.info("")
    logger.info("INSTRUCTIONS:")
    logger.info("1. Connect to your oscilloscope")
    logger.info("2. Go to Channels tab and verify CH1 is enabled (checkbox should be checked)")
    logger.info("3. Click Acquisition -> Live View (or press Ctrl+R)")
    logger.info("4. Watch this console for log messages")
    logger.info("")
    logger.info("Look for these key messages:")
    logger.info("  - '=== Live view update started ==='")
    logger.info("  - 'Channel 1: enabled=True'")
    logger.info("  - 'SUCCESS: Got XXXX samples from channel 1'")
    logger.info("  - '*** PLOTTING X waveforms ***'")
    logger.info("  - 'PyQtGraph _update_plot called'")
    logger.info("")
    logger.info("=" * 80)
    logger.info("")

    # Import and run
    from PyQt6.QtWidgets import QApplication
    from siglent.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
