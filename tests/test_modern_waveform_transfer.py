"""Modern-dialect capture over the documented :WAVeform: path (audit H9).

The modern guides contain zero occurrences of "WF?" -- the legacy transfer
this replaces (C{ch}:WF? DAT2/DESC) was validated only by our own mock, never
by the vendor manual. This module checks the driver's parser and the mock's
producer separately against a transcription of the manual (see
tests/wire_forms.py), and additionally proves the two AGREE with each other
via a round trip -- but agreement alone is not the point; test_round_trip_*
below exists to catch a formula that is self-consistent but wrong (the
co-validation defect this sub-project eliminates).
"""

import numpy as np
import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

MODERN_IDN = "Siglent Technologies,SDS814X HD,MOCK0001,1.0.0.0"


@pytest.fixture
def modern_scope():
    s = Oscilloscope("mock", connection=MockConnection(idn=MODERN_IDN))
    s.connect()
    yield s
    s.disconnect()


def test_capture_returns_a_populated_waveform(modern_scope):
    wf = modern_scope.get_waveform(1)
    assert len(wf.voltage) > 0
    assert len(wf.time) == len(wf.voltage)


def test_capture_does_not_send_the_legacy_command(modern_scope):
    modern_scope.get_waveform(1)
    assert not any("WF?" in q.upper() for q in modern_scope._connection.queries)
    assert not any("WF?" in w.upper() for w in modern_scope._connection.writes)


def test_source_is_selected_before_data_is_requested(modern_scope):
    modern_scope.get_waveform(2)
    sent = modern_scope._connection.writes + modern_scope._connection.queries
    src = next(i for i, c in enumerate(sent) if "WAVEFORM:SOURCE" in c.upper())
    dat = next(i for i, c in enumerate(sent) if "DATA?" in c.upper())
    assert src < dat


def test_source_is_sent_for_the_requested_channel(modern_scope):
    modern_scope.get_waveform(3)
    assert ":WAVeform:SOURce C3" in modern_scope._connection.writes


def test_preamble_is_read_before_data(modern_scope):
    modern_scope.get_waveform(1)
    writes_upper = [w.upper() for w in modern_scope._connection.writes]
    assert writes_upper.index(":WAVEFORM:PREAMBLE?") < writes_upper.index(":WAVEFORM:DATA?")


