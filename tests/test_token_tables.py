"""Per-dialect token tables and accessors (typed-instrument-api Task 3)."""

import pytest

from scpi_control import exceptions
from scpi_control import scpi_commands as sc


class TestModeAliasFolding:
    def test_normal_folds_to_norm_inside_mode_to_wire(self):
        assert sc.mode_to_wire("legacy", "NORMAL") == "NORM"
        assert sc.mode_to_wire("modern", "normal") == "NORMal"


class TestStructuredValidationErrors:
    def test_invalid_public_token_raises_invalid_parameter_error(self):
        with pytest.raises(exceptions.InvalidParameterError) as exc_info:
            sc.slope_to_wire("modern", "POSITIVE")
        err = exc_info.value
        assert err.parameter == "trigger slope"
        assert err.valid_options == ["NEG", "POS", "WINDOW"]
        assert err.dialect == "modern"

    def test_still_catchable_as_valueerror(self):
        # _to_wire raised bare ValueError before this change.
        with pytest.raises(ValueError):
            sc.coupling_to_wire("modern", "BOGUS")

    def test_dialect_gap_names_the_supported_subset(self):
        with pytest.raises(exceptions.FeatureNotSupportedError) as exc_info:
            sc.slope_to_wire("tektronix", "WINDOW")
        assert "NEG" in str(exc_info.value) and "POS" in str(exc_info.value)


class TestTriggerCouplingTables:
    def test_wire_tokens_match_the_setter_maps_they_replace(self):
        # trigger.py:349-354 (pre-change): modern spells out the reject modes,
        # tek uses mixed-case short forms, flat dialects send the public token.
        assert sc.trigger_coupling_to_wire("modern", "HFREJ") == "HFREJect"
        assert sc.trigger_coupling_to_wire("modern", "DC") == "DC"
        assert sc.trigger_coupling_to_wire("tektronix", "LFREJ") == "LFRej"
        assert sc.trigger_coupling_to_wire("legacy", "HFREJ") == "HFREJ"
        assert sc.trigger_coupling_to_wire("lecroy", "AC") == "AC"

    def test_tek_ac_gates_as_unsupported(self):
        # TBS p.151 / MSO2 p.2-661: vocabulary is DC|HFRej|LFRej|NOISErej -- no
        # AC token. The old setter passed AC through (invented-token class).
        with pytest.raises(exceptions.FeatureNotSupportedError):
            sc.trigger_coupling_to_wire("tektronix", "AC")

    def test_from_wire_normalizes_and_passes_unmapped_through(self):
        assert sc.trigger_coupling_from_wire("modern", "HFREJect") == "HFREJ"
        assert sc.trigger_coupling_from_wire("legacy", "DC") == "DC"
        # NOISErej can be set from the front panel; reads must not explode.
        assert sc.trigger_coupling_from_wire("tektronix", "NOISErej") == "NOISEREJ"


class TestSupportSetAccessors:
    def test_trigger_modes_are_universal_via_command_sequences(self):
        for dialect in sc.SUPPORTED_DIALECTS:
            assert sc.supported_trigger_modes(dialect) == frozenset({"AUTO", "NORM", "SINGLE", "STOP"})

    def test_dialect_gaps_are_visible(self):
        assert sc.supported_trigger_types("tektronix") == frozenset({"EDGE"})
        assert sc.supported_trigger_slopes("lecroy") == frozenset({"POS", "NEG"})
        assert sc.supported_couplings("tektronix") == frozenset({"DC", "AC"})
        assert sc.supported_trigger_couplings("tektronix") == frozenset({"DC", "HFREJ", "LFREJ"})
        assert sc.supported_trigger_sources("tektronix") == frozenset({"C1", "C2", "C3", "C4", "EX"})
        assert sc.supported_trigger_sources("modern") == frozenset({"C1", "C2", "C3", "C4", "EX", "EX5", "LINE"})

    def test_measurement_accessors(self):
        assert sc.supported_measurement_types("modern") == frozenset(sc._MEASUREMENT_TYPES)
        assert sc.supported_badge_types("legacy") == frozenset()
        assert "CMEAN" not in sc.supported_badge_types("tektronix")


class TestWireTokenAccessors:
    def test_uppercased_wire_sets(self):
        assert sc.wire_coupling_tokens("legacy") == frozenset({"D1M", "A1M", "GND"})
        assert sc.wire_coupling_tokens("modern") == frozenset({"DC", "AC", "GND"})
        assert sc.wire_trigger_mode_tokens("modern") == frozenset({"AUTO", "NORMAL", "SINGLE", "FTRIG"})
        assert sc.wire_trigger_slope_tokens("modern") == frozenset({"RISING", "FALLING", "ALTERNATE"})
        assert sc.wire_trigger_coupling_tokens("modern") == frozenset({"DC", "AC", "HFREJECT", "LFREJECT"})

    def test_derives_at_call_time(self, monkeypatch):
        # Call-time derivation is what lets Task 8's mutation guards prove the
        # mock and driver share one table.
        monkeypatch.setitem(sc._COUPLING_TO_WIRE["modern"], "DC", "DCX")
        assert "DCX" in sc.wire_coupling_tokens("modern")


class TestTriggerLevelSources:
    def test_flat_dialects_include_the_external_inputs(self):
        # RC01020-E01C p.128: <trig_source> = {C1, C2, C3, C4, EX, EX5}.
        # LeCroy TRLV is cited MAUI p.7-33 in the same table.
        for dialect in ("legacy", "lecroy"):
            assert sc.supported_trigger_level_sources(dialect) == frozenset({"C1", "C2", "C3", "C4", "EX", "EX5"})

    def test_modern_is_unrestricted_because_the_command_takes_no_source(self):
        # EN11G p.493: :TRIGger:EDGE:LEVel <level_value> -- no source argument,
        # so restricting it would invent a limit the manual does not state.
        assert sc.supported_trigger_level_sources("modern") == frozenset({"C1", "C2", "C3", "C4", "EX", "EX5", "LINE"})

    def test_tektronix_is_channels_only(self):
        # The 4/5/6 MSO manual documents TRIGger:A:LEVel:CH<x> (and D/MATH/REF)
        # but no AUX form, so an external source has no citable level command.
        assert sc.supported_trigger_level_sources("tektronix") == frozenset({"C1", "C2", "C3", "C4"})

    def test_line_is_never_a_level_source_on_a_flat_dialect(self):
        for dialect in ("legacy", "lecroy"):
            assert "LINE" not in sc.supported_trigger_level_sources(dialect)
