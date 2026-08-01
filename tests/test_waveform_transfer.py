"""Waveform transfer strategies: golden-blob parses and wire dispatch."""

import struct

import numpy as np
import pytest

from scpi_control import Oscilloscope, exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.waveform_transfer import parse_ieee_block, parse_wavedesc

TEK_IDN = "TEKTRONIX,MSO24,MOCK0100,CF:91.1CT FV:1.28"
LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
LECROY_IDN = "LECROY,WAVESURFER3024Z,MOCK0200,8.5.0"


def _block(payload: bytes) -> bytes:
    length = str(len(payload)).encode()
    return b"#" + str(len(length)).encode() + length + payload


class TestParseIeeeBlock:
    def test_parses_int8_block(self):
        data = parse_ieee_block(_block(bytes([0, 25, 231, 75])), np.int8)
        assert data.tolist() == [0, 25, -25, 75]

    def test_rejects_missing_hash(self):
        with pytest.raises(exceptions.CommandError):
            parse_ieee_block(b"garbage", np.int8)


class TestTektronixGoldenBlob:
    """Hand-built CURVe response with known WFMOutpre scaling.

    ymult=0.04, yoff=0, yzero=0 -> code 25 == 1.0 V exactly.
    xincr=1e-3 -> 1 kSa/s.
    """

    def _scope(self):
        conn = MockConnection(
            "mock",
            idn=TEK_IDN,
            channel_states={1: True, 2: True},
            voltage_scales={1: 1.0},
            waveform_payloads={1: bytes([0, 25, 50, 75])},
            sample_rate=1_000.0,
            timebase=1e-3,
        )
        scope = Oscilloscope("mock", connection=conn)
        scope.connect()
        return scope, conn

    def test_acquire_scales_via_preamble(self):
        scope, conn = self._scope()
        wf = scope.get_waveform(1)
        # mock YMUlt = vdiv/25 = 0.04; codes [0,25,50,75] -> [0,1,2,3] V
        assert wf.voltage == pytest.approx([0.0, 1.0, 2.0, 3.0])
        assert wf.sample_rate == pytest.approx(1_000.0)
        assert len(wf.time) == 4
        assert wf.time[1] - wf.time[0] == pytest.approx(1e-3)
        assert "CURVe?" in conn.writes
        assert "DATa:SOUrce CH1" in conn.writes
        scope.disconnect()

    def test_word_format_not_supported_yet(self):
        scope, conn = self._scope()
        with pytest.raises(exceptions.FeatureNotSupportedError):
            scope.waveform.acquire(1, format="WORD")
        scope.disconnect()


class TestSiglentPathUnchanged:
    def test_legacy_acquire_still_works(self):
        conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, sample_rate=1_000.0, timebase=1e-3)
        scope = Oscilloscope("mock", connection=conn)
        scope.connect()
        wf = scope.get_waveform(1)
        assert len(wf.voltage) > 0
        assert any(w.startswith("C1:WF?") for w in conn.writes)
        scope.disconnect()

    def test_word_format_raises_before_touching_the_wire(self):
        """Legacy has no documented way to ask for 16-bit samples.

        RC01020-E01C documents only WAVEFORM_SETUP/WFSU (p.144-145: Sparsing,
        Number of points, First point, and an SPO-only TYPE flag) -- no width
        selector anywhere, and CFMT/COMM_ORDER are LeCroy commands absent from
        this guide. WF? DAT2's response is one byte per sample (p.141-142's
        worked example transfers 70 bytes for 70 points). The old code sent the
        same request and reinterpreted the bytes as int16, returning half the
        samples as plausible-but-wrong voltages with no error.

        The failure must be pre-flight: no waveform request may be sent.
        """
        conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, sample_rate=1_000.0, timebase=1e-3)
        scope = Oscilloscope("mock", connection=conn)
        scope.connect()
        before_log = list(conn.command_log)
        with pytest.raises(exceptions.FeatureNotSupportedError):
            scope.waveform.acquire(1, format="WORD")
        assert conn.command_log[len(before_log) :] == []
        scope.disconnect()


