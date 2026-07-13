"""Comprehensive tests for trigger control module."""

from unittest.mock import MagicMock, Mock

import pytest

from scpi_control.exceptions import CommandError
from scpi_control.trigger import Trigger
from tests.dialect_helpers import make_dialect_scope


@pytest.fixture
def mock_scope():
    """Create a mock oscilloscope for testing."""
    return make_dialect_scope("legacy")


@pytest.fixture
def trigger(mock_scope):
    """Create a trigger instance for testing."""
    return Trigger(mock_scope)


class TestTriggerMode:
    """Test trigger mode control."""

    def test_set_mode_auto(self, trigger, mock_scope):
        """Test setting AUTO trigger mode."""
        trigger.set_mode("AUTO")
        mock_scope.write.assert_called_with("TRIG_MODE AUTO")

    def test_set_mode_normal(self, trigger, mock_scope):
        """Test setting NORMAL trigger mode."""
        trigger.set_mode("NORMAL")
        mock_scope.write.assert_called_with("TRIG_MODE NORM")

    def test_set_mode_single(self, trigger, mock_scope):
        """Test setting SINGLE trigger mode."""
        trigger.set_mode("SINGLE")
        mock_scope.write.assert_called_with("TRIG_MODE SINGLE")

    def test_set_mode_stop(self, trigger, mock_scope):
        """Test setting STOP trigger mode."""
        trigger.set_mode("STOP")
        # STOP is routed through the dedicated legacy STOP command, not TRIG_MODE
        mock_scope.write.assert_called_with("STOP")

    def test_set_mode_invalid(self, trigger, mock_scope):
        """Test setting invalid trigger mode."""
        with pytest.raises(Exception, match="Invalid trigger mode"):
            trigger.set_mode("INVALID")

    def test_mode_property_setter(self, trigger, mock_scope):
        """Test mode property setter."""
        trigger.mode = "NORMAL"
        mock_scope.write.assert_called_with("TRIG_MODE NORM")

    def test_mode_property_getter(self, trigger, mock_scope):
        """Test mode property getter."""
        mock_scope.query.return_value = "NORM"
        assert trigger.mode == "NORM"
        mock_scope.query.assert_called_with("TRIG_MODE?")


class TestTriggerSource:
    """Test trigger source control."""

    def test_set_source_channel1(self, trigger, mock_scope):
        """Test setting trigger source to channel 1."""
        mock_scope.query.return_value = "EDGE,SR,C1"  # Mock current type
        trigger.set_source("C1")
        mock_scope.write.assert_called_with("TRIG_SELECT EDGE,SR,C1")

    def test_set_source_channel2(self, trigger, mock_scope):
        """Test setting trigger source to channel 2."""
        mock_scope.query.return_value = "EDGE,SR,C2"  # Mock current type
        trigger.set_source("C2")
        mock_scope.write.assert_called_with("TRIG_SELECT EDGE,SR,C2")

    def test_set_source_external(self, trigger, mock_scope):
        """Test setting trigger source to external."""
        mock_scope.query.return_value = "EDGE,SR,EX"  # Mock current type
        trigger.set_source("EX")
        mock_scope.write.assert_called_with("TRIG_SELECT EDGE,SR,EX")

    def test_set_source_line(self, trigger, mock_scope):
        """Test setting trigger source to line."""
        mock_scope.query.return_value = "EDGE,SR,LINE"  # Mock current type
        trigger.set_source("LINE")
        mock_scope.write.assert_called_with("TRIG_SELECT EDGE,SR,LINE")

    def test_set_source_invalid(self, trigger, mock_scope):
        """Test setting invalid trigger source."""
        with pytest.raises(Exception, match="Invalid trigger source"):
            trigger.set_source("INVALID")

    def test_source_property_setter(self, trigger, mock_scope):
        """Test source property setter."""
        mock_scope.query.return_value = "EDGE,SR,C2"  # Mock current type
        trigger.source = "C2"
        mock_scope.write.assert_called_with("TRIG_SELECT EDGE,SR,C2")

    def test_source_property_getter(self, trigger, mock_scope):
        """Test source property getter."""
        mock_scope.query.return_value = "EDGE,SR,C1"
        assert trigger.source == "C1"
        mock_scope.query.assert_called_with("TRIG_SELECT?")


