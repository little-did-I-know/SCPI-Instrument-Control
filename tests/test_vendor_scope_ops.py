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


def test_lecroy_trigger_wire_matches_legacy_shape():
    scope = make_dialect_scope("lecroy")
    scope._has_command.side_effect = lambda name: True
    from scpi_control.trigger import Trigger

    trig = Trigger(scope)
    scope.query.return_value = "EDGE,SR,C1"
    trig.mode = "NORM"
    scope.write.assert_called_with("TRIG_MODE NORM")


def _lecroy_scope():
    from unittest.mock import Mock

    from scpi_control.oscilloscope import Oscilloscope
    from scpi_control.scpi_commands import SCPICommandSet

    scope = Oscilloscope("mock", connection=Mock())
    scope.dialect = "lecroy"
    scope._scpi_commands = SCPICommandSet("lecroy", "lecroy_maui")
    return scope


def test_lecroy_acquisition_status_stop_via_trig_mode():
    # TRIG_MODE? ending in STOP short-circuits to STOP without an INR? read.
    from unittest.mock import Mock

    scope = _lecroy_scope()
    scope.query = Mock(return_value="STOP")
    assert scope.acquisition_status() == "STOP"
    assert scope.query.call_count == 1  # no INR? read once STOP is seen


def test_lecroy_acquisition_status_trigd_via_inr_bit0():
    # TRIG_MODE? -> NORM, then INR? with bit 0 set == a new signal acquired.
    from unittest.mock import Mock

    scope = _lecroy_scope()
    scope.query = Mock(side_effect=["NORM", "1"])
    assert scope.acquisition_status() == "TRIGD"


def test_lecroy_acquisition_status_auto_and_ready():
    from unittest.mock import Mock

    scope = _lecroy_scope()
    scope.query = Mock(side_effect=["AUTO", "0"])
    assert scope.acquisition_status() == "AUTO"
    scope2 = _lecroy_scope()
    scope2.query = Mock(side_effect=["NORM", "0"])
    assert scope2.acquisition_status() == "READY"


def test_lecroy_bandwidth_getter_parses_global_pairs():
    # Real LeCroy BWL? vocabulary has no "ON" token -- {OFF,20MHZ,200MHZ,...}
    # (MAUI p.7-18). Any non-OFF wire token maps to the public "ON".
    from scpi_control.channel import Channel

    scope = make_dialect_scope("lecroy")
    scope.query.return_value = "C1,OFF,C2,20MHZ,C3,OFF,C4,OFF"
    assert Channel(scope, 2).bandwidth_limit == "ON"
    assert Channel(scope, 1).bandwidth_limit == "OFF"
    # Missing channel in the pair list falls back to OFF.
    scope.query.return_value = "C1,OFF"
    assert Channel(scope, 3).bandwidth_limit == "OFF"


def test_lecroy_bandwidth_setter_maps_on_to_20mhz():
    # LeCroy has no "ON" token (MAUI p.7-18): public ON -> wire "20MHZ",
    # OFF/FULL -> wire "OFF".
    from scpi_control.channel import Channel

    scope = make_dialect_scope("lecroy")
    scope._has_command.side_effect = lambda name: True
    ch = Channel(scope, 1)
    ch.bandwidth_limit = "ON"
    scope.write.assert_called_with("BWL C1,20MHZ")
    ch.bandwidth_limit = "OFF"
    scope.write.assert_called_with("BWL C1,OFF")
    ch.bandwidth_limit = "FULL"
    scope.write.assert_called_with("BWL C1,OFF")


def test_lecroy_window_slope_rejected():
    # LeCroy TRIG_SLOPE is {NEG, POS} only (MAUI p.7-40) -- WINDOW gates.
    scope = make_dialect_scope("lecroy")
    scope._has_command.side_effect = lambda name: True
    from scpi_control.trigger import Trigger

    with pytest.raises(exceptions.FeatureNotSupportedError):
        Trigger(scope).slope = "WINDOW"


# --- A1: dialect-scoped variant overrides + probe_ratio gating -------------

MSO24_IDN = "TEKTRONIX,MSO24,MOCK0100,CF:91.1CT FV:1.28"
TBS_IDN = "TEKTRONIX,TBS1102C,MOCK0002,CF:91.1CT FV:1.10"
SIGLENT_LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


