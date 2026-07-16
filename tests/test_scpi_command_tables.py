"""Tests for the dual-dialect SCPI command tables and enum mappers."""

import pytest

from scpi_control.scpi_commands import (
    SCPICommandSet,
    coupling_from_wire,
    coupling_to_wire,
    mode_from_wire,
    mode_to_wire,
    normalize_status,
    slope_from_wire,
    slope_to_wire,
)


class TestLegacyTable:
    def setup_method(self):
        self.cmds = SCPICommandSet("legacy")

    def test_trigger_select_includes_sr_keyword(self):
        assert self.cmds.get_command("set_trigger_select", type="EDGE", src="C1") == "TRIG_SELECT EDGE,SR,C1"

    def test_trigger_slope_is_per_source(self):
        assert self.cmds.get_command("set_trigger_slope", src="C1", slope="POS") == "C1:TRSL POS"

    def test_acq_status_is_sast(self):
        assert self.cmds.get_command("get_acq_status") == "SAST?"

    def test_run_stop_single(self):
        assert self.cmds.get_command("run") == "TRIG_MODE AUTO"
        assert self.cmds.get_command("stop") == "STOP"
        assert self.cmds.get_command("arm_trigger") == "ARM"
        assert self.cmds.get_command("force_trigger") == "FRTR"

    def test_no_error_query_in_either_dialect(self):
        assert not self.cmds.has_command("get_error")


class TestModernTable:
    def setup_method(self):
        self.cmds = SCPICommandSet("modern")

    def test_trigger_commands(self):
        assert self.cmds.get_command("set_trigger_mode", mode="NORMal") == ":TRIGger:MODE NORMal"
        assert self.cmds.get_command("get_trigger_mode") == ":TRIGger:MODE?"
        assert self.cmds.get_command("set_trigger_type", type="EDGE") == ":TRIGger:TYPE EDGE"
        assert self.cmds.get_command("set_trigger_source", src="D3") == ":TRIGger:EDGE:SOURce D3"
        assert self.cmds.get_command("get_trigger_source") == ":TRIGger:EDGE:SOURce?"
        assert self.cmds.get_command("set_trigger_level", level=0.5) == ":TRIGger:EDGE:LEVel 0.5"
        assert self.cmds.get_command("set_trigger_slope", slope="RISing") == ":TRIGger:EDGE:SLOPe RISing"
        assert self.cmds.get_command("set_trigger_coupling", coupling="DC") == ":TRIGger:EDGE:COUPling DC"

    def test_run_stop_force(self):
        assert self.cmds.get_command("run") == ":TRIGger:RUN"
        assert self.cmds.get_command("stop") == ":TRIGger:STOP"
        assert self.cmds.get_command("force_trigger") == ":TRIGger:MODE FTRIG"
        assert self.cmds.get_command("get_acq_status") == ":TRIGger:STATus?"
        assert not self.cmds.has_command("arm_trigger")

    def test_timebase_channel_acquire(self):
        assert self.cmds.get_command("set_time_div", tdiv=1e-3) == ":TIMebase:SCALe 0.001"
        assert self.cmds.get_command("get_time_div") == ":TIMebase:SCALe?"
        assert self.cmds.get_command("get_sample_rate") == ":ACQuire:SRATe?"
        assert self.cmds.get_command("set_channel_display", ch=2, state="ON") == ":CHANnel2:SWITch ON"
        assert self.cmds.get_command("set_voltage_div", ch=1, vdiv=0.5) == ":CHANnel1:SCALe 0.5"
        assert self.cmds.get_command("set_voltage_offset", ch=1, offset=-1.0) == ":CHANnel1:OFFSet -1.0"
        assert self.cmds.get_command("set_coupling", ch=1, coupling="AC") == ":CHANnel1:COUPling AC"
        assert self.cmds.get_command("set_probe_ratio", ch=1, ratio=10) == ":CHANnel1:PROBe VALue,10"
        assert self.cmds.get_command("set_bandwidth_limit", ch=1, limit="20M") == ":CHANnel1:BWLimit 20M"
        assert self.cmds.get_command("auto_setup") == ":AUToset"

    def test_waveform_stays_legacy_until_sp2(self):
        assert self.cmds.get_command("get_waveform", ch=1) == "C1:WF? DAT2"


