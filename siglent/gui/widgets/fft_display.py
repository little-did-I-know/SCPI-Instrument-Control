"""FFT display widget for frequency domain analysis."""

import logging
from typing import Dict, Optional

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class FFTDisplay(QWidget):
    """Widget for displaying FFT analysis results.

    Provides frequency domain plot with controls for window function,
    scale selection, and peak detection.

    Signals:
        fft_compute_requested: Emitted when FFT computation is requested (channel: str, window: str)
    """

    fft_compute_requested = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize FFT display.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.fft_result = None
        self.peak_markers = []

        self._init_ui()
        logger.info("FFT display initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Control panel
        control_group = self._create_control_panel()
        layout.addWidget(control_group)

        # FFT plot
        plot_group = self._create_plot_panel()
        layout.addWidget(plot_group)

        # Peak information
        peak_group = self._create_peak_panel()
        layout.addWidget(peak_group)

    def _create_control_panel(self) -> QGroupBox:
        """Create FFT control panel.

        Returns:
            Control panel group box
        """
        group = QGroupBox("FFT Controls")
        layout = QGridLayout(group)

        # Channel selector
        layout.addWidget(QLabel("Channel:"), 0, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["C1", "C2", "C3", "C4", "M1", "M2"])
        layout.addWidget(self.channel_combo, 0, 1)

        # Window function selector
        layout.addWidget(QLabel("Window:"), 0, 2)
        self.window_combo = QComboBox()
        self.window_combo.addItems(["Hanning", "Hamming", "Blackman", "Bartlett", "Rectangular", "Flattop"])
        layout.addWidget(self.window_combo, 0, 3)

        # Compute button
        self.compute_btn = QPushButton("Compute FFT")
        self.compute_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.compute_btn.clicked.connect(self._on_compute_fft)
        layout.addWidget(self.compute_btn, 0, 4)

        # Display options
        layout.addWidget(QLabel("Magnitude:"), 1, 0)
        self.magnitude_combo = QComboBox()
        self.magnitude_combo.addItems(["dB", "Linear"])
        self.magnitude_combo.currentTextChanged.connect(self._on_magnitude_scale_changed)
        layout.addWidget(self.magnitude_combo, 1, 1)

        # Log/Linear frequency axis
        self.log_freq_check = QCheckBox("Log Frequency")
        self.log_freq_check.toggled.connect(self._on_log_freq_changed)
        layout.addWidget(self.log_freq_check, 1, 2)

        # Show peaks
        self.show_peaks_check = QCheckBox("Show Peaks")
        self.show_peaks_check.setChecked(True)
        self.show_peaks_check.toggled.connect(self._on_show_peaks_changed)
        layout.addWidget(self.show_peaks_check, 1, 3)

        # Number of peaks to show
        layout.addWidget(QLabel("# Peaks:"), 1, 4)
        self.num_peaks_spin = QSpinBox()
        self.num_peaks_spin.setMinimum(1)
        self.num_peaks_spin.setMaximum(10)
        self.num_peaks_spin.setValue(3)
        self.num_peaks_spin.valueChanged.connect(self._update_peaks)
        layout.addWidget(self.num_peaks_spin, 1, 5)

        return group

    def _create_plot_panel(self) -> QGroupBox:
        """Create FFT plot panel.

        Returns:
            Plot panel group box
        """
        group = QGroupBox("Frequency Spectrum")
        layout = QVBoxLayout(group)

        # Create matplotlib figure
        self.figure = Figure(figsize=(8, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # Initial plot setup
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Magnitude (dB)")
        self.ax.set_title("FFT Spectrum")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

        return group

    def _create_peak_panel(self) -> QGroupBox:
        """Create peak information panel.

        Returns:
            Peak panel group box
        """
        group = QGroupBox("Peak Frequencies")
        layout = QVBoxLayout(group)

        # Peak labels
        self.peak_labels = []
        for i in range(3):
            peak_label = QLabel(f"Peak {i+1}: --")
            peak_label.setStyleSheet("font-family: monospace;")
            layout.addWidget(peak_label)
            self.peak_labels.append(peak_label)

        return group

    def _on_compute_fft(self):
        """Handle compute FFT button click."""
        channel = self.channel_combo.currentText()
        window = self.window_combo.currentText().lower()

        logger.info(f"FFT computation requested for {channel} with {window} window")
        self.fft_compute_requested.emit(channel, window)

    def _on_magnitude_scale_changed(self, scale: str):
        """Handle magnitude scale change.

        Args:
            scale: New scale ("dB" or "Linear")
        """
        if self.fft_result is not None:
            self._plot_fft(self.fft_result)

    def _on_log_freq_changed(self, enabled: bool):
        """Handle log frequency axis toggle.

        Args:
            enabled: Whether to use log scale
        """
        if self.fft_result is not None:
            self._plot_fft(self.fft_result)

    def _on_show_peaks_changed(self, enabled: bool):
        """Handle show peaks toggle.

        Args:
            enabled: Whether to show peak markers
        """
        self._update_peaks()

    def set_fft_result(self, fft_result):
        """Set and display FFT result.

        Args:
            fft_result: FFTResult object
        """
        self.fft_result = fft_result
        self._plot_fft(fft_result)
        self._update_peaks()

    def _plot_fft(self, fft_result):
        """Plot FFT result.

        Args:
            fft_result: FFTResult object
        """
        if fft_result is None:
            return

        # Clear previous plot
        self.ax.clear()

        # Get magnitude based on current scale selection
        use_db = self.magnitude_combo.currentText() == "dB"

        if use_db and not fft_result.magnitude_db:
            # Convert to dB
            magnitude = 20 * np.log10(fft_result.magnitude + 1e-12)
            ylabel = "Magnitude (dB)"
        elif not use_db and fft_result.magnitude_db:
            # Convert to linear
            magnitude = 10 ** (fft_result.magnitude / 20.0)
            ylabel = "Magnitude (Linear)"
        else:
            magnitude = fft_result.magnitude
            ylabel = "Magnitude (dB)" if use_db else "Magnitude (Linear)"

        # Plot spectrum
        self.ax.plot(fft_result.frequency, magnitude, "b-", linewidth=1.5, label="FFT")

        # Set axis labels
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(f"FFT Spectrum ({fft_result.window.capitalize()} Window)")
        self.ax.grid(True, alpha=0.3)

        # Set log/linear frequency scale
        if self.log_freq_check.isChecked():
            self.ax.set_xscale("log")
        else:
            self.ax.set_xscale("linear")

        # Adjust limits to skip DC component
        if len(fft_result.frequency) > 1:
            self.ax.set_xlim(fft_result.frequency[1], fft_result.frequency[-1])

        self.ax.legend()
        self.figure.tight_layout()
        self.canvas.draw()

        logger.info(f"FFT plot updated: {len(fft_result.frequency)} points")

    def _update_peaks(self):
        """Update peak markers and labels."""
        # Clear previous peak markers
        for marker in self.peak_markers:
            marker.remove()
        self.peak_markers.clear()

        # Clear peak labels
        for label in self.peak_labels:
            label.setText("--")

        if self.fft_result is None:
            return

        if not self.show_peaks_check.isChecked():
            self.canvas.draw()
            return

        # Get peak frequencies
        num_peaks = self.num_peaks_spin.value()
        peaks = self.fft_result.get_peak_frequency(num_peaks)

        # Get current magnitude data
        use_db = self.magnitude_combo.currentText() == "dB"
        if use_db and not self.fft_result.magnitude_db:
            magnitude = 20 * np.log10(self.fft_result.magnitude + 1e-12)
        elif not use_db and self.fft_result.magnitude_db:
            magnitude = 10 ** (self.fft_result.magnitude / 20.0)
        else:
            magnitude = self.fft_result.magnitude

        # Plot peak markers
        colors = ["r", "g", "m", "c", "y", "orange", "purple", "brown", "pink", "gray"]
        for i, (freq, mag_value) in enumerate(peaks):
            if i < len(self.peak_labels):
                # Find magnitude at this frequency for current scale
                freq_idx = np.argmin(np.abs(self.fft_result.frequency - freq))
                display_mag = magnitude[freq_idx]

                # Plot marker
                color = colors[i % len(colors)]
                marker = self.ax.plot(freq, display_mag, "o", color=color, markersize=10, label=f"Peak {i+1}")[0]
                self.peak_markers.append(marker)

                # Update label
                if freq < 1e3:
                    freq_str = f"{freq:.2f} Hz"
                elif freq < 1e6:
                    freq_str = f"{freq/1e3:.2f} kHz"
                elif freq < 1e9:
                    freq_str = f"{freq/1e6:.2f} MHz"
                else:
                    freq_str = f"{freq/1e9:.2f} GHz"

                if use_db:
                    mag_str = f"{display_mag:.2f} dB"
                else:
                    mag_str = f"{display_mag:.3e}"

                self.peak_labels[i].setText(f"Peak {i+1}: {freq_str} @ {mag_str}")

        self.ax.legend()
        self.canvas.draw()

    def clear_display(self):
        """Clear the FFT display."""
        self.fft_result = None
        self.ax.clear()
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Magnitude (dB)")
        self.ax.set_title("FFT Spectrum")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

        for label in self.peak_labels:
            label.setText("--")

    def update_available_channels(self, num_channels: int):
        """Update available channels in channel selector.

        Args:
            num_channels: Number of available channels (2 or 4)
        """
        channels = [f"C{i+1}" for i in range(num_channels)]
        channels.extend(["M1", "M2"])  # Always include math channels

        current_channel = self.channel_combo.currentText()
        self.channel_combo.clear()
        self.channel_combo.addItems(channels)

        # Restore selection if still valid
        if current_channel in channels:
            self.channel_combo.setCurrentText(current_channel)

        logger.info(f"FFT display updated for {num_channels} channels")
