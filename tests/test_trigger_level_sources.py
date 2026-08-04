"""Trigger level per source, per dialect (capability-honesty Task 6)."""

import pytest

from scpi_control import exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.trigger import Trigger
from tests.dialect_helpers import make_dialect_scope
from tests.test_dialect_connect import LEGACY_IDN
from tests.test_mock_dialects import LECROY_IDN


def make_legacy_scope():
    conn = MockConnection("mock", idn=LEGACY_IDN)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def make_lecroy_scope():
    conn = MockConnection("mock", idn=LECROY_IDN)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def trigger_with_source(dialect, source):
    scope = make_dialect_scope(dialect)
    # Flat dialects read the source out of TRIG_SELECT; give them one.
    scope.query.return_value = f"EDGE,SR,{source},HT,OFF"
    trigger = Trigger(scope)
    return scope, trigger


class TestFlatDialectsGainTheExternalInputs:
    @pytest.mark.parametrize("dialect", ["legacy", "lecroy"])
    @pytest.mark.parametrize("source", ["EX", "EX5"])
    def test_setting_the_level_reaches_the_wire(self, dialect, source):
        # RC01020-E01C p.128 / MAUI p.7-33: EX and EX5 are documented level
        # sources. The old startswith("C") check silently dropped these writes.
        scope, trigger = trigger_with_source(dialect, source)
        trigger.level = 1.5
        assert any(f"{source}:TRLV" in str(call) for call in scope.write.call_args_list)

    @pytest.mark.parametrize("dialect", ["legacy", "lecroy"])
    def test_reading_the_level_queries_the_external_input(self, dialect):
        scope, trigger = trigger_with_source(dialect, "EX")
        scope.query.side_effect = ["EDGE,SR,EX,HT,OFF", "1.50E+00"]
        assert trigger.level == pytest.approx(1.5)
        # Pin the wire form: a driver that wrongly queried C1:TRLV? would
        # still return a number here, so the value alone doesn't prove it
        # asked about the right source.
        assert scope.query.call_args_list[-1].args[0] == "EX:TRLV?"


class TestLineHasNoLevel:
    @pytest.mark.parametrize("dialect", ["legacy", "lecroy"])
    def test_setting_raises_instead_of_silently_dropping(self, dialect):
        scope, trigger = trigger_with_source(dialect, "LINE")
        with pytest.raises(exceptions.FeatureNotSupportedError):
            trigger.level = 1.0
        scope.write.assert_not_called()

    @pytest.mark.parametrize("dialect", ["legacy", "lecroy"])
    def test_reading_raises_instead_of_fabricating_zero(self, dialect):
        # This used to return 0.0 -- a number that looks like a real level.
        scope, trigger = trigger_with_source(dialect, "LINE")
        with pytest.raises(exceptions.FeatureNotSupportedError):
            trigger.level


class TestTektronixExternalSourceGates:
    def test_setting_raises_for_an_external_source(self):
        # No AUX level command in the 4/5/6 MSO manual.
        scope = make_dialect_scope("tektronix")
        scope.query.return_value = "EX"
        trigger = Trigger(scope)
        with pytest.raises(exceptions.FeatureNotSupportedError):
            trigger.level = 1.0
        scope.write.assert_not_called()

    def test_channel_sources_are_unaffected(self):
        scope = make_dialect_scope("tektronix")
        scope.query.return_value = "C2"
        Trigger(scope).level = 1.0
        assert any("TRIGger:A:LEVel:CH2" in str(c) for c in scope.write.call_args_list)


class TestModernIsUnchanged:
    @pytest.mark.parametrize("source", ["C1", "EX", "LINE"])
    def test_level_is_source_independent(self, source):
        # EN11G p.493: the command takes no source, so nothing gates here.
        scope = make_dialect_scope("modern")
        scope.query.return_value = source
        Trigger(scope).level = 0.5
        assert any(":TRIGger:EDGE:LEVel" in str(c) for c in scope.write.call_args_list)


