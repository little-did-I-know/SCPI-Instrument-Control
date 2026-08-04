"""Public vocabulary enums (typed-instrument-api Task 2)."""

import pytest

import scpi_control
from scpi_control import exceptions
from scpi_control.vocabulary import (
    BandwidthLimit, Coupling, TrackingMode, TriggerCoupling, TriggerMode,
    TriggerSlope, TriggerSource, TriggerType, normalize_token,
)


def test_members_mirror_the_command_layer_public_sets_exactly():
    # The enums and scpi_commands' public sets must never drift. vocabulary.py
    # cannot import scpi_commands (dependency direction), so the TEST pins it.
    from scpi_control.scpi_commands import _PUBLIC_COUPLINGS, _PUBLIC_MODES, _PUBLIC_SLOPES, _TRIGGER_TYPES

    assert {m.value for m in TriggerMode} == _PUBLIC_MODES
    assert {m.value for m in TriggerSlope} == _PUBLIC_SLOPES
    assert {m.value for m in Coupling} == _PUBLIC_COUPLINGS
    assert {m.value for m in TriggerType} == _TRIGGER_TYPES


def test_fixed_member_sets():
    assert {m.value for m in TriggerCoupling} == {"DC", "AC", "HFREJ", "LFREJ"}
    assert {m.value for m in TriggerSource} == {"C1", "C2", "C3", "C4", "EX", "EX5", "LINE"}
    assert {m.value for m in BandwidthLimit} == {"ON", "OFF", "FULL"}
    assert {m.value for m in TrackingMode} == {"INDEPENDENT", "SERIES", "PARALLEL"}


def test_string_compatibility_both_directions():
    assert Coupling.DC == "DC"
    assert "DC" == Coupling.DC
    assert Coupling.DC.upper() == "DC"          # setters call .upper() on inputs
    # name == value for every member => hash-compatible with plain strings:
    for enum_cls in (Coupling, TriggerMode, TriggerSlope, TriggerCoupling, TriggerType, TriggerSource, BandwidthLimit, TrackingMode):
        for member in enum_cls:
            assert member.name == member.value
            assert member in {member.value}
            assert member.value in {member}


def test_top_level_exports():
    for name in ("Coupling", "TriggerMode", "TriggerSlope", "TriggerCoupling",
                 "TriggerType", "TriggerSource", "BandwidthLimit", "TrackingMode"):
        assert hasattr(scpi_control, name)


def test_literal_aliases_still_importable_from_their_old_homes():
    from scpi_control.trigger import TriggerCouplingType, TriggerModeType, TriggerSlopeType, TriggerTypeType  # noqa: F401
    from scpi_control.channel import BandwidthLimitType, CouplingType  # noqa: F401


class TestNormalizeToken:
    def test_normalizes_case_and_folds_aliases(self):
        assert normalize_token("normal", parameter="trigger mode",
                               valid={"AUTO", "NORM", "SINGLE", "STOP"}, aliases={"NORMAL": "NORM"}) == "NORM"

    def test_accepts_enum_members(self):
        assert normalize_token(TriggerMode.AUTO, parameter="trigger mode",
                               valid={"AUTO", "NORM", "SINGLE", "STOP"}) == "AUTO"

    def test_invalid_token_raises_structured_error(self):
        with pytest.raises(exceptions.InvalidParameterError) as exc_info:
            normalize_token("XX", parameter="coupling", valid={"AC", "DC", "GND"}, dialect="modern", model="SDS824X HD")
        err = exc_info.value
        assert err.parameter == "coupling" and err.value == "XX"
        assert err.valid_options == ["AC", "DC", "GND"] and err.dialect == "modern"
        assert isinstance(err, ValueError)
