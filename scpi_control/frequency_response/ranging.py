"""Vertical and horizontal ranging choices, expressed on the 1-2-5 sequence.

Real instrument firmware coerces both VDIV and TDIV to its own 1-2-5 sequence.
The mock stores whatever value it is handed (connection/mock/siglent.py:283), so
choosing 1-2-5 values here is what keeps mock and hardware geometry aligned
instead of quietly diverging -- and it is why none of these choices can be
validated against the mock. Nothing in this module performs I/O, so every rule
is table-testable without an instrument.
"""

import math
from typing import Optional

from scpi_control import exceptions

# Fraction of the 8-division vertical grid an autoranged trace should fill. Six
# leaves headroom for a response that grows slightly between the ranging capture
# and the measured one.
TARGET_DIVISIONS = 6.0

# Half the visible vertical grid: a trace reaching this has left the screen.
SCREEN_HALF_DIVISIONS = 4.0

# Below this fraction of one division, a trace is indistinguishable from the
# quantization floor.
MIN_DIVISIONS = 0.1

# Fewer distinct sample values than this means the trace has quantized flat --
# a dialect-independent floor test, since codes per division vary by encoding.
MIN_DISTINCT_SAMPLES = 4

# Below this, a cycle is described by too few samples for phase to be trusted;
# the point is kept but flagged.
MIN_SAMPLES_PER_CYCLE = 20.0

_MANTISSAS = (1.0, 2.0, 5.0)

# Floating point puts 0.001 a hair either side of its decade; without slack,
# round_125_up(1e-3) can return 2e-3.
_MANTISSA_TOLERANCE = 1e-9


def round_125_up(value: float) -> float:
    """Smallest 1-2-5-sequence value greater than or equal to `value`."""
    if value <= 0:
        raise exceptions.InvalidParameterError(f"Value must be positive to round onto the 1-2-5 sequence, not {value!r}")
    exponent = math.floor(math.log10(value))
    mantissa = value / (10.0**exponent)
    for step in _MANTISSAS:
        if mantissa <= step * (1.0 + _MANTISSA_TOLERANCE):
            return step * (10.0**exponent)
    return 10.0 ** (exponent + 1)


def choose_timebase(frequency_hz: float) -> float:
    """Seconds per division holding at least one cycle per division at `frequency_hz`.

    Rounded UP: a longer window holds more cycles, and cycles are what suppress
    spectral leakage. How many cycles that actually yields depends on the
    instrument's grid width and memory depth, so callers must measure the result
    from the returned time axis rather than assuming it.
    """
    if frequency_hz <= 0:
        raise exceptions.InvalidParameterError(f"Frequency must be positive, not {frequency_hz!r}")
    return round_125_up(1.0 / frequency_hz)


def choose_volts_per_div(peak_to_peak_volts: float) -> Optional[float]:
    """Vertical scale putting `peak_to_peak_volts` across TARGET_DIVISIONS.

    Returns None when there is no signal to range to -- a flat trace gives no
    target, and inventing one would send an arbitrary scale to the instrument.
    """
    if peak_to_peak_volts <= 0:
        return None
    return round_125_up(peak_to_peak_volts / TARGET_DIVISIONS)