def _real_scope(idn, dialect=None):
    from scpi_control.connection.mock import MockConnection
    from scpi_control.oscilloscope import Oscilloscope

    conn = MockConnection("mock", idn=idn)
    scope = Oscilloscope("mock", connection=conn, dialect=dialect)
    scope.connect()
    return scope, conn


def test_forced_tektronix_over_siglent_gates_probe_ratio_not_keyerror():
    # Forcing dialect="tektronix" onto a non-Tek (Siglent) IDN yields variant
    # "standard" (x_series does not belong to the tektronix dialect), and the
    # base Tek table has no probe commands. probe_ratio must raise
    # FeatureNotSupportedError, never a raw KeyError (never-KeyError contract).
    scope, conn = _real_scope(SIGLENT_LEGACY_IDN, dialect="tektronix")
    with pytest.raises(exceptions.FeatureNotSupportedError):
        _ = scope.channel1.probe_ratio
    with pytest.raises(exceptions.FeatureNotSupportedError):
        scope.channel1.probe_ratio = 10.0
    scope.disconnect()


def test_forced_modern_over_mso24_uses_modern_table_no_tek_contamination():
    # dialect="modern" over an MSO24 (tek_mso) scope must fall back to the plain
    # modern base table -- no tek_mso override contaminating it. Use a write-only
    # path (the tek mock won't answer modern queries).
    scope, conn = _real_scope(MSO24_IDN, dialect="modern")
    scope.channel1.enabled = True
    assert ":CHANnel1:SWITch ON" in conn.writes
    assert not any("DISplay:GLObal" in w for w in conn.writes)  # tek_mso override absent
    scope.disconnect()


def test_forced_modern_over_tek_mso_variant_unit_level():
    # Unit-level check of the same fallback: SCPICommandSet drops the mismatched
    # tek_mso overrides and serves the plain modern channel-display command.
    from scpi_control.scpi_commands import SCPICommandSet

    cmds = SCPICommandSet("modern", "tek_mso")
    assert cmds.get_command("set_channel_display", ch=1, state="ON") == ":CHANnel1:SWITch ON"


# --- A2: MSO2 bandwidth vocabulary (NR3 hertz vs TBS TWENty) ---------------


def test_mso2_bandwidth_on_uses_nr3_hertz():
    # MSO 2-Series has no TWENty keyword; ON must serialize as a hertz value
    # (MSO2 PM 077-1776-07 p.2-183).
    scope, conn = _real_scope(MSO24_IDN)
    scope.channel1.bandwidth_limit = "ON"
    assert "CH1:BANdwidth 20E6" in conn.writes
    scope.channel1.bandwidth_limit = "OFF"
    assert "CH1:BANdwidth FULL" in conn.writes
    scope.disconnect()


def test_tbs_bandwidth_on_uses_twenty_keyword():
    # TBS1000C keeps the TWEnty keyword (TBS PM 077-1691-01 p.53).
    scope, conn = _real_scope(TBS_IDN)
    scope.channel1.bandwidth_limit = "ON"
    assert "CH1:BANdwidth TWENty" in conn.writes
    scope.disconnect()


# --- A4: EX/EX5/LINE trigger sources on tektronix --------------------------


def test_tek_external_trigger_maps_ex_to_aux():
    # Both Tek families accept AUX (TBS p.152 / MSO2 p.2-663).
    from scpi_control.scpi_commands import channel_token

    assert channel_token("tektronix", "EX") == "AUX"


def test_tek_external_trigger_gates_ex5_and_line():
    # EX5 has no Tek token and LINE is TBS-only (absent on MSO2) -- both gate.
    from scpi_control.scpi_commands import channel_token

    for src in ("EX5", "LINE"):
        with pytest.raises(exceptions.FeatureNotSupportedError):
            channel_token("tektronix", src)


def test_non_tek_dialects_pass_external_trigger_through():
    from scpi_control.scpi_commands import channel_token

    assert channel_token("modern", "EX") == "EX"
    assert channel_token("modern", "EX5") == "EX5"
    assert channel_token("legacy", "LINE") == "LINE"


def test_tek_trigger_source_ex_writes_aux(tek_scope):
    from scpi_control.trigger import Trigger

    Trigger(tek_scope).source = "EX"
    tek_scope.write.assert_called_with("TRIGger:A:EDGE:SOUrce AUX")


