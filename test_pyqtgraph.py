#!/usr/bin/env python
"""Quick test to verify PyQtGraph is working properly."""

import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

def main():
    """Test PyQtGraph with simple waveform."""
    print("Testing PyQtGraph installation...")

    app = QApplication(sys.argv)

    # Create plot window
    pw = pg.PlotWidget(title="PyQtGraph Test - You should see a sine wave")
    pw.setBackground('#1a1a1a')
    pw.showGrid(x=True, y=True, alpha=0.3)
    pw.setLabel('bottom', 'Time', units='s')
    pw.setLabel('left', 'Voltage', units='V')

    # Generate test waveform
    time = np.linspace(0, 1e-3, 1000)  # 1ms, 1000 points
    voltage = np.sin(2 * np.pi * 1000 * time)  # 1 kHz sine wave

    # Plot
    pen = pg.mkPen(color=(255, 215, 0), width=2)  # Yellow
    pw.plot(time, voltage, pen=pen, name="Test Signal")

    # Show window
    pw.show()
    pw.resize(800, 600)

    print("\n" + "=" * 60)
    print("PyQtGraph Test Window Opened!")
    print("=" * 60)
    print("\nYou should see:")
    print("  ✓ A dark background")
    print("  ✓ A yellow sine wave")
    print("  ✓ Grid lines")
    print("  ✓ Axis labels (Time and Voltage)")
    print("\nIf you see the waveform, PyQtGraph is working correctly!")
    print("Close the window to exit.")
    print("=" * 60)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