class TestEnumMappers:
    def test_mode_round_trip_modern(self):
        assert mode_to_wire("modern", "NORM") == "NORMal"
        assert mode_to_wire("modern", "SINGLE") == "SINGle"
        assert mode_to_wire("modern", "AUTO") == "AUTO"
        assert mode_from_wire("modern", "NORMal") == "NORM"
        assert mode_from_wire("modern", "SINGle") == "SINGLE"
        assert mode_from_wire("modern", "FTRIG") == "AUTO"  # transient force state reads back as AUTO

    def test_mode_passthrough_legacy(self):
        assert mode_to_wire("legacy", "NORM") == "NORM"
        assert mode_from_wire("legacy", "STOP") == "STOP"

    def test_slope_mapping(self):
        assert slope_to_wire("modern", "POS") == "RISing"
        assert slope_to_wire("modern", "NEG") == "FALLing"
        assert slope_to_wire("modern", "WINDOW") == "ALTernate"
        assert slope_from_wire("modern", "FALLing") == "NEG"
        assert slope_to_wire("legacy", "POS") == "POS"

    def test_coupling_mapping(self):
        assert coupling_to_wire("legacy", "DC") == "D1M"
        assert coupling_to_wire("legacy", "AC") == "A1M"
        assert coupling_to_wire("legacy", "GND") == "GND"
        assert coupling_from_wire("legacy", "A1M") == "AC"
        assert coupling_to_wire("modern", "DC") == "DC"
        assert coupling_from_wire("modern", "GND") == "GND"

    def test_status_normalization(self):
        assert normalize_status("Trig'd") == "TRIGD"
        assert normalize_status("Stop") == "STOP"
        assert normalize_status("SAST Trig'd") == "TRIGD"  # legacy pre-CHDR-OFF safety
        assert normalize_status("Ready") == "READY"
        assert normalize_status("Roll") == "ROLL"
        assert normalize_status("Arm") == "ARM"
        assert normalize_status("Auto") == "AUTO"

    def test_invalid_values_raise(self):
        with pytest.raises(ValueError):
            mode_to_wire("modern", "BOGUS")
        with pytest.raises(ValueError):
            normalize_status("???")


from scpi_control.scpi_commands import CONNECT_SETUP, SUPPORTED_DIALECTS


class TestDialectInfrastructure:
    def test_supported_dialects_drive_validation(self):
        assert "legacy" in SUPPORTED_DIALECTS
        assert "modern" in SUPPORTED_DIALECTS
        with pytest.raises(ValueError):
            SCPICommandSet("klingon")

    def test_connect_setup_per_dialect(self):
        assert CONNECT_SETUP["legacy"] == ["CHDR OFF"]
        assert CONNECT_SETUP["modern"] == []

    def test_ieee488_base_present_in_every_dialect(self):
        for dialect in SUPPORTED_DIALECTS:
            cmds = SCPICommandSet(dialect)
            assert cmds.get_command("identify") == "*IDN?"
            assert cmds.get_command("reset") == "*RST"
            assert cmds.get_command("clear_status") == "*CLS"
            assert cmds.get_command("operation_complete") == "*OPC?"


from scpi_control.scpi_commands import BARE_NR3_DIALECTS, channel_token, is_flat_trigger, source_from_wire


class TestDialectHelpers:
    def test_channel_token_passthrough_for_siglent(self):
        assert channel_token("legacy", 2) == "C2"
        assert channel_token("legacy", "C2") == "C2"
        assert channel_token("modern", "C1") == "C1"
        assert channel_token("legacy", "EX") == "EX"
        assert channel_token("legacy", "LINE") == "LINE"

    def test_source_from_wire_passthrough_for_siglent(self):
        assert source_from_wire("legacy", "C2") == "C2"
        assert source_from_wire("modern", " C3 ") == "C3"

    def test_flat_trigger_dialects(self):
        assert is_flat_trigger("legacy") is True
        assert is_flat_trigger("modern") is False

    def test_bare_nr3_dialects(self):
        assert "modern" in BARE_NR3_DIALECTS
        assert "legacy" not in BARE_NR3_DIALECTS