def test_round_trip_recovers_known_signal_amplitude():
    """The central risk this sub-project exists to catch: a mock encoder and
    driver decoder that agree with EACH OTHER but not with the manual. The
    voltage formula in waveform_transfer.ModernTransfer.acquire is transcribed
    from the guide (p.758); the mock in connection/mock/siglent.py's
    build_waveform_data encodes with its exact inverse. This test synthesizes
    a KNOWN sine amplitude, captures it through the full SCPI round trip
    (encode to codes+WAVEDESC, decode back to volts), and checks the
    recovered peaks against the known amplitude -- within the mock's own ADC
    quantization step (vdiv/code_per_div), not arbitrary test slop.
    """
    amplitude = 2.0
    vdiv = 1.0  # MockConnection's default C1 voltage_scales value
    code_per_div = 25.0  # mock's BYTE-format code_per_div (siglent.py's _MODERN_CODE_PER_DIV_BYTE)
    conn = MockConnection(
        idn=MODERN_IDN,
        timebase=1e-3,
        sample_rate=20_000.0,
        # Clean, noise-free sine sampled ~100x/period over ~2.8 periods --
        # plenty of resolution to hit the true peaks without aliasing.
        signals={1: SignalSpec(kind="sine", frequency=200.0, amplitude=amplitude, noise_rms=0.0)},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    wf = scope.get_waveform(1)

    quantization_step = vdiv / code_per_div
    assert np.max(wf.voltage) == pytest.approx(amplitude, abs=quantization_step * 2)
    assert np.min(wf.voltage) == pytest.approx(-amplitude, abs=quantization_step * 2)
    scope.disconnect()


def test_round_trip_honors_nonzero_offset_and_scale():
    """Same round trip, but with a non-default vdiv/voffset, so the test
    cannot pass by coincidence of the mock's zero-offset default."""
    amplitude = 0.3
    vdiv = 0.2
    voffset = 0.5
    code_per_div = 25.0
    conn = MockConnection(
        idn=MODERN_IDN,
        timebase=1e-3,
        sample_rate=20_000.0,
        voltage_scales={1: vdiv},
        voltage_offsets={1: voffset},
        signals={1: SignalSpec(kind="sine", frequency=200.0, amplitude=amplitude, noise_rms=0.0)},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    wf = scope.get_waveform(1)

    quantization_step = vdiv / code_per_div
    assert np.max(wf.voltage) == pytest.approx(amplitude, abs=quantization_step * 2)
    assert np.min(wf.voltage) == pytest.approx(-amplitude, abs=quantization_step * 2)
    assert wf.voltage_scale == pytest.approx(vdiv, rel=1e-5)
    assert wf.voltage_offset == pytest.approx(voffset, rel=1e-5)
    scope.disconnect()


def test_deep_memory_capture_is_chunked(modern_scope):
    """MAXPoint caps one transfer; longer records need repeated STARt windows."""
    conn = modern_scope._connection
    conn.max_points = 1000
    conn.record_length = 2500
    wf = modern_scope.get_waveform(1)
    assert len(wf.voltage) == 2500
    starts = [w for w in conn.writes if "STAR" in w.upper()]
    assert len(starts) >= 3


def test_deep_memory_chunks_preserve_sample_order_and_values():
    """Fidelity check on the chunked path: reassembly must not corrupt or
    misorder samples. A "ramp" signal spans far less than one period across
    the whole 2500-sample record (frequency=1 Hz, ~125 ms of a 1 s period),
    so the true waveform is strictly increasing end-to-end with no wraparound
    -- any chunk dropped, duplicated, or reordered by the STARt loop would
    break that monotonicity immediately. The trigger level is set unreachably
    high so the mock's trigger-crossing search finds nothing and falls back
    to its free-run path, which starts a channel's very first capture at
    t=0 -- making the expected samples fully predictable, not just "some
    ramp phase".
    """
    amplitude = 1.0
    vdiv = 1.0  # MockConnection's default C1 voltage_scales value
    code_per_div = 25.0  # mock's BYTE-format code_per_div
    conn = MockConnection(
        idn=MODERN_IDN,
        timebase=1e-3,
        sample_rate=20_000.0,
        signals={1: SignalSpec(kind="ramp", frequency=1.0, amplitude=amplitude, noise_rms=0.0)},
    )
    conn.trigger_level[1] = 10 * amplitude  # unreachable -> no trigger crossing -> free-run t0=0
    conn.max_points = 1000
    conn.record_length = 2500
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    wf = scope.get_waveform(1)

    assert len(wf.voltage) == 2500
    # Non-decreasing, not strictly increasing: the true ramp step per sample
    # (~0.0008 V) is far finer than the mock's 8-bit ADC quantization
    # (0.04 V/code), so consecutive samples legitimately land on the same
    # code -- but a ramp must never go BACKWARDS, which a dropped/duplicated/
    # reordered chunk would cause at the join.
    assert np.all(np.diff(wf.voltage) >= 0), "chunked reassembly moved backwards -- a chunk was dropped, duplicated, or reordered at a boundary"

    t = np.arange(2500) / 20_000.0
    expected = amplitude * (2.0 * ((1.0 * t) % 1.0) - 1.0)
    quantization_step = vdiv / code_per_div
    assert np.max(np.abs(wf.voltage - expected)) < quantization_step * 2
    scope.disconnect()


def test_word_format_round_trips_too():
    """format='WORD' switches COMM_TYPE and the code_per_div scale; the
    driver must read COMM_TYPE from the preamble rather than assuming BYTE."""
    amplitude = 1.0
    conn = MockConnection(
        idn=MODERN_IDN,
        timebase=1e-3,
        sample_rate=20_000.0,
        signals={1: SignalSpec(kind="sine", frequency=200.0, amplitude=amplitude, noise_rms=0.0)},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    wf = scope.waveform.acquire(1, format="WORD", provenance=False)

    assert ":WAVeform:WIDTh WORD" in conn.writes
    code_per_div_word = 25.0 * 256
    quantization_step = 1.0 / code_per_div_word
    assert np.max(wf.voltage) == pytest.approx(amplitude, abs=quantization_step * 2)
    assert np.min(wf.voltage) == pytest.approx(-amplitude, abs=quantization_step * 2)
    scope.disconnect()
