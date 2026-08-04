"""Trigger level per source, per dialect (capability-honesty Task 6)."""

import pytest

from scpi_control import exceptions
from scpi_control.trigger import Trigger
from tests.dialect_helpers import make_dialect_scope


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
