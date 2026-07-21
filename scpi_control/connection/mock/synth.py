"""State-coupled waveform synthesis for MockConnection.

Computes int8 sample codes from the mock's *current* state (timebase, V/div,
offset, trigger) via scpi_control.signal_synth, so SCPI SET commands visibly
change the next capture. Explicit waveform_payloads bytes always win. The
volts->codes inverse mirrors waveform_transfer's converters: Siglent/LeCroy
subtract the channel offset on read (codes add it back); the Tek mock preamble
does not model offset (include_offset=False).
"""

from dataclasses import replace
from typing import TYPE_CHECKING, Dict

import numpy as np

from scpi_control.signal_synth import SignalSpec, synthesize

if TYPE_CHECKING:
    from scpi_control.connection.mock.base import MockConnection

DIVISIONS = 14  # horizontal grid, matches SiglentTransfer._generate_time_axis
MAX_POINTS = 14_000
CODES_PER_DIV = 25  # int8 path, matches WAVEFORM_CODE_PER_DIV_8BIT
CODE_LIMIT = 127
_DRIFT_FRACTION = 0.137  # free-run phase drift per acquisition (non-period-aligned)

_DEFAULT_SPECS: Dict[int, SignalSpec] = {
    1: SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, noise_rms=0.01),
    2: SignalSpec(kind="sine", frequency=2_000.0, amplitude=0.5, noise_rms=0.01),
    3: SignalSpec(kind="sine", frequency=5_000.0, amplitude=0.25, noise_rms=0.01),
    4: SignalSpec(kind="sine", frequency=10_000.0, amplitude=0.125, noise_rms=0.01),
}
_FALLBACK_SPEC = SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.01)


def spec_for(conn: "MockConnection", channel: int) -> SignalSpec:
    """The signal a channel 'sees': user-specified, else the channel default."""
    return conn._signals.get(channel) or _DEFAULT_SPECS.get(channel, _FALLBACK_SPEC)


def point_count(conn: "MockConnection", channel: int) -> int:
    """Sample count the next waveform response will carry."""
    explicit = conn._waveform_payloads.get(channel)
    if explicit is not None:
        return len(explicit)
    window = DIVISIONS * conn.timebase
    return max(2, min(MAX_POINTS, int(round(conn.sample_rate * window))))


def payload_for(conn: "MockConnection", channel: int, *, include_offset: bool) -> bytes:
    """int8 code bytes for a channel: explicit payload if given, else synthesized."""
    explicit = conn._waveform_payloads.get(channel)
    if explicit is not None:
        return explicit
    spec = spec_for(conn, channel)
    n = point_count(conn, channel)
    count = conn._acquisition_counts.get(channel, 0)
    conn._acquisition_counts[channel] = count + 1
    window = DIVISIONS * conn.timebase
    t0 = count * window * _DRIFT_FRACTION  # free-run; Task 5 adds trigger alignment
    per_acquisition = spec if spec.seed is None else replace(spec, seed=spec.seed + count)
    volts = synthesize(per_acquisition, conn.sample_rate, n, t0=t0)
    vdiv = conn._voltage_scales.get(channel, 1.0)
    voffset = conn._voltage_offsets.get(channel, 0.0) if include_offset else 0.0
    codes = np.clip(np.rint((volts + voffset) * CODES_PER_DIV / vdiv), -CODE_LIMIT, CODE_LIMIT)
    return codes.astype(np.int8).tobytes()
