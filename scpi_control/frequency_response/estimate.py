"""Transfer-function estimation from one reference capture and one response capture.

No I/O: everything here works on arrays that are already in memory, which is
what makes the accuracy rules testable against synthetic signals with known
answers rather than against an instrument.
"""

import math
from typing import Optional, Tuple

import numpy as np

from scpi_control import exceptions
from scpi_control.frequency_response.model import ResponsePoint
from scpi_control.frequency_response.ranging import MIN_DISTINCT_SAMPLES, MIN_DIVISIONS, SCREEN_HALF_DIVISIONS
from scpi_control.waveform import WaveformData

# Two samples at the rail, not one: a single sample there is ordinary for a sine
# whose peak lands on a sample, while two means the trace is sitting on it.
_MIN_RAIL_SAMPLES = 2


def tone_at(volts: np.ndarray, times: np.ndarray, frequency_hz: float) -> complex:
    """Complex amplitude of `frequency_hz` in one trace (Hann-windowed single-bin DFT).

    Evaluated at the EXACT frequency, never at the nearest FFT bin. A drive
    frequency landing half a bin from the grid is the common case once the
    timebase is rounded to a 1-2-5 value, and snapping costs about 15% of
    amplitude and 90 degrees of phase there. The v4.0.0 report-honesty work
    found the same defect in THD, reading harmonics at n * rounded_bin.

    Returns half the tone's peak amplitude as a complex number: magnitude is
    amplitude/2, argument is the tone's phase.
    """
    if len(volts) < 2:
        raise exceptions.InvalidParameterError(f"Need at least 2 samples to estimate a tone, got {len(volts)}")
    centred = np.asarray(volts, dtype=float) - float(np.mean(volts))
    window = np.hanning(len(centred))
    return complex(np.sum(centred * window * np.exp(-2j * np.pi * frequency_hz * np.asarray(times, dtype=float))) / np.sum(window))


def _peak_to_peak(waveform: WaveformData) -> float:
    return float(np.max(waveform.voltage) - np.min(waveform.voltage))


def _at_floor(waveform: WaveformData) -> bool:
    """True when the trace cannot be told apart from the quantization floor.

    Two complementary rules, because codes per division differ by dialect and
    encoding (25 on the legacy int8 path, thousands on the modern WORD path) and
    this module has no business knowing which one produced the samples: a small
    trace on a coarse scale fails the division test, and a trace that has
    quantized flat fails the distinct-value test.
    """
    if len(np.unique(waveform.voltage)) < MIN_DISTINCT_SAMPLES:
        return True
    if waveform.voltage_scale is None:
        return False
    return _peak_to_peak(waveform) < MIN_DIVISIONS * waveform.voltage_scale


def _off_screen(waveform: WaveformData) -> bool:
    """True when the trace reaches beyond the visible grid.

    Off-screen and clipped are treated alike: whether the samples were clamped
    by the ADC or merely drawn past the graticule, a peak that left the screen
    cannot be trusted to carry the tone's real amplitude.
    """
    if waveform.voltage_scale is None:
        return False
    limit = SCREEN_HALF_DIVISIONS * waveform.voltage_scale
    excursion = np.abs(np.asarray(waveform.voltage, dtype=float) - waveform.voltage_offset)
    return int(np.count_nonzero(excursion >= limit)) >= _MIN_RAIL_SAMPLES


def _exclusion(reference: WaveformData, response: WaveformData) -> Optional[str]:
    if _at_floor(reference):
        return "reference below vertical resolution — source connected?"
    if _at_floor(response):
        return "response below vertical resolution"
    if _off_screen(response):
        return f"response reaches beyond ±{SCREEN_HALF_DIVISIONS:.0f} divisions (clipped or off screen)"
    return None


def _geometry(response: WaveformData, frequency_hz: float) -> Tuple[float, float]:
    """(cycles in the window, samples per cycle), measured from the returned axis.

    Measured, not assumed: the instrument coerces the timebase it was sent, and
    a memory-depth cap can truncate the window it delivers, so neither number
    follows from what the sweep asked for.
    """
    times = np.asarray(response.time, dtype=float)
    span = float(times[-1] - times[0]) if len(times) > 1 else 0.0
    sample_rate = response.sample_rate or (len(times) / span if span > 0 else 0.0)
    return span * frequency_hz, (sample_rate / frequency_hz if frequency_hz > 0 else 0.0)


def estimate_point(reference: WaveformData, response: WaveformData, frequency_hz: float) -> ResponsePoint:
    """Gain and phase of `response` relative to `reference` at `frequency_hz`."""
    if frequency_hz <= 0:
        raise exceptions.InvalidParameterError(f"Frequency must be positive, not {frequency_hz!r}")

    cycles, samples_per_cycle = _geometry(response, frequency_hz)
    common = dict(
        frequency_hz=frequency_hz,
        reference_vpp=_peak_to_peak(reference),
        response_vpp=_peak_to_peak(response),
        cycles_in_window=cycles,
        samples_per_cycle=samples_per_cycle,
        volts_per_div=response.voltage_scale,
    )

    excluded = _exclusion(reference, response)
    if excluded is not None:
        return ResponsePoint(gain_db=None, phase_deg=None, excluded_reason=excluded, **common)

    reference_tone = tone_at(reference.voltage, reference.time, frequency_hz)
    if reference_tone == 0:
        # Belt and braces: the floor rule should have caught this, but dividing
        # by zero would produce inf rather than an honest exclusion.
        return ResponsePoint(gain_db=None, phase_deg=None, excluded_reason="reference carries no energy at the drive frequency", **common)

    ratio = tone_at(response.voltage, response.time, frequency_hz) / reference_tone
    if abs(ratio) == 0:
        return ResponsePoint(gain_db=None, phase_deg=None, excluded_reason="response carries no energy at the drive frequency", **common)

    return ResponsePoint(gain_db=20.0 * math.log10(abs(ratio)), phase_deg=math.degrees(np.angle(ratio)), **common)
