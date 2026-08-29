"""State-coupled mock waveform synthesis: all vendor personalities, trigger alignment, and server mock sessions."""

from dataclasses import replace

import numpy as np
import pytest

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec, SuperposedSignal, synthesize_combined

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


def test_trigger_centered_even_when_point_cap_clamps():
    # TDIV 10 ms/div at 1 MSa/s wants 140k points; MAX_POINTS clamps to 14k,
    # so the sampled span (14 ms) is shorter than the nominal window (140 ms).
    # The trigger edge must sit at the center of the SAMPLED span.
    scope, _ = _scope(signals={1: SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0, seed=1)})
    scope.write("TDIV 1e-2")
    scope.write("C1:TRLV 0.0")
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    n = len(data.voltage)
    assert n == 14_000
    assert data.voltage[n // 2] == pytest.approx(0.0, abs=0.05)
    assert data.voltage[n // 2 + 20] > data.voltage[n // 2 - 20]


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


def test_server_mock_connection_synthesizes():
    from scpi_control.server.sessions import _make_mock_connection

    conn = _make_mock_connection(None)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) >= 1_000  # real trace, not the old 256-byte ramp
    assert np.ptp(data.voltage) > 1.0  # default CH1 square, ~2 Vpp


@pytest.mark.parametrize(
    "spec",
    [
        SignalSpec(kind="pulse", frequency=1_000.0, amplitude=1.0, pulse_width=2e-4, edge_time=1e-5),
        SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, tau=1e-4),
        SignalSpec(kind="multitone", frequency=1_000.0, amplitude=1.0),
        SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=5_000.0, sweep_time=1e-3),
    ],
    ids=["pulse", "exponential", "multitone", "chirp"],
)
def test_new_kinds_capture_through_a_mock_scope(spec):
    scope, _ = _scope(signals={1: spec})
    data = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert len(data.voltage) == 14_000
    # int8 codes at 25 per division against the mock's 1 V/div default: a 1 V
    # amplitude signal survives the volts -> codes -> volts round trip.
    assert np.max(data.voltage) == pytest.approx(1.0, abs=0.1)
    assert np.min(data.voltage) == pytest.approx(-1.0, abs=0.1)


def test_periodic_kinds_are_trigger_aligned_and_chirp_free_runs():
    """The one behavioural consequence of the PERIODIC_KINDS classification:
    a kind with a stable period gets the same trigger-aligned t0 on every
    acquisition, so two captures of a noiseless signal are identical, while
    chirp free-runs and drifts between acquisitions."""
    scope, _ = _scope(signals={1: SignalSpec(kind="pulse", frequency=1_000.0, pulse_width=2e-4, edge_time=1e-5)})
    first = scope.get_waveform(1, provenance=False)
    second = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    np.testing.assert_array_equal(first.voltage, second.voltage)

    scope, _ = _scope(signals={1: SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=5_000.0, sweep_time=1e-3)})
    first = scope.get_waveform(1, provenance=False)
    second = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert not np.array_equal(first.voltage, second.voltage)


def test_new_kinds_still_couple_to_volts_per_division():
    scope, _ = _scope(signals={1: SignalSpec(kind="multitone", frequency=1_000.0, amplitude=1.0)})
    scope.write("C1:VDIV 2.0")
    coarse = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    # Wider V/div, same signal: still ~1 V peak in volts, but the mock had to
    # encode it at half the code density -- so the trace is coarser, not smaller.
    assert np.max(coarse.voltage) == pytest.approx(1.0, abs=0.15)


@pytest.mark.parametrize(
    "impairment",
    [
        {"ringing_frequency": 50_000.0},
        {"drift_amplitude": 0.5, "drift_frequency": 200.0},
        {"glitch_rate": 50_000.0, "glitch_amplitude": 2.0, "seed": 3},
    ],
    ids=["ringing", "drift", "glitch"],
)
def test_trigger_search_ignores_the_impairments(impairment):
    """The search is for the IDEAL crossing, so every impairment is stripped from
    it -- an impairment that moved the crossing would move t0 with it, and the
    alignment would track the impairment settings rather than the signal's own
    edge. Discriminating: with the impairments left in (noise and seed alone
    stripped, as before), this exponential's ideal 68.85 us crossing moves to
    66.41 us with ringing, 64.70 us with drift and 10.25 us with glitches."""
    from scpi_control.connection.mock.synth import _trigger_crossing

    clean = SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, tau=1e-4, noise_rms=0.0)
    impaired = replace(clean, **impairment)
    assert _trigger_crossing(impaired, 0.0, True) == _trigger_crossing(clean, 0.0, True)


def test_a_ringing_trigger_aligned_kind_still_displays_stably():
    """The behavioural half: a trigger-aligned kind with ringing switched on
    still lands on the same t0 every acquisition, so the trace does not walk."""
    spec = SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, tau=1e-4, noise_rms=0.0, ringing_frequency=50_000.0)
    scope, _ = _scope(signals={1: spec})
    scope.write("C1:TRLV 0.0")
    first = scope.get_waveform(1, provenance=False)
    second = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    np.testing.assert_array_equal(first.voltage, second.voltage)


