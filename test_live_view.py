"""Test script to debug live view issues."""

import logging
import sys

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Test the GUI
from PyQt6.QtWidgets import QApplication
from siglent.gui.main_window import MainWindow

def main():
    """Test live view functionality."""
    logger.info("Starting live view test...")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    logger.info("Window shown - please connect to scope and enable live view")
    logger.info("Watch the console for debug messages")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