class TestTriggerLevel:
    """Test trigger level control."""

    def test_set_level_channel1(self, trigger, mock_scope):
        """Test setting trigger level for channel 1."""
        # set_level first sets source, then level
        mock_scope.query.return_value = "EDGE,SR,C1"  # Mock current type for source setter
        trigger.set_level(1, 1.5)
        # Check that level was set (last write call)
        calls = [str(call) for call in mock_scope.write.call_args_list]
        assert any("C1:TRIG_LEVEL 1.5" in call or "C1:TRLV 1.5" in call for call in calls)

    def test_set_level_channel2(self, trigger, mock_scope):
        """Test setting trigger level for channel 2."""
        mock_scope.query.return_value = "EDGE,SR,C2"  # Mock current type for source setter
        trigger.set_level(2, -0.5)
        calls = [str(call) for call in mock_scope.write.call_args_list]
        assert any("C2:TRIG_LEVEL -0.5" in call or "C2:TRLV -0.5" in call for call in calls)

    def test_set_level_invalid_channel(self, trigger, mock_scope):
        """Test setting trigger level with invalid channel."""
        with pytest.raises(Exception):
            trigger.set_level(0, 1.0)

        with pytest.raises(Exception):
            trigger.set_level(5, 1.0)

    def test_level_property_setter(self, trigger, mock_scope):
        """Test level property setter."""
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.level = 2.0
        # Should have made a write call
        assert mock_scope.write.called

    def test_level_property_getter(self, trigger, mock_scope):
        """Test level property getter."""
        mock_scope.query.side_effect = ["EDGE,SR,C1", "1.500E+00V"]
        level = trigger.level
        assert isinstance(level, (int, float))


class TestTriggerSlope:
    """Test trigger slope/edge control."""

    def test_set_slope_positive(self, trigger, mock_scope):
        """Test setting positive (rising) edge."""
        # routed per-source; bare TRIG_SLOPE/TRIG_COUPLING were invalid on hardware (AUDIT H1)
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.slope = "POS"
        mock_scope.write.assert_called_with("C1:TRSL POS")

    def test_set_slope_negative(self, trigger, mock_scope):
        """Test setting negative (falling) edge."""
        # routed per-source; bare TRIG_SLOPE/TRIG_COUPLING were invalid on hardware (AUDIT H1)
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.slope = "NEG"
        mock_scope.write.assert_called_with("C1:TRSL NEG")

    def test_set_slope_invalid(self, trigger, mock_scope):
        """Test setting invalid slope."""
        with pytest.raises(Exception, match="Invalid trigger slope"):
            trigger.slope = "INVALID"

    def test_slope_property_setter(self, trigger, mock_scope):
        """Test slope property setter."""
        # routed per-source; bare TRIG_SLOPE/TRIG_COUPLING were invalid on hardware (AUDIT H1)
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.slope = "NEG"
        mock_scope.write.assert_called_with("C1:TRSL NEG")

    def test_slope_property_getter(self, trigger, mock_scope):
        """Test slope property getter."""
        mock_scope.query.side_effect = ["EDGE,SR,C1", "POS"]
        assert trigger.slope == "POS"
        mock_scope.query.assert_called_with("C1:TRSL?")


class TestEdgeTrigger:
    """Test edge trigger setup."""

    def test_set_edge_trigger_defaults(self, trigger, mock_scope):
        """Test setting edge trigger with default parameters."""
        # slope setter now looks up the source; mock_scope reflects it as C1
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.set_edge_trigger(source="C1", slope="POS")

        calls = mock_scope.write.call_args_list
        assert len(calls) >= 2
        # Check that source and slope commands were sent
        commands = [call[0][0] for call in calls]
        assert any("TRIG_SELECT EDGE,SR,C1" in cmd for cmd in commands)
        # routed per-source; bare TRIG_SLOPE/TRIG_COUPLING were invalid on hardware (AUDIT H1)
        assert any("C1:TRSL POS" in cmd for cmd in commands)

    def test_set_edge_trigger_with_slope(self, trigger, mock_scope):
        """Test setting edge trigger with slope."""
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.set_edge_trigger(source="C1", slope="POS")

        # Should set source and slope
        assert mock_scope.write.call_count >= 2

    def test_set_edge_trigger_channel2(self, trigger, mock_scope):
        """Test setting edge trigger on channel 2."""
        # slope setter now looks up the source; mock_scope reflects it as C2
        mock_scope.query.return_value = "EDGE,SR,C2"
        trigger.set_edge_trigger(source="C2", slope="NEG")

        calls = mock_scope.write.call_args_list
        commands = [call[0][0] for call in calls]
        assert any("TRIG_SELECT EDGE,SR,C2" in cmd for cmd in commands)
        # routed per-source; bare TRIG_SLOPE/TRIG_COUPLING were invalid on hardware (AUDIT H1)
        assert any("C2:TRSL NEG" in cmd for cmd in commands)


class TestTriggerActions:
    """Test trigger action commands."""

    def test_single(self, trigger, mock_scope):
        """Test single trigger."""
        trigger.single()
        mock_scope.write.assert_called_with("TRIG_MODE SINGLE")

    def test_force(self, trigger, mock_scope):
        """Test force trigger."""
        trigger.force()
        mock_scope.write.assert_called_with("FRTR")

    def test_auto(self, trigger, mock_scope):
        """Test auto trigger."""
        trigger.auto()
        mock_scope.write.assert_called_with("TRIG_MODE AUTO")


