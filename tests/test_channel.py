"""Tests for channel control module."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from siglent.channel import Channel
from siglent.exceptions import CommandError


@pytest.fixture
def mock_scope():
    """Create a mock oscilloscope for testing."""
    scope = Mock()
    scope.write = Mock()
    scope.query = Mock()
    return scope


@pytest.fixture
def channel(mock_scope):
    """Create a channel instance for testing."""
    return Channel(mock_scope, 1)


class TestChannelInitialization:
    """Test channel initialization."""

    def test_channel_number_valid(self, mock_scope):
        """Test valid channel numbers."""
        for i in range(1, 5):
            channel = Channel(mock_scope, i)
            assert channel._channel == i

    def test_channel_number_invalid(self, mock_scope):
        """Test invalid channel numbers."""
        with pytest.raises(Exception, match="Invalid channel number"):
            Channel(mock_scope, 0)

        with pytest.raises(Exception, match="Invalid channel number"):
            Channel(mock_scope, 5)


class TestChannelEnable:
    """Test channel enable/disable."""

    def test_enable(self, channel, mock_scope):
        """Test enabling a channel."""
        channel.enable()
        mock_scope.write.assert_called_once_with("C1:TRA ON")

    def test_disable(self, channel, mock_scope):
        """Test disabling a channel."""
        channel.disable()
        mock_scope.write.assert_called_once_with("C1:TRA OFF")

    def test_enabled_property_true(self, channel, mock_scope):
        """Test reading enabled state when ON."""
        mock_scope.query.return_value = "C1:TRA ON"
        assert channel.enabled is True
        mock_scope.query.assert_called_once_with("C1:TRA?")

    def test_enabled_property_false(self, channel, mock_scope):
        """Test reading enabled state when OFF."""
        mock_scope.query.return_value = "C1:TRA OFF"
        assert channel.enabled is False

    def test_enabled_property_alternate_format(self, channel, mock_scope):
        """Test reading enabled state with alternate response format."""
        mock_scope.query.return_value = "TRACE ON"
        assert channel.enabled is True


class TestVoltageScale:
    """Test voltage scale (volts/div) control."""

    def test_set_voltage_scale(self, channel, mock_scope):
        """Test setting voltage scale."""
        channel.set_scale(2.0)
        mock_scope.write.assert_called_once_with("C1:VDIV 2.0")

    def test_voltage_scale_property_setter(self, channel, mock_scope):
        """Test voltage_scale property setter."""
        channel.voltage_scale = 1.5
        mock_scope.write.assert_called_once_with("C1:VDIV 1.5")

    def test_voltage_scale_property_getter(self, channel, mock_scope):
        """Test voltage_scale property getter."""
        mock_scope.query.return_value = "C1:VDIV 1.000E+00V"
        assert channel.voltage_scale == 1.0
        mock_scope.query.assert_called_once_with("C1:VDIV?")

    def test_set_scale_invalid_value(self, channel, mock_scope):
        """Test setting invalid voltage scale."""
        with pytest.raises(Exception, match="Voltage scale must be positive"):
            channel.set_scale(0)

        with pytest.raises(Exception, match="Voltage scale must be positive"):
            channel.set_scale(-1.0)


class TestVoltageOffset:
    """Test voltage offset control."""

    def test_set_offset(self, channel, mock_scope):
        """Test setting voltage offset."""
        channel.voltage_offset = 0.5
        mock_scope.write.assert_called_once_with("C1:OFST 0.5")

    def test_voltage_offset_property_setter(self, channel, mock_scope):
        """Test voltage_offset property setter."""
        channel.voltage_offset = -0.5
        mock_scope.write.assert_called_once_with("C1:OFST -0.5")

    def test_voltage_offset_property_getter(self, channel, mock_scope):
        """Test voltage_offset property getter."""
        mock_scope.query.return_value = "C1:OFST 5.000E-01V"
        assert channel.voltage_offset == 0.5
        mock_scope.query.assert_called_once_with("C1:OFST?")


class TestCoupling:
    """Test coupling mode control."""

    def test_set_coupling_dc(self, channel, mock_scope):
        """Test setting DC coupling."""
        channel.coupling = "DC"
        mock_scope.write.assert_called_once_with("C1:CPL DC")

    def test_set_coupling_ac(self, channel, mock_scope):
        """Test setting AC coupling."""
        channel.coupling = "AC"
        mock_scope.write.assert_called_once_with("C1:CPL AC")

    def test_set_coupling_ground(self, channel, mock_scope):
        """Test setting GND coupling."""
        channel.coupling = "GND"
        mock_scope.write.assert_called_once_with("C1:CPL GND")

    def test_set_coupling_invalid(self, channel, mock_scope):
        """Test setting invalid coupling mode."""
        with pytest.raises(Exception, match="Invalid coupling mode"):
            channel.coupling = "INVALID"

    def test_coupling_property_setter(self, channel, mock_scope):
        """Test coupling property setter."""
        channel.coupling = "AC"
        mock_scope.write.assert_called_once_with("C1:CPL AC")

    def test_coupling_property_getter(self, channel, mock_scope):
        """Test coupling property getter."""
        mock_scope.query.return_value = "DC"
        assert channel.coupling == "DC"


class TestProbeRatio:
    """Test probe attenuation ratio control."""

    def test_set_probe_ratio(self, channel, mock_scope):
        """Test setting probe ratio."""
        channel.probe_ratio = 10
        mock_scope.write.assert_called_once_with("C1:ATTN 10")

    def test_probe_ratio_property_setter(self, channel, mock_scope):
        """Test probe_ratio property setter."""
        channel.probe_ratio = 100
        mock_scope.write.assert_called_once_with("C1:ATTN 100")

    def test_probe_ratio_property_getter(self, channel, mock_scope):
        """Test probe_ratio property getter."""
        mock_scope.query.return_value = "C1:ATTN 10"
        assert channel.probe_ratio == 10.0

    def test_probe_ratio_invalid(self, channel, mock_scope):
        """Test setting invalid probe ratio."""
        with pytest.raises(Exception, match="Probe ratio must be positive"):
            channel.probe_ratio = 0

        with pytest.raises(Exception, match="Probe ratio must be positive"):
            channel.probe_ratio = -10


class TestBandwidthLimit:
    """Test bandwidth limiting control."""

    def test_set_bandwidth_limit_on(self, channel, mock_scope):
        """Test enabling bandwidth limit."""
        channel.bandwidth_limit = "ON"
        mock_scope.write.assert_called_once_with("C1:BWL ON")

    def test_set_bandwidth_limit_off(self, channel, mock_scope):
        """Test disabling bandwidth limit."""
        channel.bandwidth_limit = "OFF"
        mock_scope.write.assert_called_once_with("C1:BWL OFF")

    def test_set_bandwidth_limit_invalid(self, channel, mock_scope):
        """Test setting invalid bandwidth limit."""
        with pytest.raises(Exception, match="Invalid bandwidth limit"):
            channel.bandwidth_limit = "INVALID"

    def test_bandwidth_limit_property_setter(self, channel, mock_scope):
        """Test bandwidth_limit property setter."""
        channel.bandwidth_limit = "ON"
        mock_scope.write.assert_called_once_with("C1:BWL ON")

    def test_bandwidth_limit_property_getter(self, channel, mock_scope):
        """Test bandwidth_limit property getter."""
        mock_scope.query.return_value = "ON"
        assert channel.bandwidth_limit == "ON"


class TestChannelConfiguration:
    """Test getting channel configuration."""

    def test_get_configuration(self, channel, mock_scope):
        """Test getting complete channel configuration."""
        # Setup mock responses
        mock_scope.query.side_effect = [
            "C1:TRA ON",  # enabled
            "DC",  # coupling
            "1.000E+00V",  # voltage_scale
            "0.000E+00V",  # voltage_offset
            "10",  # probe_ratio
            "OFF",  # bandwidth_limit
            "V",  # unit
        ]

        config = channel.get_configuration()

        assert config["channel"] == 1
        assert config["enabled"] is True
        assert config["voltage_scale"] == 1.0
        assert config["voltage_offset"] == 0.0
        assert config["coupling"] == "DC"
        assert config["probe_ratio"] == 10.0
        assert config["bandwidth_limit"] == "OFF"
        assert config["unit"] == "V"

    def test_get_configuration_disabled_channel(self, channel, mock_scope):
        """Test getting configuration of disabled channel."""
        mock_scope.query.side_effect = [
            "C1:TRA OFF",  # enabled
            "AC",  # coupling
            "2.000E+00V",  # voltage_scale
            "1.000E+00V",  # voltage_offset
            "1",  # probe_ratio
            "ON",  # bandwidth_limit
            "V",  # unit
        ]

        config = channel.get_configuration()

        assert config["enabled"] is False
        assert config["coupling"] == "AC"
        assert config["bandwidth_limit"] == "ON"


class TestChannelStringRepresentation:
    """Test string representation."""

    def test_str(self, channel, mock_scope):
        """Test string representation."""
        # Mock the query responses for get_configuration
        mock_scope.query.side_effect = ["C1:TRA ON", "DC", "1.0E+00V", "0.0E+00V", "10", "OFF", "V"]
        assert "Channel1" in repr(channel)

    def test_repr(self, channel, mock_scope):
        """Test repr."""
        # Mock the query responses for get_configuration
        mock_scope.query.side_effect = ["C1:TRA ON", "DC", "1.0E+00V", "0.0E+00V", "10", "OFF", "V"]
        assert "Channel1" in repr(channel)


class TestMultipleChannels:
    """Test multiple channel instances."""

    def test_different_channels(self, mock_scope):
        """Test that different channels send correct commands."""
        ch1 = Channel(mock_scope, 1)
        ch2 = Channel(mock_scope, 2)
        ch3 = Channel(mock_scope, 3)
        ch4 = Channel(mock_scope, 4)

        ch1.enable()
        assert mock_scope.write.call_args[0][0] == "C1:TRA ON"

        ch2.set_scale(2.0)
        assert mock_scope.write.call_args[0][0] == "C2:VDIV 2.0"

        ch3.coupling = "AC"
        assert mock_scope.write.call_args[0][0] == "C3:CPL AC"

        ch4.voltage_offset = 0.5
        assert mock_scope.write.call_args[0][0] == "C4:OFST 0.5"
