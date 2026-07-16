"""Tektronix wire traffic through the public Oscilloscope API (mock-free unit level)."""

import pytest

from scpi_control import exceptions
from scpi_control.scpi_commands import coupling_from_wire
from tests.dialect_helpers import make_dialect_scope


@pytest.fixture
def tek_scope():
    scope = make_dialect_scope("tektronix")
    scope._has_command.side_effect = lambda name: True
    return scope


def test_single_shot_is_stopafter_sequence(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    trig.mode = "SINGLE"
    written = [c.args[0] for c in tek_scope.write.call_args_list]
    assert written == ["ACQuire:STOPAfter SEQuence", "ACQuire:STATE RUN"]


def test_auto_mode_restores_runstop(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    trig.mode = "AUTO"
    written = [c.args[0] for c in tek_scope.write.call_args_list]
    assert written == ["ACQuire:STOPAfter RUNSTop", "TRIGger:A:MODe AUTO"]


def test_trigger_source_uses_ch_tokens(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    trig.source = "C2"
    tek_scope.write.assert_called_with("TRIGger:A:EDGE:SOUrce CH2")

    tek_scope.query.return_value = "CH2"
    assert trig.source == "C2"


def test_trigger_level_targets_source_channel(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    tek_scope.query.return_value = "CH3"
    trig.level = 0.25
    tek_scope.write.assert_called_with("TRIGger:A:LEVel:CH3 0.25")


def test_slope_round_trip(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    trig.slope = "NEG"
    tek_scope.write.assert_called_with("TRIGger:A:EDGE:SLOpe FALL")
    tek_scope.query.return_value = "RISE"
    assert trig.slope == "POS"


def test_window_slope_rejected(tek_scope):
    from scpi_control.trigger import Trigger

    with pytest.raises(exceptions.FeatureNotSupportedError):
        Trigger(tek_scope).slope = "WINDOW"


def test_channel_enabled_parses_numeric_select(tek_scope):
    from scpi_control.channel import Channel

    ch = Channel(tek_scope, 1)
    tek_scope.query.return_value = "1"
    assert ch.enabled is True
    tek_scope.query.return_value = "0"
    assert ch.enabled is False


def test_probe_ratio_gain_inversion():
    from scpi_control.channel import Channel

    # Probe commands are family-split (tek_tbs vs tek_mso); the default
    # "standard" variant has no probe entries at all (Task 7 report,
    # correction #4), so this test builds a tek_tbs scope explicitly.
    tek_tbs_scope = make_dialect_scope("tektronix", "tek_tbs")
    tek_tbs_scope._has_command.side_effect = lambda name: True

    ch = Channel(tek_tbs_scope, 1)
    ch.probe_ratio = 10.0
    tek_tbs_scope.write.assert_called_with("CH1:PRObe:GAIN 0.1")
    tek_tbs_scope.query.return_value = "0.1"
    assert ch.probe_ratio == pytest.approx(10.0)


def test_bandwidth_limit_mapping(tek_scope):
    from scpi_control.channel import Channel

    ch = Channel(tek_scope, 1)
    ch.bandwidth_limit = "ON"
    tek_scope.write.assert_called_with("CH1:BANdwidth TWENty")
    ch.bandwidth_limit = "OFF"
    tek_scope.write.assert_called_with("CH1:BANdwidth FULL")
    tek_scope.query.return_value = "FULL"
    assert ch.bandwidth_limit == "OFF"


def test_dcreject_coupling_normalizes_to_ac():
    # MSO2 CH<x>:COUPling? can return DCREJect; DCREJect passes AC only, so
    # it normalizes to the public AC token -- MSO2 PM 077-1776-07 p.2-184.
    assert coupling_from_wire("tektronix", "DCREJ") == "AC"
    assert coupling_from_wire("tektronix", "DCREJECT") == "AC"
