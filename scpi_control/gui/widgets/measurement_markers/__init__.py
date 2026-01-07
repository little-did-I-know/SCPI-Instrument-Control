"""Specialized measurement marker implementations.

This package contains concrete implementations of measurement markers
for different types of oscilloscope measurements.

Marker Types:
    FrequencyMarker: Frequency and period measurements
        - Auto-detects signal period using zero-crossing or peak detection
        - Displays two vertical gates spanning one complete cycle
        - Supports: FREQ, PER

    VoltageMarker: Voltage-based measurements
        - Horizontal lines at measured voltage levels
        - Supports: PKPK, AMPL, MAX, MIN, RMS, MEAN, TOP, BASE

    TimingMarker: Timing and edge measurements
        - Threshold detection (10%/90% levels)
        - Edge finding for rise/fall time
        - Pulse width and duty cycle
        - Supports: RISE, FALL, WID, NWID, DUTY

All markers inherit from MeasurementMarker base class and implement:
    - render(): Visual representation on matplotlib axes
    - calculate_measurement(): NumPy-based measurement computation
    - update_position(): Handle user interaction
"""

from .frequency_marker import FrequencyMarker
from .timing_marker import TimingMarker
from .voltage_marker import VoltageMarker

__all__ = ["FrequencyMarker", "VoltageMarker", "TimingMarker"]
