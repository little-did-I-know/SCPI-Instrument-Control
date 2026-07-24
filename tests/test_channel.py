"""Tests for channel control module."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from scpi_control.channel import Channel
from scpi_control.exceptions import CommandError
from tests.dialect_helpers import make_dialect_scope


@pytest.fixture
def mock_scope():
    """Create a mock oscilloscope for testing."""
    return make_dialect_scope("legacy")


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
        # legacy wire tokens; the API still speaks DC/AC/GND (AUDIT M9)
        mock_scope.write.assert_called_once_with("C1:CPL D1M")

    def test_set_coupling_ac(self, channel, mock_scope):
        """Test setting AC coupling."""
        channel.coupling = "AC"
        # legacy wire tokens; the API still speaks DC/AC/GND (AUDIT M9)
        mock_scope.write.assert_called_once_with("C1:CPL A1M")

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
        # legacy wire tokens; the API still speaks DC/AC/GND (AUDIT M9)
        mock_scope.write.assert_called_once_with("C1:CPL A1M")

    def test_coupling_property_getter(self, channel, mock_scope):
        """Test coupling property getter."""
        mock_scope.query.return_value = "D1M"
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
        mock_scope.write.assert_called_once_with("BWL C1,ON")

    def test_set_bandwidth_limit_off(self, channel, mock_scope):
        """Test disabling bandwidth limit."""
        channel.bandwidth_limit = "OFF"
        mock_scope.write.assert_called_once_with("BWL C1,OFF")

    def test_set_bandwidth_limit_invalid(self, channel, mock_scope):
        """Test setting invalid bandwidth limit."""
        with pytest.raises(Exception, match="Invalid bandwidth limit"):
            channel.bandwidth_limit = "INVALID"

    def test_bandwidth_limit_property_setter(self, channel, mock_scope):
        """Test bandwidth_limit property setter."""
        channel.bandwidth_limit = "ON"
        mock_scope.write.assert_called_once_with("BWL C1,ON")

    def test_bandwidth_limit_property_getter(self, channel, mock_scope):
        """Test bandwidth_limit property getter."""
        # Documented response is the global, header-echoed "BWL <ch>,<mode>"
        # pairs form (RC01020-E01C p.27) -- not a per-channel bare token.
        mock_scope.query.return_value = "BWL C1,ON"
        assert channel.bandwidth_limit == "ON"


class TestChannelConfiguration:
    """Test getting channel configuration."""

    def test_get_configuration(self, channel, mock_scope):
        """Test getting complete channel configuration."""
        # Setup mock responses
        mock_scope.query.side_effect = [
            "C1:TRA ON",  # enabled
            "D1M",  # coupling
            "1.000E+00V",  # voltage_scale
            "0.000E+00V",  # voltage_offset
            "10",  # probe_ratio
            "BWL C1,OFF",  # bandwidth_limit
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
            "A1M",  # coupling
            "2.000E+00V",  # voltage_scale
            "1.000E+00V",  # voltage_offset
            "1",  # probe_ratio
            "BWL C1,ON",  # bandwidth_limit
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
        mock_scope.query.side_effect = ["C1:TRA ON", "D1M", "1.0E+00V", "0.0E+00V", "10", "OFF", "V"]
        assert "Channel1" in repr(channel)

    def test_repr(self, channel, mock_scope):
        """Test repr."""
        # Mock the query responses for get_configuration
        mock_scope.query.side_effect = ["C1:TRA ON", "D1M", "1.0E+00V", "0.0E+00V", "10", "OFF", "V"]
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
        # legacy wire tokens; the API still speaks DC/AC/GND (AUDIT M9)
        assert mock_scope.write.call_args[0][0] == "C3:CPL A1M"

        ch4.voltage_offset = 0.5
        assert mock_scope.write.call_args[0][0] == "C4:OFST 0.5"


class TestChannelModernDialect:
    def setup_method(self):
        self.scope = make_dialect_scope("modern")
        self.channel = Channel(self.scope, 1)

    def test_enable(self):
        self.channel.enabled = True
        self.scope.write.assert_called_once_with(":CHANnel1:SWITch ON")

    def test_set_scale(self):
        self.channel.voltage_scale = 0.5
        self.scope.write.assert_called_once_with(":CHANnel1:SCALe 0.5")

    def test_set_offset(self):
        self.channel.voltage_offset = -1.0
        self.scope.write.assert_called_once_with(":CHANnel1:OFFSet -1.0")

    def test_coupling_passthrough(self):
        self.channel.coupling = "AC"
        self.scope.write.assert_called_once_with(":CHANnel1:COUPling AC")

    def test_get_coupling(self):
        self.scope.query.return_value = "GND"
        assert self.channel.coupling == "GND"

    def test_probe_ratio(self):
        self.channel.probe_ratio = 10
        self.scope.write.assert_called_once_with(":CHANnel1:PROBe VALue,10")

    def test_bandwidth_limit_on_maps_to_20m(self):
        self.channel.bandwidth_limit = "ON"
        self.scope.write.assert_called_once_with(":CHANnel1:BWLimit 20M")

    def test_bandwidth_limit_off_maps_to_full(self):
        self.channel.bandwidth_limit = "OFF"
        self.scope.write.assert_called_once_with(":CHANnel1:BWLimit FULL")

    def test_get_bandwidth_limit_maps_back(self):
        self.scope.query.return_value = "20M"
        assert self.channel.bandwidth_limit == "ON"


class TestChannelLegacyCouplingTokens:
    def setup_method(self):
        self.scope = make_dialect_scope("legacy")
        self.channel = Channel(self.scope, 1)

    def test_dc_maps_to_d1m(self):
        self.channel.coupling = "DC"
        self.scope.write.assert_called_once_with("C1:CPL D1M")

    def test_get_coupling_maps_a1m_to_ac(self):
        self.scope.query.return_value = "A1M"
        assert self.channel.coupling == "AC"
