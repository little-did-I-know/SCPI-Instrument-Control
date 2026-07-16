"""Tests for the dual-dialect SCPI command tables and enum mappers."""

import pytest

from scpi_control.scpi_commands import (
    SCPICommandSet,
    badge_type_to_wire,
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

    def test_valid_public_token_unsupported_on_dialect_raises(self):
        # STOP is the :TRIGger:STOP command on modern, not a trigger-mode token;
        # the converter contract maps "valid public token, missing from dialect
        # table" to FeatureNotSupportedError (ValueError stays reserved for
        # invalid public tokens).
        from scpi_control import exceptions

        with pytest.raises(exceptions.FeatureNotSupportedError):
            mode_to_wire("modern", "STOP")


from scpi_control.scpi_commands import measurement_to_wire


class TestMeasurementRouting:
    def test_legacy_measurement_table_entries(self):
        cmds = SCPICommandSet("legacy")
        # NOTE: get_parameter_value's wire form is "PAVA? {param},C{ch}", not
        # "C{ch}:PAVA? {param}" -- this matches the wire string measurement.py
        # actually sent pre-refactor (and what the legacy mock's PAVA? regex
        # parses); the table previously held an unreachable, never-exercised
        # value here.
        assert cmds.get_command("get_parameter_value", ch=1, param="PKPK") == "PAVA? PKPK,C1"
        assert cmds.get_command("add_measurement", mtype="FREQ", ch=2) == "PACU FREQ,C2"
        assert cmds.get_command("set_statistics", state="ON") == "PAST ON"
        assert cmds.get_command("clear_measurements") == "PACL"
        assert cmds.get_command("reset_statistics") == "PASTAT RESET"
        assert cmds.get_command("set_trigger_holdoff", t=0.001) == "TRIG_DELAY 0.001"
        assert cmds.get_command("set_channel_unit", ch=1, unit="A") == "C1:UNIT A"

    def test_modern_lacks_statistics_and_holdoff(self):
        cmds = SCPICommandSet("modern")
        assert not cmds.has_command("add_measurement")
        assert not cmds.has_command("set_statistics")
        assert not cmds.has_command("set_trigger_holdoff")
        assert not cmds.has_command("set_channel_unit")

    def test_measurement_to_wire_identity_for_siglent(self):
        assert measurement_to_wire("legacy", "PKPK") == "PKPK"
        assert measurement_to_wire("modern", "FREQ") == "FREQ"
        with pytest.raises(ValueError):
            measurement_to_wire("legacy", "BOGUS")


from scpi_control.scpi_commands import probe_from_wire, probe_to_wire
from scpi_control import exceptions as exc


class TestTektronixTable:
    def setup_method(self):
        self.cmds = SCPICommandSet("tektronix", "tek_tbs")

    def test_channel_and_timebase(self):
        assert self.cmds.get_command("set_voltage_div", ch=1, vdiv=0.5) == "CH1:SCAle 0.5"
        assert self.cmds.get_command("set_voltage_offset", ch=2, offset=-1.0) == "CH2:OFFSet -1.0"
        assert self.cmds.get_command("set_coupling", ch=1, coupling="AC") == "CH1:COUPling AC"
        assert self.cmds.get_command("set_time_div", tdiv=0.002) == "HORizontal:SCAle 0.002"
        assert self.cmds.get_command("get_sample_rate") == "HORizontal:SAMPLERate?"
        assert self.cmds.get_command("set_channel_display", ch=1, state="ON") == "SELect:CH1 ON"

    def test_mso_display_override(self):
        mso = SCPICommandSet("tektronix", "tek_mso")
        assert mso.get_command("set_channel_display", ch=1, state="ON") == "DISplay:GLObal:CH1:STATE ON"

    def test_trigger_commands(self):
        assert self.cmds.get_command("set_trigger_mode", mode="NORMal") == "TRIGger:A:MODe NORMal"
        assert self.cmds.get_command("set_trigger_source", src="CH2") == "TRIGger:A:EDGE:SOUrce CH2"
        assert self.cmds.get_command("set_trigger_level", ch=1, level=0.5) == "TRIGger:A:LEVel:CH1 0.5"
        assert self.cmds.get_command("set_trigger_slope", slope="RISe") == "TRIGger:A:EDGE:SLOpe RISe"
        assert self.cmds.get_command("run") == "ACQuire:STATE RUN"
        assert self.cmds.get_command("stop") == "ACQuire:STATE STOP"
        assert self.cmds.get_command("set_stop_after", mode="SEQuence") == "ACQuire:STOPAfter SEQuence"
        assert self.cmds.get_command("get_acq_status") == "TRIGger:STATE?"
        assert self.cmds.get_command("set_trigger_holdoff", t=0.001) == "TRIGger:A:HOLDoff:TIMe 0.001"
        assert not self.cmds.has_command("arm_trigger")

    def test_waveform_and_measurement_entries(self):
        assert self.cmds.get_command("set_data_source", ch=1) == "DATa:SOUrce CH1"
        assert self.cmds.get_command("get_waveform") == "CURVe?"
        assert self.cmds.get_command("get_wfm_ymult") == "WFMOutpre:YMUlt?"
        # PK2Pk spelling per TBS1000C PM 077-1691-01 p.119
        assert self.cmds.get_command("set_meas_immed_type", type="PK2Pk") == "MEASUrement:IMMed:TYPe PK2Pk"

    def test_family_splits(self):
        # Manual-verified divergences: IMMed measurements and PRObe:GAIN are
        # TBS-only; WFMOutpre:PT_Off? and PROBEFunc:EXTAtten are MSO-only.
        mso = SCPICommandSet("tektronix", "tek_mso")
        assert self.cmds.has_command("set_meas_immed_type")
        assert not mso.has_command("set_meas_immed_type")
        assert not mso.has_command("get_meas_immed_value")
        assert not self.cmds.has_command("get_wfm_pt_off")
        assert mso.get_command("get_wfm_pt_off") == "WFMOutpre:PT_Off?"
        assert self.cmds.get_command("set_probe_ratio", ch=1, gain=0.1) == "CH1:PRObe:GAIN 0.1"
        assert mso.get_command("set_probe_ratio", ch=1, gain=0.1) == "CH1:PROBEFunc:EXTAtten 0.1"

    def test_connect_setup(self):
        assert CONNECT_SETUP["tektronix"] == ["HEADer OFF"]


class TestTektronixConverters:
    def test_modes(self):
        assert mode_to_wire("tektronix", "AUTO") == "AUTO"
        assert mode_to_wire("tektronix", "NORM") == "NORMal"
        assert mode_from_wire("tektronix", "NORMAL") == "NORM"
        with pytest.raises(exc.FeatureNotSupportedError):
            mode_to_wire("tektronix", "SINGLE")  # single-shot is a command sequence, not a mode

    def test_slopes(self):
        assert slope_to_wire("tektronix", "POS") == "RISe"
        assert slope_to_wire("tektronix", "NEG") == "FALL"
        assert slope_from_wire("tektronix", "RISE") == "POS"
        with pytest.raises(exc.FeatureNotSupportedError):
            slope_to_wire("tektronix", "WINDOW")

    def test_coupling_identity(self):
        assert coupling_to_wire("tektronix", "DC") == "DC"
        assert coupling_to_wire("tektronix", "AC") == "AC"
        assert coupling_from_wire("tektronix", "AC") == "AC"
        # No Tek family has GND coupling (TBS1000C PM p.53: {AC|DC}; MSO2 PM
        # p.2-184: {AC|DC|DCREJect}; 4/5/6 PM 077-1305-11 p.2-299:
        # {AC|DC|DCREJ}) -- valid public token, so it gates as
        # FeatureNotSupportedError rather than ValueError.
        with pytest.raises(exc.FeatureNotSupportedError):
            coupling_to_wire("tektronix", "GND")

    def test_status_map_covers_tek_states(self):
        assert normalize_status("TRIGGER") == "TRIGD"
        assert normalize_status("SAVE") == "STOP"
        assert normalize_status("ARMED") == "ARM"

    def test_probe_gain_inversion(self):
        assert probe_to_wire("tektronix", 10.0) == "0.1"
        assert probe_from_wire("tektronix", "0.1") == pytest.approx(10.0)
        assert probe_to_wire("legacy", 10.0) == "10"
        assert probe_from_wire("legacy", "10") == pytest.approx(10.0)

    def test_channel_token_tek(self):
        assert channel_token("tektronix", 2) == "CH2"
        assert channel_token("tektronix", "C2") == "CH2"
        assert source_from_wire("tektronix", "CH2") == "C2"

    def test_measurement_map(self):
        # Wire spellings verbatim from TBS1000C PM 077-1691-01 p.119
        assert measurement_to_wire("tektronix", "PKPK") == "PK2Pk"
        assert measurement_to_wire("tektronix", "FREQ") == "FREQuency"
        assert measurement_to_wire("tektronix", "TOP") == "HIGH"
        assert measurement_to_wire("tektronix", "DUTY") == "PDUty"


class TestLeCroyTable:
    def setup_method(self):
        self.cmds = SCPICommandSet("lecroy", "lecroy_maui")

    def test_inherits_lecroy_flat_syntax(self):
        assert self.cmds.get_command("set_voltage_div", ch=1, vdiv=0.5) == "C1:VDIV 0.5"
        assert self.cmds.get_command("set_trigger_select", type="EDGE", src="C2") == "TRIG_SELECT EDGE,SR,C2"
        assert self.cmds.get_command("set_time_div", tdiv=0.002) == "TDIV 0.002"
        assert self.cmds.get_command("run") == "TRIG_MODE AUTO"
        assert self.cmds.get_command("stop") == "STOP"
        assert self.cmds.get_command("arm_trigger") == "ARM"

    def test_lecroy_specific_diffs(self):
        assert self.cmds.get_command("get_acq_status") == "INR?"
        assert self.cmds.get_command("get_waveform", ch=1) == "C1:WF? ALL"
        assert self.cmds.get_command("set_comm_format", fmt="BYTE") == "CFMT DEF9,BYTE,BIN"
        assert self.cmds.get_command("set_comm_order") == "CORD LO"
        assert self.cmds.get_command("set_bandwidth_limit", ch=1, limit="ON") == "BWL C1,ON"
        assert not self.cmds.has_command("set_statistics")
        assert not self.cmds.has_command("set_trigger_holdoff")
        # add_measurement dropped: LeCroy PACU is slot-first (see task-13 report)
        assert not self.cmds.has_command("add_measurement")
        # PAVA form: manual mandates the LeCroy-native trace-prefix form
        # "C{ch}:PAVA? {param}" (MAUI p.7-70), NOT the Siglent "PAVA? p,C{ch}"
        # form -- decided from the manual (see task-13 report, PAVA-form decision).
        assert self.cmds.get_command("get_parameter_value", ch=1, param="PKPK") == "C1:PAVA? PKPK"

    def test_lecroy_converters_match_legacy(self):
        assert mode_to_wire("lecroy", "NORM") == "NORM"
        assert slope_to_wire("lecroy", "POS") == "POS"
        assert coupling_to_wire("lecroy", "AC") == "A1M"
        assert measurement_to_wire("lecroy", "PKPK") == "PKPK"
        assert is_flat_trigger("lecroy") is True
        assert "lecroy" in BARE_NR3_DIALECTS

    def test_connect_setup(self):
        assert CONNECT_SETUP["lecroy"] == ["CHDR OFF"]


# --- Task 3: tektronix base table verified against 4/5/6 PM 077-1305-11 ------


def test_tek_mso_variant_serves_all_modern_mso_families():
    # MSO 2/4/5/6 all resolve to tek_mso and therefore to the same overrides;
    # verified against MSO2 PM 077-1776-07 and 4/5/6 PM 077-1305-11.
    from scpi_control.models import MODEL_REGISTRY

    for model in ("MSO24", "MSO44", "MSO46", "MSO54", "MSO56", "MSO58", "MSO58LP", "MSO64"):
        assert MODEL_REGISTRY[model].scpi_variant == "tek_mso"

    cmds = SCPICommandSet("tektronix", "tek_mso")
    # DISplay:GLObal:CH<x>:STATE {<NR1>|OFF|ON} -- MSO2 p.2-225 / MSO456 p.2-352
    assert cmds.get_command("set_channel_display", ch=8, state="ON") == "DISplay:GLObal:CH8:STATE ON"
    # CH<x>:PROBEFunc:EXTAtten <NR3> -- MSO2 p.2-192 / MSO456 p.2-316
    assert cmds.get_command("set_probe_ratio", ch=8, gain="0.1") == "CH8:PROBEFunc:EXTAtten 0.1"
    # WFMOutpre:PT_Off? -- MSO2 p.2-701 / MSO456 p.2-1462
    assert cmds.get_command("get_wfm_pt_off") == "WFMOutpre:PT_Off?"
    # MEASUrement:IMMed has no command-reference entry in either MSO manual.
    assert not cmds.has_command("set_meas_immed_type")


def test_tek_line_trigger_source_gate_is_conservative_not_absence():
    """LINE exists on 2 of the 3 Tek families; the gate is a portability gate.

    Edge-source vocabularies, verbatim from the manuals:
      TBS1000C  077-1691-01 p.152    {CH1|CH2|LINE|AUX}       -> LINE
      2 Series  077-1776-07 p.2-663  {CH<x>|DCH<x>_D<x>|INTernal|AUXiliary}
      4/5/6     077-1305-11 p.2-1406 {CH<x>|CH<x>_D<y>|LINE|AUXiliary} -> LINE

    The LINE divergence falls *inside* the tek_mso variant (MSO2 lacks it, the
    4/5/6 has it), so the variant cannot express it and LINE stays gated
    dialect-wide. If tek_mso is ever split, or a per-model capability flag
    lands, this test is the one to revisit -- see the task-3 report.
    """
    from scpi_control.scpi_commands import channel_token

    with pytest.raises(exc.FeatureNotSupportedError):
        channel_token("tektronix", "LINE")

    # The AUX mapping is family-independent and stays available.
    assert channel_token("tektronix", "EX") == "AUX"


class TestBadgeMeasurementTable:
    def setup_method(self):
        self.cmds = SCPICommandSet("tektronix", "tek_mso")

    def test_badge_entries(self):
        assert self.cmds.get_command("add_measurement_badge", n=3) == 'MEASUrement:ADDNew "MEAS3"'
        assert self.cmds.get_command("set_badge_type", n=3, type="PK2Pk") == "MEASUrement:MEAS3:TYPe PK2Pk"
        assert self.cmds.get_command("set_badge_source", n=3, src="CH2") == "MEASUrement:MEAS3:SOUrce CH2"
        assert self.cmds.get_command("get_badge_value", n=3) == "MEASUrement:MEAS3:RESUlts:CURRentacq:MEAN?"
        assert self.cmds.get_command("delete_badge", n=3) == 'MEASUrement:DELete "MEAS3"'
        assert self.cmds.get_command("list_badges") == "MEASUrement:LIST?"

    def test_badges_are_mso_only_not_tbs(self):
        # TBS1000C has MEASUrement:IMMed instead; the two are mutually exclusive.
        tbs = SCPICommandSet("tektronix", "tek_tbs")
        assert not tbs.has_command("add_measurement_badge")
        assert tbs.has_command("set_meas_immed_type")
        assert not self.cmds.has_command("set_meas_immed_type")


class TestBadgeTypeMap:
    def test_maps_the_types_both_manuals_share(self):
        assert badge_type_to_wire("tektronix", "PKPK") == "PK2Pk"
        assert badge_type_to_wire("tektronix", "AMPL") == "AMPLITUDE"
        assert badge_type_to_wire("tektronix", "MAX") == "MAXIMUM"
        assert badge_type_to_wire("tektronix", "MIN") == "MINIMUM"
        assert badge_type_to_wire("tektronix", "MEAN") == "MEAN"
        assert badge_type_to_wire("tektronix", "RMS") == "RMS"
        assert badge_type_to_wire("tektronix", "FREQ") == "FREQUENCY"
        assert badge_type_to_wire("tektronix", "PER") == "PERIOD"
        assert badge_type_to_wire("tektronix", "WID") == "PWIDTH"
        assert badge_type_to_wire("tektronix", "NWID") == "NWIDTH"
        assert badge_type_to_wire("tektronix", "DUTY") == "PDUTY"

    def test_badge_vocabulary_differs_from_immed(self):
        # IMMed spells these RISe/FALL; the badge subsystem spells them out.
        assert badge_type_to_wire("tektronix", "RISE") == "RISETIME"
        assert badge_type_to_wire("tektronix", "FALL") == "FALLTIME"
        assert measurement_to_wire("tektronix", "RISE") == "RISe"

    def test_family_divergent_and_absent_types_gate(self):
        # TOP/BASE exist on MSO2 but not 4/5/6 (and vice versa for HIGH/LOW);
        # CMEAN has no badge token; ACRMS is AC-coupled RMS, not cycle RMS.
        for mtype in ("TOP", "BASE", "CMEAN", "CRMS"):
            with pytest.raises(exc.FeatureNotSupportedError):
                badge_type_to_wire("tektronix", mtype)

    def test_unknown_public_type_is_a_value_error(self):
        with pytest.raises(ValueError):
            badge_type_to_wire("tektronix", "BOGUS")
