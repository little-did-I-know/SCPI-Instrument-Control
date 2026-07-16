"""Tests for the dual-personality mock: dialect-exact responses, timeout on unknown queries."""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import TimeoutError

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


def make(idn, **kwargs):
    conn = MockConnection("mock", idn=idn, **kwargs)
    conn.connect()
    return conn


class TestPersonalitySelection:
    def test_dialect_derived_from_idn(self):
        assert make(LEGACY_IDN).scope_dialect == "legacy"
        assert make(MODERN_IDN).scope_dialect == "modern"


class TestModernResponses:
    def setup_method(self):
        self.conn = make(MODERN_IDN, trigger_status=["Ready", "Trig'd"])

    def test_channel_scale_round_trip(self):
        self.conn.write(":CHANnel1:SCALe 0.5")
        assert self.conn.query(":CHANnel1:SCALe?") == "5.00E-01"

    def test_trigger_mode_round_trip_mixed_case(self):
        self.conn.write(":TRIGger:MODE NORMal")
        assert self.conn.query(":TRIGger:MODE?") == "NORMal"

    def test_trigger_status_enum(self):
        assert self.conn.query(":TRIGger:STATus?") == "Ready"
        assert self.conn.query(":TRIGger:STATus?") == "Trig'd"

    def test_timebase_scale_nr3(self):
        self.conn.write(":TIMebase:SCALe 0.001")
        assert self.conn.query(":TIMebase:SCALe?") == "1.00E-03"

    def test_legacy_query_times_out_on_modern_scope(self):
        with pytest.raises(TimeoutError):
            self.conn.query("TDIV?")

    def test_legacy_write_is_recorded_but_ignored(self):
        # Real scopes silently drop unknown writes; only queries time out
        self.conn.write("TDIV 0.001")
        assert "TDIV 0.001" in self.conn.writes

    def test_single_arming_uses_real_status_vocabulary(self):
        conn = make(MODERN_IDN)
        conn.write(":TRIGger:MODE SINGle")
        assert conn.query(":TRIGger:STATus?") == "Ready"
        assert conn.query(":TRIGger:STATus?") == "Stop"

    def test_initial_state_is_modern_vocabulary(self):
        conn = make(MODERN_IDN, trigger_status=["Ready"])
        assert conn.query(":TRIGger:EDGE:SLOPe?") == "RISing"
        assert conn.query(":TRIGger:MODE?") == "AUTO"


class TestLegacyResponses:
    def setup_method(self):
        self.conn = make(LEGACY_IDN)

    def test_vdiv_is_bare_value_with_unit_after_chdr_off(self):
        self.conn.write("C1:VDIV 0.5")
        assert self.conn.query("C1:VDIV?") == "5.00E-01V"

    def test_modern_query_times_out_on_legacy_scope(self):
        with pytest.raises(TimeoutError):
            self.conn.query(":TIMebase:SCALe?")

    def test_unknown_query_times_out(self):
        with pytest.raises(TimeoutError):
            self.conn.query("BOGUS:QUERY?")


