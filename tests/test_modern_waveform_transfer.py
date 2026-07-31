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
    # BYTE carries the HIGH BYTE of the native code, so its effective scale is
    # _MODERN_CODE_PER_DIV_NATIVE / 256 = 30 codes/div (hardware-measured).
    code_per_div = 7680.0 / 256
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
    code_per_div = 7680.0 / 256  # BYTE = high byte of the native code
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
    code_per_div = 7680.0 / 256  # BYTE = high byte of the native code
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
    code_per_div_word = 7680.0  # WORD uses the native scale as reported
    quantization_step = 1.0 / code_per_div_word
    assert np.max(wf.voltage) == pytest.approx(amplitude, abs=quantization_step * 2)
    assert np.min(wf.voltage) == pytest.approx(-amplitude, abs=quantization_step * 2)
    scope.disconnect()


def _preamble_under(conn, width):
    """What the mock would answer :WAVeform:PREamble? with at this width."""
    from scpi_control.connection.mock.siglent import build_waveform_preamble
    from scpi_control.waveform_transfer import parse_ieee_block, parse_modern_wavedesc

    conn.waveform_width = width
    conn.waveform_source = "C1"
    payload = parse_ieee_block(build_waveform_preamble(conn), np.uint8).tobytes()
    return parse_modern_wavedesc(payload)


def test_one_code_per_div_serves_both_widths_on_a_high_resolution_front_end():
    """MEASURED on the real SDS824X HD (fw 3.8.12.1.1.3.6), 2026-07-30:
    the preamble reports Adc_bit=16 and code_per_div=7680 -- the SAME 7680
    under :WAVeform:WIDTh BYTE and under WORD. BYTE does not get its own
    smaller code_per_div; the instrument sends the HIGH BYTE of the native
    code and leaves the scale field alone.

    The mock used to report 25.0 for BYTE and 6400.0 for WORD, i.e. it scaled
    the field by 256 across widths where the instrument does not. Because the
    mock's encoder and the driver's decoder both used that same wrong number
    they round-tripped perfectly, which is precisely the self-consistent-but-
    wrong defect this module's docstring says it exists to catch.
    """
    conn = MockConnection(idn=MODERN_IDN, sample_rate=20_000.0, timebase=1e-3)

    byte_meta = _preamble_under(conn, "BYTE")
    word_meta = _preamble_under(conn, "WORD")

    assert byte_meta["adc_bit"] > 8, "an HD front end reports more than 8 ADC bits"
    assert byte_meta["code_per_div"] == word_meta["code_per_div"], "the instrument reports one code_per_div regardless of transfer width"
    assert byte_meta["comm_type"] == 0 and word_meta["comm_type"] == 1


