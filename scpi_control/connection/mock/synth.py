"""State-coupled waveform synthesis for MockConnection.

Computes int8 sample codes from the mock's *current* state (timebase, V/div,
offset, trigger) via scpi_control.signal_synth, so SCPI SET commands visibly
change the next capture. Explicit waveform_payloads bytes always win. The
volts->codes inverse mirrors waveform_transfer's converters: Siglent/LeCroy
subtract the channel offset on read (codes add it back); the Tek mock preamble
does not model offset (include_offset=False).
"""

from dataclasses import replace
from typing import TYPE_CHECKING, Dict, Optional

import numpy as np

from scpi_control.signal_synth import PERIODIC_KINDS, SignalSpec, SuperposedSignal, synthesize, synthesize_combined

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


def _is_rising(slope_token) -> bool:
    """Normalize per-dialect slope tokens: POS/RISing/RISE vs NEG/FALLing/FALL."""
    token = str(slope_token).upper()
    return not (token.startswith("NEG") or token.startswith("FALL"))


def _trigger_crossing(spec: SignalSpec, level: float, rising: bool) -> Optional[float]:
    """Time within one period where the ideal signal crosses `level`, or None."""
    if spec.kind not in PERIODIC_KINDS:
        return None
    period = 1.0 / spec.frequency
    n = 4096
    # Every impairment is stripped, not just the noise: this search is for the
    # IDEAL crossing, and an impairment that shifts it would shift t0 with it --
    # trigger alignment would then jitter with the impairment settings instead of
    # sitting on the signal's own edge. (Ringing moves an exponential's crossing
    # from 68.85 us to 66.41 us, and re-synthesizing it here costs ~20 ms per
    # acquisition on the continuous kinds.)
    ideal = synthesize(replace(spec, noise_rms=0.0, seed=0, ringing_frequency=0.0, drift_amplitude=0.0, glitch_rate=0.0), sample_rate=n / period, n_points=n)
    above = ideal >= level
    # np.roll makes the comparison periodic: a crossing at the period boundary
    # (e.g. a zero-phase sine rising through 0 at t=0/t=P) is not missed.
    nxt = np.roll(above, -1)
    if rising:
        indices = np.flatnonzero(~above & nxt)
    else:
        indices = np.flatnonzero(above & ~nxt)
    if indices.size == 0:
        return None
    return float(indices[0] + 1) * (period / n)


def spec_for(conn: "MockConnection", channel: int) -> SignalSpec:
    """The signal a channel 'sees': user-specified, else the channel default.

    A stored value is either a SignalSpec or a zero-argument callable returning
    one. The callable is invoked at EVERY acquisition, which is what lets a live
    source -- an AwgLoopback reading a mock AWG's state -- change what the scope
    captures between captures. Everything downstream (point_count, raw_volts, the
    trigger-crossing search, the three vendor personalities) keeps receiving a
    plain SignalSpec and never learns the difference.
    """
    source = conn._signals.get(channel)
    if source is None:
        return _DEFAULT_SPECS.get(channel, _FALLBACK_SPEC)
    return source() if callable(source) else source


def point_count(conn: "MockConnection", channel: int) -> int:
    """Sample count the next waveform response will carry."""
    explicit = conn._waveform_payloads.get(channel)
    if explicit is not None:
        return len(explicit)
    window = DIVISIONS * conn.timebase
    return max(2, min(MAX_POINTS, int(round(conn.sample_rate * window))))


