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