class TestTriggerProperties:
    """Test additional trigger properties."""

    def test_trigger_type_getter(self, trigger, mock_scope):
        """Test getting trigger type."""
        mock_scope.query.return_value = "EDGE,SR,C1"
        assert trigger.trigger_type == "EDGE"

    def test_trigger_type_setter(self, trigger, mock_scope):
        """Test setting trigger type."""
        mock_scope.query.return_value = "EDGE,SR,C1"  # Mock current source
        trigger.trigger_type = "EDGE"
        mock_scope.write.assert_called_with("TRIG_SELECT EDGE,SR,C1")


class TestMultipleTriggerSettings:
    """Test setting multiple trigger parameters."""

    def test_configure_trigger_sequence(self, trigger, mock_scope):
        """Test configuring trigger with multiple settings."""
        # Set mode
        trigger.mode = "NORMAL"

        # Set source
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.source = "C1"

        # Set slope
        trigger.slope = "POS"

        # Set level
        mock_scope.query.return_value = "EDGE,SR,C1"
        trigger.set_level(1, 1.5)

        # Verify all commands were sent
        assert mock_scope.write.call_count >= 4

    def test_trigger_workflow(self, trigger, mock_scope):
        """Test a complete trigger configuration workflow."""
        # slope setter now looks up the source; mock_scope reflects it as C2
        mock_scope.query.return_value = "EDGE,SR,C2"
        # Configure edge trigger
        trigger.set_edge_trigger(source="C2", slope="NEG")

        # Set to normal mode
        trigger.set_mode("NORMAL")

        # Force a trigger
        trigger.force()

        # Verify commands were sent in sequence
        assert mock_scope.write.call_count >= 4


class TestTriggerModernDialect:
    def setup_method(self):
        self.scope = make_dialect_scope("modern")
        self.trigger = Trigger(self.scope)

    def test_set_mode_normal(self):
        self.trigger.mode = "NORM"
        self.scope.write.assert_called_once_with(":TRIGger:MODE NORMal")

    def test_set_mode_stop_uses_stop_command(self):
        self.trigger.mode = "STOP"
        self.scope.write.assert_called_once_with(":TRIGger:STOP")

    def test_get_mode_normalizes_mixed_case(self):
        self.scope.query.side_effect = ["Ready", "SINGle"]  # status first, then mode
        assert self.trigger.mode == "SINGLE"

    def test_get_mode_reports_stop_from_status(self):
        self.scope.query.side_effect = ["Stop"]
        assert self.trigger.mode == "STOP"

    def test_set_source(self):
        self.trigger.source = "C2"
        self.scope.write.assert_called_once_with(":TRIGger:EDGE:SOURce C2")

    def test_get_source(self):
        self.scope.query.return_value = "C1"
        assert self.trigger.source == "C1"
        self.scope.query.assert_called_once_with(":TRIGger:EDGE:SOURce?")

    def test_set_slope_maps_tokens(self):
        self.trigger.slope = "NEG"
        self.scope.write.assert_called_once_with(":TRIGger:EDGE:SLOPe FALLing")

    def test_get_slope_maps_back(self):
        self.scope.query.return_value = "RISing"
        assert self.trigger.slope == "POS"

    def test_set_level(self):
        self.trigger.level = 0.5
        self.scope.write.assert_called_once_with(":TRIGger:EDGE:LEVel 0.5")

    def test_set_coupling(self):
        self.trigger.coupling = "AC"
        self.scope.write.assert_called_once_with(":TRIGger:EDGE:COUPling AC")

    def test_get_coupling_maps_reject_tokens_back(self):
        self.scope.query.return_value = "HFREJect"
        assert self.trigger.coupling == "HFREJ"

    def test_force(self):
        self.trigger.force()
        self.scope.write.assert_called_once_with(":TRIGger:MODE FTRIG")


class TestTriggerLegacyRouted:
    def setup_method(self):
        self.scope = make_dialect_scope("legacy")
        self.trigger = Trigger(self.scope)

    def test_set_slope_is_per_source(self):
        self.scope.query.return_value = "EDGE,SR,C1"
        self.trigger.slope = "POS"
        self.scope.write.assert_called_once_with("C1:TRSL POS")

    def test_set_coupling_is_per_source(self):
        self.scope.query.return_value = "EDGE,SR,C2"
        self.trigger.coupling = "DC"
        self.scope.write.assert_called_once_with("C2:TRCP DC")

    def test_set_mode_passthrough(self):
        self.trigger.mode = "NORM"
        self.scope.write.assert_called_once_with("TRIG_MODE NORM")


class TestTriggerStringRepresentation:
    """Test string representation."""

    def test_str(self, trigger):
        """Test string representation."""
        assert "Trigger" in str(trigger)

    def test_repr(self, trigger):
        """Test repr."""
        assert "Trigger" in repr(trigger)