def test_tek_trigger_source_ex5_raises_before_write(tek_scope):
    from scpi_control.trigger import Trigger

    with pytest.raises(exceptions.FeatureNotSupportedError):
        Trigger(tek_scope).source = "EX5"
    assert not any("EDGE:SOUrce" in c.args[0] for c in tek_scope.write.call_args_list)


# --- B8: tektronix trigger-level getter -----------------------------------


def test_tek_trigger_level_getter_queries_source_channel(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    # source resolves to CH3, so the level getter targets the per-channel path
    tek_scope.query.side_effect = ["CH3", "0.25"]
    assert trig.level == pytest.approx(0.25)
    assert tek_scope.query.call_args_list[-1].args[0] == "TRIGger:A:LEVel:CH3?"


def test_tek_trigger_level_getter_non_channel_source_returns_zero(tek_scope):
    from scpi_control.trigger import Trigger

    trig = Trigger(tek_scope)
    # A non-channel source (external AUX/LINE) has no per-channel trigger level;
    # the getter guards and returns 0.0 without issuing a level query.
    tek_scope.query.return_value = "AUX"
    assert trig.level == 0.0
    assert not any("LEVel" in c.args[0] for c in tek_scope.query.call_args_list)


def test_validate_channel_uses_model_capability():
    from scpi_control import exceptions
    from scpi_control.models import MODEL_REGISTRY, validate_channel

    class _Scope:
        pass

    scope = _Scope()
    scope.model_capability = MODEL_REGISTRY["SDS1202X-E"]  # 2-channel Siglent
    validate_channel(scope, 1)
    validate_channel(scope, 2)
    # Previously channels 3-4 sailed through the hardcoded 1-4 guard and queried
    # a channel this scope does not physically have.
    with pytest.raises(exceptions.InvalidParameterError, match="Invalid channel number"):
        validate_channel(scope, 3)
    with pytest.raises(exceptions.InvalidParameterError, match="Invalid channel number"):
        validate_channel(scope, 0)


def test_validate_channel_falls_back_when_capability_missing():
    from unittest.mock import Mock

    from scpi_control import exceptions
    from scpi_control.models import MAX_SUPPORTED_CHANNELS, validate_channel

    assert MAX_SUPPORTED_CHANNELS == 8

    # A Mock scope's model_capability.num_channels is itself a Mock, which cannot
    # be compared numerically; the guard must fall back, not raise TypeError.
    validate_channel(Mock(), 8)
    with pytest.raises(exceptions.InvalidParameterError):
        validate_channel(Mock(), 9)

    # No capability attribute at all (pre-connect scope)
    class _Bare:
        model_capability = None

    validate_channel(_Bare(), 8)
    with pytest.raises(exceptions.InvalidParameterError):
        validate_channel(_Bare(), 9)


def test_eight_channel_scope_creates_all_channels_and_cleans_up():
    from scpi_control import Oscilloscope, exceptions
    from scpi_control.connection.mock import MockConnection

    # MSO58 is an 8-channel scope (registry entry lands in Task 2); this test
    # asserts the ceiling machinery, so it builds the capability directly.
    from scpi_control.models import ModelCapability

    cap = ModelCapability(
        model_name="FAKE8",
        series="Test",
        num_channels=8,
        max_sample_rate=1.0,
        memory_depth=1000,
        bandwidth_mhz=100,
        has_math_channels=True,
        has_fft=True,
        has_protocol_decode=False,
        supported_decode_types=[],
        scpi_variant="standard",
        dialect="legacy",
    )
    conn = MockConnection("mock", channel_states={i: True for i in range(1, 9)})
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    # Swap in an 8-channel capability and re-create channels
    scope.model_capability = cap
    for i in range(1, 5):
        if hasattr(scope, f"channel{i}"):
            delattr(scope, f"channel{i}")
    scope._create_channels()

    assert scope.channel8._channel == 8
    assert scope.supported_channels == list(range(1, 9))
    with pytest.raises(exceptions.InvalidParameterError):
        scope.measurement.measure("PKPK", 9)

    scope.disconnect()
    assert not hasattr(scope, "channel8")  # disconnect must clear beyond channel 4