def build_wavedesc(
    codes: bytes,
    gain: float = 0.04,
    offset: float = 0.0,
    hinterval: float = 1e-3,
    hoffset: float = -2e-3,
    comm_type: int = 0,
    trigtime_len: int = 0,
    ristime_len: int = 0,
) -> bytes:
    desc = bytearray(346)
    desc[0:8] = b"WAVEDESC"
    struct.pack_into("<h", desc, 32, comm_type)  # COMM_TYPE: 0=byte, 1=word
    struct.pack_into("<i", desc, 36, 346)  # WAVE_DESCRIPTOR length
    struct.pack_into("<i", desc, 40, 0)  # USER_TEXT length
    struct.pack_into("<i", desc, 48, trigtime_len)  # TRIGTIME_ARRAY length
    struct.pack_into("<i", desc, 52, ristime_len)  # RIS_TIME_ARRAY length
    struct.pack_into("<i", desc, 116, len(codes))  # WAVE_ARRAY_COUNT
    struct.pack_into("<f", desc, 156, gain)  # VERTICAL_GAIN
    struct.pack_into("<f", desc, 160, offset)  # VERTICAL_OFFSET
    struct.pack_into("<f", desc, 176, hinterval)  # HORIZ_INTERVAL
    struct.pack_into("<d", desc, 180, hoffset)  # HORIZ_OFFSET
    # DATA_ARRAY_1 follows the two optional time arrays; pad them with the
    # declared number of filler bytes so data_offset has something to skip.
    return bytes(desc) + b"\x00" * (trigtime_len + ristime_len) + codes


class TestWavedescGoldenBlob:
    def test_parse_wavedesc_fields(self):
        payload = build_wavedesc(bytes([0, 25, 231, 75]))  # 231 == -25 signed
        meta = parse_wavedesc(payload)
        assert meta["wave_array_count"] == 4
        assert meta["vertical_gain"] == pytest.approx(0.04)
        assert meta["horiz_interval"] == pytest.approx(1e-3)
        assert meta["data_offset"] == 346

    def test_missing_wavedesc_raises(self):
        with pytest.raises(exceptions.CommandError):
            parse_wavedesc(b"\x00" * 400)

    def test_parse_wavedesc_skips_trigtime_array(self):
        # A non-zero TRIGTIME_ARRAY sits between USER_TEXT and the sample data;
        # data_offset must skip WAVEDESC + USER_TEXT + TRIGTIME_ARRAY +
        # RIS_TIME_ARRAY so the codes still decode to the correct volts.
        trigtime = 24
        payload = build_wavedesc(bytes([0, 25, 50, 75]), trigtime_len=trigtime)
        meta = parse_wavedesc(payload)
        assert meta["trigtime_len"] == trigtime
        assert meta["ristime_len"] == 0
        assert meta["data_offset"] == 346 + trigtime
        codes = np.frombuffer(payload, dtype=np.int8, count=meta["wave_array_count"], offset=meta["data_offset"])
        voltage = meta["vertical_gain"] * codes.astype(np.float64) - meta["vertical_offset"]
        assert voltage == pytest.approx([0.0, 1.0, 2.0, 3.0])


class TestLeCroyAcquire:
    def test_acquire_scales_via_wavedesc(self):
        conn = MockConnection(
            "mock",
            idn=LECROY_IDN,
            channel_states={1: True},
            voltage_scales={1: 1.0},
            waveform_payloads={1: bytes([0, 25, 50, 75])},
            sample_rate=1_000.0,
            timebase=1e-3,
        )
        scope = Oscilloscope("mock", connection=conn)
        scope.connect()
        wf = scope.get_waveform(1)
        # mock gain = vdiv/25 = 0.04, offset 0: codes [0,25,50,75] -> [0,1,2,3] V
        assert wf.voltage == pytest.approx([0.0, 1.0, 2.0, 3.0])
        assert wf.time[1] - wf.time[0] == pytest.approx(1e-3)
        assert "CFMT DEF9,BYTE,BIN" in conn.writes
        assert "CORD LO" in conn.writes
        assert "C1:WF? ALL" in conn.writes
        scope.disconnect()