def test_legacy_mock_answers_pava_measurements():
    from scpi_control import Oscilloscope
    from scpi_control.connection.mock import MockConnection

    conn = MockConnection("mock", idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0", channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        for mtype in ("PKPK", "FREQ", "RMS", "MEAN", "PER", "MAX", "MIN"):
            value = scope.measurement.measure(mtype, 1)
            assert isinstance(value, float), mtype
    finally:
        scope.disconnect()


def test_modern_mock_still_times_out_on_pava():
    import pytest as _pytest

    from scpi_control import Oscilloscope
    from scpi_control.connection.mock import MockConnection
    from scpi_control.exceptions import SiglentTimeoutError

    conn = MockConnection("mock", idn="Siglent Technologies,SDS824X HD,MOCK0002,3.8.12", channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        with _pytest.raises(SiglentTimeoutError):
            scope.measurement.measure("PKPK", 1)
    finally:
        scope.disconnect()


def test_mock_answers_scdp_with_a_valid_image():
    import io

    from PIL import Image

    from scpi_control import Oscilloscope
    from scpi_control.connection.mock import MockConnection

    conn = MockConnection("mock", idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0")
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        image = scope.screen_capture.get_screenshot_pil()  # BMP → PIL
        assert image.size[0] >= 1 and image.size[1] >= 1
        buf = io.BytesIO()
        image.save(buf, "PNG")
        assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    finally:
        scope.disconnect()


TEK_IDN = "TEKTRONIX,MSO24,MOCK0100,CF:91.1CT FV:1.28"


def _tek_conn(**kwargs):
    from scpi_control.connection.mock import MockConnection

    conn = MockConnection("mock", idn=TEK_IDN, **kwargs)
    conn.connect()
    return conn


def test_tek_mock_answers_tek_queries():
    conn = _tek_conn()
    conn.write("CH1:SCAle 0.5")
    assert conn.query("CH1:SCAle?") == "5.00E-01"
    conn.write("HORizontal:SCAle 0.002")
    assert conn.query("HORizontal:SCAle?") == "2.00E-03"
    assert conn.query("TRIGger:STATE?") in {"ARMED", "AUTO", "READY", "SAVE", "TRIGGER"}


def test_tek_mock_times_out_on_siglent_commands():
    import pytest

    from scpi_control import exceptions

    conn = _tek_conn()
    with pytest.raises(exceptions.TimeoutError):
        conn.query("TDIV?")
    with pytest.raises(exceptions.TimeoutError):
        conn.query(":TIMebase:SCALe?")


def test_tek_mock_trigger_state_machine():
    conn = _tek_conn()
    conn.write("ACQuire:STOPAfter SEQuence")
    conn.write("ACQuire:STATE RUN")
    assert conn.tek_stop_after == "SEQUENCE"
    conn.write("TRIGger:A:EDGE:SOUrce CH2")
    assert conn.trigger_source == "CH2"
    conn.write("TRIGger:A:LEVel:CH2 0.5")
    assert conn.trigger_level[2] == 0.5


def test_tek_mock_serves_curve_block():
    conn = _tek_conn(waveform_payloads={1: bytes([0, 25, 50, 75])})
    conn.write("DATa:SOUrce CH1")
    assert conn.query("WFMOutpre:NR_Pt?") == "4"
    conn.write("CURVe?")
    raw = conn.read_raw()
    assert raw.startswith(b"#")  # bare IEEE block, no DESC prefix


def test_tek_mock_probe_gain_family_split():
    """Task 7 correction: tek_tbs writes CH{ch}:PRObe:GAIN, tek_mso writes
    CH{ch}:PROBEFunc:EXTAtten -- both must land in the same probe_gains state."""
    conn = _tek_conn()
    conn.write("CH1:PRObe:GAIN 0.1")
    assert conn.query("CH1:PRObe:GAIN?") == "1.00E-01"
    conn.write("CH2:PROBEFunc:EXTAtten 10")
    assert conn.query("CH2:PROBEFunc:EXTAtten?") == "1.00E+01"
    assert conn.probe_gains[1] == 0.1
    assert conn.probe_gains[2] == 10.0


LECROY_IDN = "LECROY,WAVESURFER3024Z,MOCK0200,8.5.0"


def _lecroy_conn(**kwargs):
    from scpi_control.connection.mock import MockConnection

    conn = MockConnection("mock", idn=LECROY_IDN, **kwargs)
    conn.connect()
    return conn


def test_lecroy_mock_answers_bare_nr3():
    conn = _lecroy_conn()
    conn.write("C1:VDIV 0.5")
    assert conn.query("C1:VDIV?") == "5.00E-01"  # no V suffix, unlike Siglent legacy
    conn.write("TDIV 0.002")
    assert conn.query("TDIV?") == "2.00E-03"


def test_lecroy_mock_status_and_vbs():
    conn = _lecroy_conn()
    conn.write("TRIG_MODE AUTO")
    assert conn.query("TRIG_MODE?") == "AUTO"
    assert conn.query("INR?") in {"0", "1"}
    assert float(conn.query("VBS? 'return=app.Acquisition.Horizontal.SamplingRate'")) == 1000.0


def test_lecroy_mock_times_out_on_wrong_dialect():
    import pytest

    from scpi_control import exceptions

    conn = _lecroy_conn()
    with pytest.raises(exceptions.TimeoutError):
        conn.query("SAST?")
    with pytest.raises(exceptions.TimeoutError):
        conn.query(":TIMebase:SCALe?")


def test_lecroy_mock_pava():
    conn = _lecroy_conn()
    resp = conn.query("C1:PAVA? PKPK")
    parts = resp.split(",")
    assert parts[0] == "PKPK"
    assert float(parts[1]) == 2.0
    assert parts[2] == "OK"