class TestGetConfigurationDegradesGracefully:
    def test_line_source_omits_level_but_keeps_the_rest(self):
        # get_configuration() must not let one ungated field (level) take the
        # whole trigger dump down -- mode/type/source/slope/coupling/holdoff
        # should still report even when the source has no level command.
        scope = make_dialect_scope("legacy")
        responses = {
            "TRIG_MODE?": "AUTO",
            "TRIG_SELECT?": "EDGE,SR,LINE,HT,OFF",
            "LINE:TRSL?": "POS",
            "LINE:TRCP?": "DC",
            "TRIG_DELAY?": "TRIG_DELAY 0.0E+00S",
        }
        scope.query.side_effect = lambda cmd: responses[cmd]

        config = Trigger(scope).get_configuration()

        assert config["level"] is None
        assert config["mode"] == "AUTO"
        assert config["type"] == "EDGE"
        assert config["source"] == "LINE"
        assert config["slope"] == "POS"
        assert config["coupling"] == "DC"
        assert config["holdoff"] == pytest.approx(0.0)


class TestMockHandlesExternalTriggerLevel:
    @pytest.mark.parametrize("source", ["EX", "EX5"])
    def test_external_level_round_trips_through_the_mock(self, source):
        # _format_scientific(1.5, "V") == "1.50E+00V" -- the same shape the
        # channel handler returns, so one driver parser handles both.
        scope, conn = make_legacy_scope()
        conn.error_queue.clear()
        conn.write(f"{source}:TRLV 1.5")
        assert conn.error_queue == []
        assert conn.query(f"{source}:TRLV?").strip() == "1.50E+00V"

    def test_ex5_is_not_swallowed_by_the_ex_pattern(self):
        # "EX5" must be tried before "EX", or EX matches and leaves a stray 5.
        scope, conn = make_legacy_scope()
        conn.write("EX:TRLV 1.0")
        conn.write("EX5:TRLV 2.0")
        assert conn.query("EX:TRLV?").strip() == "1.00E+00V"
        assert conn.query("EX5:TRLV?").strip() == "2.00E+00V"

    def test_channel_levels_are_independent_of_the_external_ones(self):
        scope, conn = make_legacy_scope()
        conn.write("C1:TRLV 0.5")
        conn.write("EX:TRLV 2.5")
        assert conn.query("C1:TRLV?").strip() == "5.00E-01V"
        assert conn.query("EX:TRLV?").strip() == "2.50E+00V"


class TestLecroyMockHandlesExternalTriggerLevel:
    # LeCroy's mock answers CHDR OFF: bare values, no unit suffix
    # (_format_nr3), unlike the legacy Siglent chain's "V"-suffixed replies.
    @pytest.mark.parametrize("source", ["EX", "EX5"])
    def test_external_level_round_trips_through_the_mock(self, source):
        scope, conn = make_lecroy_scope()
        conn.error_queue.clear()
        conn.write(f"{source}:TRLV 1.5")
        assert conn.error_queue == []
        assert conn.query(f"{source}:TRLV?").strip() == "1.50E+00"

    def test_ex5_is_not_swallowed_by_the_ex_pattern(self):
        scope, conn = make_lecroy_scope()
        conn.write("EX:TRLV 1.0")
        conn.write("EX5:TRLV 2.0")
        assert conn.query("EX:TRLV?").strip() == "1.00E+00"
        assert conn.query("EX5:TRLV?").strip() == "2.00E+00"

    def test_channel_levels_are_independent_of_the_external_ones(self):
        scope, conn = make_lecroy_scope()
        conn.write("C1:TRLV 0.5")
        conn.write("EX:TRLV 2.5")
        assert conn.query("C1:TRLV?").strip() == "5.00E-01"
        assert conn.query("EX:TRLV?").strip() == "2.50E+00"
