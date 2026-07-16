"""Waveform transfer strategies: golden-blob parses and wire dispatch."""

import numpy as np
import pytest

from scpi_control import Oscilloscope, exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.waveform_transfer import parse_ieee_block

TEK_IDN = "TEKTRONIX,MSO24,MOCK0100,CF:91.1CT FV:1.28"
LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


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