def raw_volts(conn: "MockConnection", channel: int, n_override: Optional[int] = None) -> np.ndarray:
    """Synthesize one channel's sample volts, advancing its acquisition count.

    Shared by the legacy int8 encoder (payload_for) and the modern-dialect
    encoder (connection/mock/siglent.py's build_waveform_preamble/
    build_waveform_data), so both dialects see the same signal for the same
    mock state -- only the code-per-division scaling that turns volts into
    codes differs.

    Args:
        n_override: Sample count to synthesize instead of `point_count`'s
            single-shot formula. Task 19 (deep-memory chunking): the modern
            dialect's `conn.record_length`, when set, can exceed
            `conn.max_points` (the per-:WAVeform:DATA?-transfer cap) -- the
            FULL record must still be synthesized as one call so a caller can
            slice consistent windows out of it afterwards.
    """
    source = conn._signals.get(channel)
    n = point_count(conn, channel) if n_override is None else n_override
    count = conn._acquisition_counts.get(channel, 0)
    conn._acquisition_counts[channel] = count + 1
    window = DIVISIONS * conn.timebase

    if isinstance(source, SuperposedSignal):
        # components[0] is the PRIMARY component: it alone drives trigger-level
        # detection, exactly like the single-spec path below does with its one
        # spec -- a SuperposedSignal has no single "kind", so _trigger_crossing
        # cannot be asked about the combination as a whole.
        primary = source.components[0]
        crossing = _trigger_crossing(primary, conn.trigger_level.get(channel, 0.0), _is_rising(conn.trigger_slope))
        if crossing is not None:
            t0 = crossing - (n / conn.sample_rate) / 2.0  # center of the SAMPLED span (may be shorter than the nominal window when MAX_POINTS clamps)
        else:
            t0 = count * window * _DRIFT_FRACTION  # untriggerable: free-run drift
        # Each component bumps its OWN seed independently by the same
        # count-based rule the single-spec path applies below, then the
        # per-acquisition components are recombined into a new SuperposedSignal
        # so synthesize_combined() sees the bumped seeds.
        per_acquisition_components = tuple(component if component.seed is None else replace(component, seed=component.seed + count) for component in source.components)
        per_acquisition = replace(source, components=per_acquisition_components)
        dut = source.dut  # NOT the getattr(conn._signals.get(channel), "dut", None) lookup below: for a bare SuperposedSignal that reads the same object, but a SuperposedSignal is never wrapped in a callable, so `source` (already resolved above) is the right place to read it from directly.
        if dut is None:
            return synthesize_combined(per_acquisition, conn.sample_rate, n, t0=t0)
        # See the single-spec DUT branch below for why a lead-in is rendered
        # and sliced off; the only difference here is synthesize_combined()
        # sums every component over that same extended window before filtering.
        warmup = dut.warmup_samples(conn.sample_rate)
        extended = synthesize_combined(per_acquisition, conn.sample_rate, n + warmup, t0=t0 - warmup / conn.sample_rate)
        return dut.apply(extended, conn.sample_rate)[warmup:]

    spec = spec_for(conn, channel)
    crossing = _trigger_crossing(spec, conn.trigger_level.get(channel, 0.0), _is_rising(conn.trigger_slope))
    if crossing is not None:
        t0 = crossing - (n / conn.sample_rate) / 2.0  # center of the SAMPLED span (may be shorter than the nominal window when MAX_POINTS clamps)
    else:
        t0 = count * window * _DRIFT_FRACTION  # untriggerable: free-run drift
    per_acquisition = spec if spec.seed is None else replace(spec, seed=spec.seed + count)
    dut = getattr(conn._signals.get(channel), "dut", None)
    if dut is None:
        return synthesize(per_acquisition, conn.sample_rate, n, t0=t0)
    # A DUT filter is STATEFUL, unlike every generator in signal_synth. Filtering
    # the bare capture would start from y=0 and put a settling transient at the
    # head of every acquisition, so render a lead-in BEFORE t0, filter across the
    # whole extended window, then slice the lead-in off -- the same fix, for the
    # same reason, as the ringing impairment's pre-t0 window (signal_synth.py:381).
    #
    # Note the extended t0 is computed as a subtraction rather than by shifting
    # the index range the way the ringing path does, so the sample at index
    # `warmup` can land a few ULP from `t0`. That is deliberate here: the output
    # is low-pass filtered and then quantized. The relevant grid is the FINER of
    # the two this function feeds -- not the int8 path's 25 codes/div (~0.04 V at
    # 1 V/div) but the modern dialect's WORD path at 6400 codes/div
    # (siglent.py's _MODERN_CODE_PER_DIV_WORD), i.e. 0.15625 mV/LSB. A
    # sub-femtosecond timebase difference is still many orders of magnitude below
    # even that. The lead-in's DEPTH is sized against the same WORD grid rather
    # than int8 -- see dut._WARMUP_TIME_CONSTANTS for the measured numbers.
    warmup = dut.warmup_samples(conn.sample_rate)
    extended = synthesize(per_acquisition, conn.sample_rate, n + warmup, t0=t0 - warmup / conn.sample_rate)
    return dut.apply(extended, conn.sample_rate)[warmup:]


def payload_for(conn: "MockConnection", channel: int, *, include_offset: bool) -> bytes:
    """int8 code bytes for a channel: explicit payload if given, else synthesized."""
    explicit = conn._waveform_payloads.get(channel)
    if explicit is not None:
        return explicit
    volts = raw_volts(conn, channel)
    vdiv = conn._voltage_scales.get(channel, 1.0)
    voffset = conn._voltage_offsets.get(channel, 0.0) if include_offset else 0.0
    codes = np.clip(np.rint((volts + voffset) * CODES_PER_DIV / vdiv), -CODE_LIMIT, CODE_LIMIT)
    return codes.astype(np.int8).tobytes()
