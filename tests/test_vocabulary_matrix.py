"""Driver-side per-dialect vocabulary matrix (typed-instrument-api Tasks 4-5).

Every token-valued setter x every dialect: canonical tokens produce the
documented wire command; invalid tokens raise structured InvalidParameterError
BEFORE any write; dialect gaps raise FeatureNotSupportedError.
"""

import pytest

from scpi_control import exceptions
from scpi_control.channel import Channel
from scpi_control.scpi_commands import (
    supported_couplings,
    supported_trigger_couplings,
    supported_trigger_modes,
    supported_trigger_slopes,
    supported_trigger_types,
    trigger_coupling_to_wire,
    trigger_type_to_wire,
    slope_to_wire,
)
from scpi_control.trigger import Trigger
from scpi_control.vocabulary import BandwidthLimit, Coupling, TriggerCoupling, TriggerMode, TriggerSlope
from tests.dialect_helpers import make_dialect_scope

DIALECTS = ["legacy", "modern", "tektronix", "lecroy"]


@pytest.mark.parametrize("dialect", DIALECTS)
def test_every_supported_trigger_mode_writes_without_error(dialect):
    scope = make_dialect_scope(dialect)
    # Global-style setters read acquisition status / current type first; feed
    # a plausible query response for any query the setter performs.
    scope.query.return_value = "EDGE,SR,C1,HT,OFF"
    trigger = Trigger(scope)
    for mode in sorted(supported_trigger_modes(dialect)):
        trigger.mode = mode
        assert scope.write.called
        scope.write.reset_mock()


@pytest.mark.parametrize("dialect", DIALECTS)
def test_enum_and_string_spell_the_same_wire_bytes(dialect):
    scope_a, scope_b = make_dialect_scope(dialect), make_dialect_scope(dialect)
    scope_a.query.return_value = scope_b.query.return_value = "EDGE,SR,C1,HT,OFF"
    Trigger(scope_a).mode = TriggerMode.AUTO
    Trigger(scope_b).mode = "AUTO"
    assert scope_a.write.call_args_list == scope_b.write.call_args_list


@pytest.mark.parametrize("dialect", DIALECTS)
def test_invalid_mode_is_rejected_before_the_wire(dialect):
    scope = make_dialect_scope(dialect)
    trigger = Trigger(scope)
    with pytest.raises(exceptions.InvalidParameterError) as exc_info:
        trigger.mode = "SOMETIMES"
    assert exc_info.value.parameter == "trigger mode"
    assert exc_info.value.dialect == dialect
    scope.write.assert_not_called()


def test_normal_alias_still_folds():
    scope = make_dialect_scope("legacy")
    Trigger(scope).mode = "NORMAL"
    scope.write.assert_called_once_with("TRIG_MODE NORM")


def test_invalid_source_rejected_before_wire_with_options_listed():
    scope = make_dialect_scope("modern")
    trigger = Trigger(scope)
    with pytest.raises(exceptions.InvalidParameterError) as exc_info:
        trigger.source = "C9"
    assert "C1" in str(exc_info.value)
    scope.write.assert_not_called()


class TestTriggerCoupling:
    def test_modern_reject_modes_spelled_out_on_the_wire(self):
        scope = make_dialect_scope("modern")
        Trigger(scope).coupling = TriggerCoupling.HFREJ
        scope.write.assert_called_once_with(":TRIGger:EDGE:COUPling HFREJect")

    def test_flat_dialect_sends_public_token_with_source_prefix(self):
        scope = make_dialect_scope("legacy")
        scope.query.return_value = "EDGE,SR,C1,HT,OFF"  # source lookup
        Trigger(scope).coupling = "LFREJ"
        scope.write.assert_called_once_with("C1:TRCP LFREJ")

    def test_tek_ac_now_gates_instead_of_shipping_an_undocumented_token(self):
        # TBS p.151: DC|HFRej|LFRej|NOISErej -- no AC. Old code sent "AC".
        scope = make_dialect_scope("tektronix")
        with pytest.raises(exceptions.FeatureNotSupportedError):
            Trigger(scope).coupling = "AC"
        scope.write.assert_not_called()

    def test_getter_normalizes_and_tolerates_front_panel_states(self):
        scope = make_dialect_scope("modern")
        scope.query.return_value = "HFREJect"
        assert Trigger(scope).coupling == "HFREJ"
        scope_tek = make_dialect_scope("tektronix")
        scope_tek.query.return_value = "NOISErej"
        assert Trigger(scope_tek).coupling == "NOISEREJ"


def test_capability_sets_and_setters_agree():
    # Whatever the support-set accessors claim, the converter must express --
    # this is the invariant scope.capabilities relies on (Task 6).
    for dialect in DIALECTS:
        for token in supported_trigger_slopes(dialect):
            slope_to_wire(dialect, token)
        for token in supported_trigger_types(dialect):
            trigger_type_to_wire(dialect, token)
        for token in supported_trigger_couplings(dialect):
            trigger_coupling_to_wire(dialect, token)


@pytest.mark.parametrize("dialect", DIALECTS)
def test_every_supported_channel_coupling_reaches_the_wire(dialect):
    scope = make_dialect_scope(dialect)
    channel = Channel(scope, 1)
    for token in sorted(supported_couplings(dialect)):
        channel.coupling = token
        assert scope.write.called
        scope.write.reset_mock()


def test_channel_coupling_enum_spells_legacy_wire_token():
    scope = make_dialect_scope("legacy")
    Channel(scope, 1).coupling = Coupling.DC
    scope.write.assert_called_once_with("C1:CPL D1M")


def test_invalid_channel_coupling_structured_and_prewire():
    scope = make_dialect_scope("modern")
    channel = Channel(scope, 1)
    with pytest.raises(exceptions.InvalidParameterError) as exc_info:
        channel.coupling = "AC50"
    assert exc_info.value.parameter == "coupling mode"
    scope.write.assert_not_called()


def test_tek_gnd_coupling_still_gates():
    scope = make_dialect_scope("tektronix")
    with pytest.raises(exceptions.FeatureNotSupportedError):
        Channel(scope, 1).coupling = Coupling.GND
    scope.write.assert_not_called()


def test_bandwidth_limit_enum_and_string_equivalent():
    scope_a, scope_b = make_dialect_scope("modern"), make_dialect_scope("modern")
    Channel(scope_a, 1).bandwidth_limit = BandwidthLimit.ON
    Channel(scope_b, 1).bandwidth_limit = "ON"
    assert scope_a.write.call_args_list == scope_b.write.call_args_list
    assert scope_a.write.call_args_list[0].args[0] == ":CHANnel1:BWLimit 20M"


def test_invalid_bandwidth_limit_structured():
    scope = make_dialect_scope("legacy")
    with pytest.raises(exceptions.InvalidParameterError) as exc_info:
        Channel(scope, 1).bandwidth_limit = "20MHZ"
    assert exc_info.value.valid_options == ["FULL", "OFF", "ON"]
    scope.write.assert_not_called()
