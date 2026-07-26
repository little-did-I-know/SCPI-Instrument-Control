"""A patch cable from a mock AWG channel to a mock scope channel.

The AWG and the scope are separate MockConnection instances, so nothing in the
scope's synthesis can see the AWG's state. This object closes that gap: it is a
callable suitable for `MockConnection(signals={...})`, and it reads the AWG's
live channel state every time it is called, so a `C1:BSWV` write between two
captures changes the second one.
"""

import logging
import math
from typing import Any, Dict, Optional

from scpi_control.signal_synth import SignalSpec

logger = logging.getLogger(__name__)

# Waveform names come from awg_output.py:65. RAMP is absent because it maps to
# two kinds depending on symmetry, and ARB is absent because the mock stores no
# arbitrary sample data; both are handled explicitly below.
_FUNCTION_KINDS = {
    "SINE": "sine",
    "SQUARE": "square",
    "NOISE": "noise",
    "DC": "dc",
    "PULSE": "pulse",
}

# Percent either side of 50 that still counts as a triangle rather than a sawtooth.
_RAMP_SYMMETRY_TOLERANCE = 1.0

# SignalSpec requires 0 < duty < 1; an AWG happily accepts 0 and 100.
_MIN_DUTY = 0.01
_MAX_DUTY = 0.99

# An output that is off reads like a disconnected input: flat, not a zero-amplitude
# waveform at some frequency.
_OUTPUT_OFF = SignalSpec(kind="dc", offset=0.0)


class AwgLoopback:
    """Reads a mock AWG channel and yields the SignalSpec a scope would see.

    Args:
        awg_connection: A MockConnection built with ``awg_mode=True``.
        awg_channel: Which of its channels to patch from.
        dut: Optional device model (e.g. ``RCLowPass``) sitting between the two
            instruments. Stored here rather than on the scope connection because
            a DUT physically sits between them -- this object models the cable
            run. It is APPLIED in connection/mock/synth.py's raw_volts, which is
            the only layer that knows the sample rate and can render the filter's
            lead-in.
    """

    def __init__(self, awg_connection: Any, awg_channel: int = 1, dut: Optional[Any] = None) -> None:
        self.awg_connection = awg_connection
        self.awg_channel = awg_channel
        self.dut = dut
        self._warned_about_arb = False

    def __call__(self) -> SignalSpec:
        state = getattr(self.awg_connection, "awg_channels", {}).get(self.awg_channel)
        if not state or not state.get("enabled", False):
            return _OUTPUT_OFF
        return self._spec_from(state)

    def _spec_from(self, state: Dict[str, Any]) -> SignalSpec:
        function = str(state.get("function", "SINE")).upper()
        frequency = float(state.get("frequency", 1000.0)) or 1000.0
        # SDG `AMP` is peak-to-peak (PG02-E05B p.29); SignalSpec.amplitude is peak.
        amplitude = float(state.get("amplitude", 1.0)) / 2.0
        offset = float(state.get("offset", 0.0))
        phase = math.radians(float(state.get("phase", 0.0)))
        duty = min(_MAX_DUTY, max(_MIN_DUTY, float(state.get("pulse_duty", 50.0)) / 100.0))

        if function == "RAMP":
            symmetry = float(state.get("ramp_symmetry", 50.0))
            kind = "triangle" if abs(symmetry - 50.0) <= _RAMP_SYMMETRY_TOLERANCE else "ramp"
        elif function == "ARB":
            if not self._warned_about_arb:
                logger.warning("AwgLoopback: the mock stores no ARB sample data, so an ARB waveform is captured as a sine")
                self._warned_about_arb = True
            kind = "sine"
        else:
            kind = _FUNCTION_KINDS.get(function, "sine")

        common = {"frequency": frequency, "amplitude": amplitude, "offset": offset, "phase": phase}
        if kind == "square":
            return SignalSpec(kind=kind, duty=duty, **common)
        if kind == "pulse":
            period = 1.0 / frequency
            # edge_time shrinks with the period: SignalSpec's 10 us default is
            # LONGER than the period above 100 kHz, and _validate then has no legal
            # pulse_width at all.
            edge_time = min(SignalSpec().edge_time, period / 10.0)
            # _validate requires pulse_width > edge_time and
            # pulse_width + edge_time <= period.
            width = min(period - edge_time, max(edge_time * 1.01, duty * period))
            return SignalSpec(kind=kind, pulse_width=width, edge_time=edge_time, **common)
        return SignalSpec(kind=kind, **common)
