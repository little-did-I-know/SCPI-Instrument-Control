"""A channel's signal may be computed fresh at every acquisition.

`signals={1: SignalSpec(...)}` pins a channel to one static signal. Allowing a
callable is what lets a LIVE source -- an AwgLoopback reading a mock AWG's state
-- change what the scope captures between captures. Everything downstream keeps
receiving a plain SignalSpec and never learns the difference.
"""

import numpy as np
import pytest

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


def _scope(**kwargs):
    # Channel 2 is ENABLED here, unlike the helper in test_mock_synthesis.py:
    # one test below captures it to prove an unlisted channel still falls back
    # to its built-in default signal.
    conn = MockConnection(
        "mock",
        idn=LEGACY_IDN,
        channel_states={1: True, 2: True, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
        **kwargs,
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def test_a_callable_signal_is_re_read_on_every_acquisition():
    """The whole point: the source is consulted per capture, not once."""
    box = {"spec": SignalSpec(kind="dc", offset=1.0)}
    scope, _ = _scope(signals={1: lambda: box["spec"]})
    try:
        first = scope.get_waveform(1, provenance=False)
        box["spec"] = SignalSpec(kind="dc", offset=-1.0)
        second = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    assert np.mean(first.voltage) == pytest.approx(1.0, abs=0.1)
    assert np.mean(second.voltage) == pytest.approx(-1.0, abs=0.1)


def test_a_static_spec_still_works_unchanged():
    """The non-breaking guarantee: a SignalSpec is not callable, so the new
    branch never fires for an existing caller."""
    scope, _ = _scope(signals={1: SignalSpec(kind="dc", offset=0.5)})
    try:
        data = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    assert np.mean(data.voltage) == pytest.approx(0.5, abs=0.1)


def test_a_channel_with_no_entry_still_gets_its_default():
    scope, _ = _scope(signals={1: SignalSpec(kind="dc", offset=0.5)})
    try:
        data = scope.get_waveform(2, provenance=False)
    finally:
        scope.disconnect()
    assert np.ptp(data.voltage) > 0.1, "channel 2 falls back to its built-in default signal"
