"""State-coupled mock waveform synthesis (Siglent dialects)."""

import numpy as np
import pytest

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


def _scope(idn=LEGACY_IDN, **kwargs):
    conn = MockConnection(
        "mock",
        idn=idn,
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
        **kwargs,
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def _measured_frequency(data):
    v = data.voltage - np.mean(data.voltage)
    spectrum = np.abs(np.fft.rfft(v))
    return np.fft.rfftfreq(len(v), 1.0 / data.sample_rate)[np.argmax(spectrum)]


@pytest.mark.parametrize("idn", [LEGACY_IDN, MODERN_IDN])
def test_seeded_square_round_trip(idn):
    scope, _ = _scope(idn, signals={1: SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, seed=7)})
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    # 14 divisions x 1 ms/div at 1 MSa/s
    assert len(data.voltage) == 14_000
    assert np.max(data.voltage) == pytest.approx(1.0, abs=0.1)
    assert np.min(data.voltage) == pytest.approx(-1.0, abs=0.1)
    assert _measured_frequency(data) == pytest.approx(1_000.0, rel=0.05)


def test_default_specs_without_signals_kwarg():
    scope, _ = _scope()
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) == 14_000
    assert np.ptp(data.voltage) > 1.5  # default CH1: 2 Vpp square (plus small noise)


def test_timebase_coupling():
    scope, _ = _scope(signals={1: SignalSpec(seed=1)})
    scope.write("TDIV 1e-4")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) == 1_400  # 14 divisions x 0.1 ms/div at 1 MSa/s


def test_overrange_clips_at_full_scale():
    # 2 Vpp signal on a 0.1 V/div scale: full scale is 127 codes = 0.508 V
    scope, _ = _scope(signals={1: SignalSpec(kind="square", amplitude=1.0, seed=2)})
    scope.write("C1:VDIV 0.1")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert np.max(data.voltage) == pytest.approx(127 * 0.1 / 25, abs=0.01)
    assert np.min(data.voltage) == pytest.approx(-127 * 0.1 / 25, abs=0.01)


def test_vertical_offset_round_trips():
    scope, _ = _scope(signals={1: SignalSpec(kind="dc", offset=0.5, seed=3)})
    scope.write("C1:OFST 0.2")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    # Converter subtracts the channel offset; synthesis adds it back, so the
    # recovered trace is the signal itself.
    # One int8 code = 40 mV at 1 V/div, so quantization alone can shift the
    # recovered level by up to ~20 mV; allow for it.
    assert np.mean(data.voltage) == pytest.approx(0.5, abs=0.03)


def test_explicit_payload_precedence():
    scope, _ = _scope(waveform_payloads={1: bytes([0, 25, 50, 75])})
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    np.testing.assert_allclose(data.voltage, [0.0, 1.0, 2.0, 3.0])


def test_unseeded_noise_rerolls_each_capture():
    # The default CH1 spec is trigger-aligned (stable t0), so consecutive
    # captures differ ONLY because unseeded noise (noise_rms=0.01) re-rolls
    # each acquisition. Free-run drift is covered separately by
    # test_unattainable_level_free_runs.
    scope, _ = _scope()
    a = scope.get_waveform(1, provenance=False)
    b = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert not np.array_equal(a.voltage, b.voltage)


def test_seeded_sequences_reproduce_across_connections():
    signals = {1: SignalSpec(kind="sine", noise_rms=0.05, seed=11)}
    scope1, _ = _scope(signals=signals)
    first_a = scope1.get_waveform(1, provenance=False)
    second_a = scope1.get_waveform(1, provenance=False)
    scope1.disconnect()
    scope2, _ = _scope(signals=signals)
    first_b = scope2.get_waveform(1, provenance=False)
    second_b = scope2.get_waveform(1, provenance=False)
    scope2.disconnect()
    np.testing.assert_array_equal(first_a.voltage, first_b.voltage)
    np.testing.assert_array_equal(second_a.voltage, second_b.voltage)
    assert not np.array_equal(first_a.voltage, second_a.voltage)  # seed advances per acquisition


TEK_IDN = "TEKTRONIX,MSO24,MOCK0100,CF:91.1CT FV:1.28"
LECROY_IDN = "LECROY,WAVESURFER3024Z,MOCK0200,8.5.0"


@pytest.mark.parametrize("idn", [TEK_IDN, LECROY_IDN])
def test_vendor_round_trip(idn):
    scope, _ = _scope(idn, signals={1: SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, seed=7)})
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) == 14_000
    assert np.max(data.voltage) == pytest.approx(1.0, abs=0.1)
    assert np.min(data.voltage) == pytest.approx(-1.0, abs=0.1)
    assert _measured_frequency(data) == pytest.approx(1_000.0, rel=0.05)


def test_tek_nr_pt_matches_curve_length():
    scope, conn = _scope(TEK_IDN, signals={1: SignalSpec(seed=1)})
    scope.write("HORIZONTAL:SCALE 1.0E-4")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) == 1_400  # preamble NR_Pt and CURVe? payload agree


def test_lecroy_timebase_coupling():
    scope, _ = _scope(LECROY_IDN, signals={1: SignalSpec(seed=1)})
    scope.write("TDIV 1e-4")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) == 1_400


def test_vendor_explicit_payload_precedence():
    scope, _ = _scope(TEK_IDN, waveform_payloads={1: bytes([0, 25, 50, 75])})
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    np.testing.assert_allclose(data.voltage, [0.0, 1.0, 2.0, 3.0])


def test_trigger_aligns_rising_edge_at_center():
    scope, _ = _scope(signals={1: SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0, seed=1)})
    scope.write("C1:TRLV 0.0")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    n = len(data.voltage)
    center = data.voltage[n // 2]
    assert center == pytest.approx(0.0, abs=0.05)  # crossing sits at window center
    assert data.voltage[n // 2 + 20] > data.voltage[n // 2 - 20]  # rising through it


def test_trigger_falling_slope():
    scope, _ = _scope(signals={1: SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0, seed=1)})
    scope.write("C1:TRLV 0.0")
    scope.write("C1:TRSL NEG")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    n = len(data.voltage)
    assert data.voltage[n // 2] == pytest.approx(0.0, abs=0.05)
    assert data.voltage[n // 2 + 20] < data.voltage[n // 2 - 20]  # falling through it


def test_triggered_display_is_stable():
    # A real triggered scope shows a stable trace: consecutive noise-free
    # captures are identical when the trigger aligns them.
    scope, _ = _scope(signals={1: SignalSpec(kind="sine", frequency=1_000.0, noise_rms=0.0)})
    scope.write("C1:TRLV 0.0")
    a = scope.get_waveform(1, provenance=False)
    b = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    np.testing.assert_array_equal(a.voltage, b.voltage)


def test_unattainable_level_free_runs():
    # Level above the signal: no alignment, so noise-free captures drift.
    scope, _ = _scope(signals={1: SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0)})
    scope.write("C1:TRLV 5.0")
    a = scope.get_waveform(1, provenance=False)
    b = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert not np.array_equal(a.voltage, b.voltage)
