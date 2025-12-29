"""Test script for waveform display widget."""

import numpy as np
import pytest

pytest.skip("Interactive GUI demo; skipped in automated CI runs", allow_module_level=True)

import sys

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt

from siglent.gui.widgets.waveform_display import WaveformDisplay
from siglent.waveform import WaveformData


class TestWindow(QMainWindow):
    """Test window for waveform display."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waveform Display Test")
        self.setGeometry(100, 100, 1000, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Create waveform display
        self.display = WaveformDisplay()
        layout.addWidget(self.display)

        # Add test buttons
        btn_layout = QVBoxLayout()

        btn1 = QPushButton("Plot Test Sine Wave")
        btn1.clicked.connect(self.plot_sine)
        btn_layout.addWidget(btn1)

        btn2 = QPushButton("Plot Test Square Wave")
        btn2.clicked.connect(self.plot_square)
        btn_layout.addWidget(btn2)

        btn3 = QPushButton("Plot Multiple Channels")
        btn3.clicked.connect(self.plot_multiple)
        btn_layout.addWidget(btn3)

        btn4 = QPushButton("Clear Display")
        btn4.clicked.connect(self.display.clear_all)
        btn_layout.addWidget(btn4)

        layout.addLayout(btn_layout)

    def plot_sine(self):
        """Plot a test sine wave."""
        print("Plotting sine wave...")

        # Generate test data
        t = np.linspace(0, 1e-3, 1000)  # 1ms, 1000 samples
        v = np.sin(2 * np.pi * 1000 * t)  # 1kHz sine wave

        # Create waveform data
        waveform = WaveformData(time=t, voltage=v, channel=1, source="Test", description="1kHz Sine Wave")

        # Plot it
        self.display.plot_waveform(waveform, clear_others=True)
        print("Sine wave plotted")

    def plot_square(self):
        """Plot a test square wave."""
        print("Plotting square wave...")

        # Generate test data
        t = np.linspace(0, 1e-3, 1000)  # 1ms, 1000 samples
        v = np.sign(np.sin(2 * np.pi * 1000 * t))  # 1kHz square wave

        # Create waveform data
        waveform = WaveformData(time=t, voltage=v, channel=2, source="Test", description="1kHz Square Wave")

        # Plot it
        self.display.plot_waveform(waveform, clear_others=True)
        print("Square wave plotted")

    def plot_multiple(self):
        """Plot multiple test waveforms."""
        print("Plotting multiple waveforms...")

        t = np.linspace(0, 1e-3, 1000)

        # Sine wave on CH1
        wf1 = WaveformData(time=t, voltage=np.sin(2 * np.pi * 1000 * t), channel=1, source="Test", description="CH1: 1kHz Sine")

        # Square wave on CH2
        wf2 = WaveformData(time=t, voltage=0.5 * np.sign(np.sin(2 * np.pi * 500 * t)), channel=2, source="Test", description="CH2: 500Hz Square")

        # Sawtooth on CH3
        wf3 = WaveformData(time=t, voltage=0.8 * (2 * (t * 2000 % 1) - 1), channel=3, source="Test", description="CH3: 2kHz Sawtooth")

        # Plot all
        self.display.plot_multiple_waveforms([wf1, wf2, wf3])
        print("Multiple waveforms plotted")


def main():
    """Run the test application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Waveform Display Test")

    window = TestWindow()
    window.show()

    print("\n" + "=" * 60)
    print("Waveform Display Test")
    print("=" * 60)
    print("\nClick the buttons to test different waveform displays.")
    print("If the graphs update properly, the display widget is working correctly.")
    print("\nPress Ctrl+C in terminal or close window to exit.")
    print("=" * 60 + "\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