def test_a_byte_read_is_not_scaled_off_by_the_word_factor():
    """THE 256x guard. With one code_per_div serving both widths, a decoder
    that divides BYTE codes by the native (16-bit) code_per_div returns volts
    256x too small. On the instrument that showed up as a 3.075 Vpp signal
    read back as 0.0119792 Vpp, with the scope's own :MEASure MEAN
    (1.45474 V) agreeing with the WORD read (1.45602 V) and not the BYTE one.

    Both widths must recover the same amplitude, to within BYTE's coarser
    quantization -- that is the whole claim.
    """
    amplitude = 2.0
    conn = MockConnection(
        idn=MODERN_IDN,
        timebase=1e-3,
        sample_rate=20_000.0,
        signals={1: SignalSpec(kind="sine", frequency=200.0, amplitude=amplitude, noise_rms=0.0)},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    wf_byte = scope.waveform.acquire(1, format="BYTE", provenance=False)
    wf_word = scope.waveform.acquire(1, format="WORD", provenance=False)

    vdiv = 1.0
    byte_step = vdiv / (7680.0 / 256)  # BYTE carries the high byte: 30 codes/div
    assert np.max(wf_byte.voltage) == pytest.approx(amplitude, abs=byte_step * 2)
    assert np.max(wf_byte.voltage) == pytest.approx(np.max(wf_word.voltage), abs=byte_step * 2)
    assert np.min(wf_byte.voltage) == pytest.approx(np.min(wf_word.voltage), abs=byte_step * 2)
    scope.disconnect()


def test_the_parser_accepts_the_block_shapes_the_instrument_actually_sends():
    """Byte shapes captured off a real SDS824X HD (fw 3.8.12.1.1.3.6),
    2026-07-30, at ACQ:POINts=50000:

      :WAVeform:PREamble? -> b'#9000000346WAVEDESC...' + b'\n'
      :WAVeform:DATA?     -> b'#550000' + 50000 bytes + b'\n\n'
      empty DATA?         -> b'C1:WF DAT2,#9000000000\n\n'

    Two things the guide does not say. DATA? uses the GENERAL IEEE-488.2 form
    with a variable digit count ("#5" for 50000 bytes), not the fixed
    "#9<9-digits>" of p.757's example -- which PREamble? does use. And every
    reply carries trailing newlines, DATA? two of them. The empty reply also
    arrives behind a legacy "C1:WF DAT2," response header, on the modern
    subsystem.

    parse_ieee_block already survives all of this (it scans for "#" and reads
    the declared length), but nothing pinned it, and the mock emitted none of
    it -- so the tolerance was accidental rather than guaranteed.
    """
    from scpi_control.waveform_transfer import parse_ieee_block

    payload = bytes(range(256)) * 4  # 1024 bytes
    variable_header = b"#4" + b"1024" + payload + b"\n\n"
    assert parse_ieee_block(variable_header, np.int8).size == 1024

    fixed_header = b"#9" + b"000001024" + payload + b"\n"
    assert parse_ieee_block(fixed_header, np.int8).size == 1024

    legacy_prefixed_empty = b"C1:WF DAT2,#9000000000\n\n"
    assert parse_ieee_block(legacy_prefixed_empty, np.int8).size == 0


class TestProbeAttenuationScaling:
    """Backend review 2026-07-31 High-1, measured on SDS824X HD fw 3.8.12.1.1.3.6:
    preamble VERTICAL_GAIN/VERTICAL_OFFSET are probe-FREE (BNC frame). At probe
    10x the display reads 20 V/div but the preamble still says gain=2.0. The
    driver must multiply by the probe ratio; the mock must keep the preamble
    probe-free. These two tests pin OPPOSITE sides of the wire so the pair
    cannot co-validate a shared wrong assumption."""

    def test_mock_preamble_gain_is_probe_free(self, modern_scope):
        # Wire-level pin of the hardware measurement: scale 20 V/div at probe
        # 10x -> preamble vertical_gain 2.0 (NOT 20.0).
        conn = modern_scope._connection
        modern_scope.channel1.probe_ratio = 10.0
        modern_scope.channel1.voltage_scale = 20.0

        meta = _preamble_under(conn, "BYTE")

        assert meta["vertical_gain"] == pytest.approx(2.0)

    def test_acquire_multiplies_by_probe_ratio(self):
        """Expectations adjusted from the brief's illustrative "* 10" form, as
        its own NOTE anticipates: the mock synthesizes codes against the
        DISPLAYED :CHANnel:SCALe/:OFFSet (unaffected by a probe-ratio-only
        change), so the correctly probe-compensated round trip recovers the
        SAME displayed volts at 10x as at 1x -- not 10x more of them. Without
        the driver's probe_ratio multiply, the BNC-frame preamble gain alone
        (scale/probe) decodes the 10x capture at 1/10 the correct volts; that
        1/10 is what this test actually catches (confirmed by reverting just
        the multiply -- see the report).

        Uses an explicit noise-free signal/sample_rate rather than the
        `modern_scope` fixture's defaults: channel 1's default square wave
        (1 kHz) against that fixture's default 1 kHz sample_rate aliases
        badly (14 points/acquisition), so successive free-run acquisitions'
        ptp is not stably comparable -- the same reason the round-trip tests
        above configure their own MockConnection instead of reusing it.
        """
        conn = MockConnection(
            idn=MODERN_IDN,
            timebase=1e-3,
            sample_rate=20_000.0,
            signals={1: SignalSpec(kind="sine", frequency=200.0, amplitude=1.0, noise_rms=0.0)},
        )
        scope = Oscilloscope("mock", connection=conn)
        scope.connect()

        wf_1x = scope.get_waveform(1)
        scope.channel1.probe_ratio = 10.0
        wf_10x = scope.get_waveform(1)

        assert wf_10x.voltage_scale == pytest.approx(wf_1x.voltage_scale)
        assert np.ptp(wf_10x.voltage) == pytest.approx(np.ptp(wf_1x.voltage), rel=0.05)
        scope.disconnect()

    def test_mock_rejects_bare_probe_set_form_like_hardware(self, modern_scope):
        # Measured 2026-07-31: ':CHANnel1:PROBe 10' -> -224, setting unchanged.
        conn = modern_scope._connection
        conn.write(":CHANnel1:PROBe 10")
        assert conn.error_queue and conn.error_queue[0][0] == -224
        assert conn.query(":CHANnel1:PROBe?") == "1.00E+00"


def test_the_mock_frames_data_the_way_the_instrument_does():
    """The mock emitted a bare fixed-width "#9..." with no trailing bytes for
    BOTH replies, so CI never exercised the variable-width header or the
    trailing newlines that every real transfer carries.
    """
    from scpi_control.connection.mock.siglent import build_waveform_data, build_waveform_preamble

    conn = MockConnection(idn=MODERN_IDN, sample_rate=20_000.0, timebase=1e-3)
    conn.record_length = 1000
    conn.waveform_source = "C1"
    build_waveform_preamble(conn)  # populates the code cache DATA? slices
    data = build_waveform_data(conn)

    assert data.endswith(b"\n\n"), "DATA? replies carry two trailing newlines"
    assert data.startswith(b"#41000"), "1000 bytes must use the general variable-width header (#4 + '1000'), " "not the fixed 9-digit form: {0!r}".format(data[:12])
    assert build_waveform_preamble(conn).endswith(b"\n"), "PREamble? carries one trailing newline"
    assert build_waveform_preamble(conn).startswith(b"#9000000346"), "PREamble? does keep the fixed 9-digit header, unlike DATA?"