def test_superposed_signal_is_triggerable_via_its_primary_component():
    """The primary (first) component alone drives trigger-crossing detection --
    a noiseless periodic primary still gives a stable, repeatable capture even
    with a second, unrelated component summed in, exactly like a plain
    SignalSpec's own trigger-stability test above."""
    signal = SuperposedSignal(
        (
            SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0),
            SignalSpec(kind="dc", offset=0.1, noise_rms=0.0),
        )
    )
    scope, _ = _scope(signals={1: signal})
    scope.write("C1:TRLV 0.0")
    first = scope.get_waveform(1, provenance=False)
    second = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    np.testing.assert_array_equal(first.voltage, second.voltage)


def test_superposed_signal_free_runs_when_the_primary_is_unattainable():
    """The mirror image of the trigger test above: an unattainable trigger
    level on the primary component free-runs the combined signal, same as a
    plain SignalSpec (test_unattainable_level_free_runs)."""
    signal = SuperposedSignal(
        (
            SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0),
            SignalSpec(kind="dc", offset=0.1, noise_rms=0.0),
        )
    )
    scope, _ = _scope(signals={1: signal})
    scope.write("C1:TRLV 5.0")
    a = scope.get_waveform(1, provenance=False)
    b = scope.get_waveform(1, provenance=False)
    scope.disconnect()
    assert not np.array_equal(a.voltage, b.voltage)


def test_superposed_components_seed_independently_per_acquisition():
    """Mirrors test_seeded_sequences_reproduce_across_connections: each
    component's own seed must advance by the acquisition count independently,
    so two connections built from the same SuperposedSignal reproduce the same
    sequence, and consecutive acquisitions on one connection differ."""
    signals = {
        1: SuperposedSignal(
            (
                SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0, seed=11),
                SignalSpec(kind="noise", amplitude=0.05, seed=21),
            )
        )
    }
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


def test_superposed_signal_dut_filters_the_summed_signal():
    """A SuperposedSignal's dut is applied to the SUMMED signal (raw_volts'
    combined branch), not to each component separately -- checked at
    raw_volts's float64 precision (mirrors test_trigger_search_ignores_the_
    impairments' style of importing internals directly), independently
    reconstructing the expected sum-then-filter result via the public
    synthesize_combined()/RCLowPass API rather than duplicating raw_volts'
    own arithmetic."""
    from scpi_control.connection.mock.synth import _trigger_crossing, raw_volts
    from scpi_control.dut import RCLowPass

    tone = SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.0)
    dc = SignalSpec(kind="dc", offset=0.3, noise_rms=0.0)
    dut = RCLowPass(cutoff_hz=5_000.0)
    signal = SuperposedSignal((tone, dc), dut=dut)

    scope, conn = _scope(signals={1: signal})
    scope.write("C1:TRLV 0.0")
    actual = raw_volts(conn, 1)
    scope.disconnect()

    n = len(actual)
    crossing = _trigger_crossing(tone, 0.0, True)  # primary component drives the trigger search
    t0 = crossing - (n / conn.sample_rate) / 2.0
    warmup = dut.warmup_samples(conn.sample_rate)
    extended = synthesize_combined(signal, conn.sample_rate, n + warmup, t0=t0 - warmup / conn.sample_rate)
    expected = dut.apply(extended, conn.sample_rate)[warmup:]

    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-9)


def test_superposed_signal_dut_visibly_smooths_a_square_component():
    """Sanity check that the DUT branch above is actually exercised (not just
    mathematically vacuous): with a DUT, a square-wave component's sharp edges
    are visibly rounded, mirroring test_loopback_capture.py's
    test_the_dut_visibly_rounds_a_square_wave."""
    from scpi_control.connection.mock.synth import raw_volts
    from scpi_control.dut import RCLowPass

    components = (SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, noise_rms=0.0), SignalSpec(kind="dc", offset=0.3, noise_rms=0.0))
    sharp_scope, sharp_conn = _scope(signals={1: SuperposedSignal(components)})
    sharp_scope.write("C1:TRLV 0.0")
    unfiltered = raw_volts(sharp_conn, 1)
    sharp_scope.disconnect()

    soft_scope, soft_conn = _scope(signals={1: SuperposedSignal(components, dut=RCLowPass(cutoff_hz=2_000.0))})
    soft_scope.write("C1:TRLV 0.0")
    filtered = raw_volts(soft_conn, 1)
    soft_scope.disconnect()

    assert np.max(np.abs(np.diff(filtered))) < np.max(np.abs(np.diff(unfiltered)))


def test_spec_for_rejects_a_superposed_signal():
    """spec_for()'s contract is a plain SignalSpec -- it was never taught about
    SuperposedSignal, which raw_volts' own isinstance check keeps upstream of
    every real call site. Calling spec_for() directly on a channel configured
    with a SuperposedSignal must fail loudly (InvalidParameterError) rather
    than silently handing back a SuperposedSignal where a SignalSpec was
    promised."""
    from scpi_control import exceptions
    from scpi_control.connection.mock.synth import spec_for

    signal = SuperposedSignal(
        (
            SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0),
            SignalSpec(kind="dc", offset=0.1),
        )
    )
    _, conn = _scope(signals={1: signal})
    with pytest.raises(exceptions.InvalidParameterError):
        spec_for(conn, 1)
