"""Unit tests for FunctionGenerator class and related modules."""

import pytest

from scpi_control import FunctionGenerator
from scpi_control.awg_models import (
    AWGCapability,
    ChannelSpec,
    create_generic_awg_capability,
    detect_awg_from_idn,
)
from scpi_control.awg_scpi_commands import AWGSCPICommandSet
from scpi_control.connection.mock import MockConnection


class TestAWGModels:
    """Test AWG model detection and capabilities."""

    def test_detect_siglent_sdg1032x(self):
        """Test detection of Siglent SDG1032X."""
        idn = "Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1"
        cap = detect_awg_from_idn(idn)

        assert cap.model_name == "SDG1032X"
        assert cap.manufacturer == "Siglent"
        assert cap.num_channels == 2
        assert cap.scpi_variant == "siglent_sdg"
        assert cap.has_modulation is True
        assert cap.has_arbitrary is True

    def test_detect_siglent_sdg2122x(self):
        """Test detection of Siglent SDG2122X."""
        idn = "Siglent Technologies,SDG2122X,SDG2XXXXX,1.0"
        cap = detect_awg_from_idn(idn)

        assert cap.model_name == "SDG2122X"
        assert cap.num_channels == 2
        assert cap.scpi_variant == "siglent_sdg"
        assert cap.channel_specs[0].max_frequency == 120e6

    def test_detect_generic_awg(self):
        """Test detection of generic/unknown AWG."""
        idn = "Keysight Technologies,33500B,MY000000,1.0.0"
        cap = detect_awg_from_idn(idn)

        assert cap.model_name == "33500B"
        assert cap.manufacturer == "Keysight Technologies"
        assert cap.scpi_variant == "generic"
        assert cap.num_channels == 1  # Conservative default

    def test_channel_spec_string(self):
        """Test ChannelSpec string representation."""
        spec = ChannelSpec(1, 30e6, 20.0, 0.002, 10.0, 1e-6, 0.001)
        assert "Ch1" in str(spec)
        assert "30" in str(spec)  # Frequency in MHz


class TestAWGSCPICommandSet:
    """Test SCPI command generation."""

    def test_generic_commands(self):
        """Test generic SCPI-99 command generation."""
        cmd_set = AWGSCPICommandSet("generic")

        assert cmd_set.get_command("identify") == "*IDN?"
        assert cmd_set.get_command("reset") == "*RST"
        assert (
            cmd_set.get_command("set_frequency", ch=1, frequency=1000.0)
            == "SOUR1:FREQ 1000.0"
        )
        assert cmd_set.get_command("get_frequency", ch=1) == "SOUR1:FREQ?"

    def test_siglent_sdg_commands(self):
        """Test Siglent SDG command overrides."""
        cmd_set = AWGSCPICommandSet("siglent_sdg")

        assert (
            cmd_set.get_command("set_function", ch=1, function="SINE")
            == "C1:BSWV WVTP,SINE"
        )
        assert (
            cmd_set.get_command("set_frequency", ch=1, frequency=1000.0)
            == "C1:BSWV FRQ,1000.0"
        )
        assert (
            cmd_set.get_command("set_amplitude", ch=1, amplitude=5.0)
            == "C1:BSWV AMP,5.0"
        )
        assert cmd_set.get_command("set_output", ch=1, state="ON") == "C1:OUTP ON"

    def test_fallback_to_generic(self):
        """Test that Siglent variant falls back to generic for unknown commands."""
        cmd_set = AWGSCPICommandSet("siglent_sdg")

        # System commands should still use generic
        assert cmd_set.get_command("identify") == "*IDN?"
        assert cmd_set.get_command("reset") == "*RST"

    def test_unknown_command(self):
        """Test that unknown command raises KeyError."""
        cmd_set = AWGSCPICommandSet("generic")

        with pytest.raises(KeyError):
            cmd_set.get_command("nonexistent_command")

    def test_missing_parameter(self):
        """Test that missing parameter raises ValueError."""
        cmd_set = AWGSCPICommandSet("generic")

        with pytest.raises(ValueError):
            cmd_set.get_command("set_frequency", ch=1)  # Missing frequency parameter


class TestFunctionGeneratorConnection:
    """Test FunctionGenerator connection and initialization."""

    @pytest.fixture
    def mock_awg(self):
        """Create mock AWG connection."""
        conn = MockConnection(
            awg_mode=True,
            awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1",
        )
        awg = FunctionGenerator("mock", connection=conn)
        awg.connect()
        return awg

    def test_awg_connection(self, mock_awg):
        """Test AWG connects and initializes."""
        assert mock_awg.is_connected
        assert mock_awg.model_capability is not None
        assert mock_awg.model_capability.model_name == "SDG1032X"

    def test_awg_identification(self, mock_awg):
        """Test AWG identification."""
        idn = mock_awg.identify()
        assert "SDG1032X" in idn
        assert "Siglent" in idn

    def test_awg_device_info(self, mock_awg):
        """Test parsed device info."""
        info = mock_awg.device_info
        assert info["manufacturer"] == "Siglent"
        assert info["model"] == "SDG1032X"

    def test_awg_channels_created(self, mock_awg):
        """Test that channels are created dynamically."""
        assert hasattr(mock_awg, "channel1")
        assert hasattr(mock_awg, "channel2")
        assert mock_awg.supported_channels == [1, 2]

    def test_awg_disconnect(self, mock_awg):
        """Test AWG disconnection."""
        mock_awg.disconnect()
        assert not mock_awg.is_connected
        assert mock_awg.model_capability is None

    def test_awg_context_manager(self):
        """Test AWG as context manager."""
        conn = MockConnection(
            awg_mode=True,
            awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1",
        )
        with FunctionGenerator("mock", connection=conn) as awg:
            assert awg.is_connected
            assert awg.model_capability is not None

        # Should disconnect automatically
        assert not conn.is_connected


class TestAWGOutput:
    """Test AWGOutput control."""

    @pytest.fixture
    def mock_awg(self):
        """Create mock AWG connection."""
        conn = MockConnection(
            awg_mode=True,
            awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1",
        )
        awg = FunctionGenerator("mock", connection=conn)
        awg.connect()
        return awg

    def test_set_function(self, mock_awg):
        """Test waveform function setting."""
        mock_awg.channel1.function = "SINE"
        assert mock_awg.channel1.function == "SINE"

        mock_awg.channel1.function = "SQUARE"
        assert mock_awg.channel1.function == "SQUARE"

    def test_set_frequency(self, mock_awg):
        """Test frequency setting."""
        mock_awg.channel1.frequency = 1000.0
        assert mock_awg.channel1.frequency == 1000.0

    def test_set_amplitude(self, mock_awg):
        """Test amplitude setting."""
        mock_awg.channel1.amplitude = 5.0
        assert mock_awg.channel1.amplitude == 5.0

    def test_set_offset(self, mock_awg):
        """Test DC offset setting."""
        mock_awg.channel1.offset = 2.5
        assert mock_awg.channel1.offset == 2.5

    def test_set_phase(self, mock_awg):
        """Test phase setting."""
        mock_awg.channel1.phase = 90.0
        assert mock_awg.channel1.phase == 90.0

    def test_enable_output(self, mock_awg):
        """Test output enable."""
        mock_awg.channel1.enabled = True
        assert mock_awg.channel1.enabled is True

        mock_awg.channel1.disable()
        assert mock_awg.channel1.enabled is False

        mock_awg.channel1.enable()
        assert mock_awg.channel1.enabled is True

    def test_frequency_limit_validation(self, mock_awg):
        """Test frequency limit validation."""
        # Channel 1 max is 30MHz
        mock_awg.channel1.frequency = 30e6  # Should work
        assert mock_awg.channel1.frequency == 30e6

        # Exceeding max should raise error
        with pytest.raises(Exception):  # InvalidParameterError
            mock_awg.channel1.frequency = 50e6

    def test_amplitude_limit_validation(self, mock_awg):
        """Test amplitude limit validation."""
        # Channel 1 max is 20Vpp
        mock_awg.channel1.amplitude = 20.0  # Should work
        assert mock_awg.channel1.amplitude == 20.0

        # Exceeding max should raise error
        with pytest.raises(Exception):  # InvalidParameterError
            mock_awg.channel1.amplitude = 25.0

    def test_invalid_waveform(self, mock_awg):
        """Test invalid waveform type."""
        with pytest.raises(Exception):  # InvalidParameterError
            mock_awg.channel1.function = "INVALID"

    def test_configure_sine(self, mock_awg):
        """Test sine wave configuration convenience method."""
        mock_awg.channel1.configure_sine(frequency=1000.0, amplitude=5.0, offset=0.0)

        assert mock_awg.channel1.function == "SINE"
        assert mock_awg.channel1.frequency == 1000.0
        assert mock_awg.channel1.amplitude == 5.0
        assert mock_awg.channel1.offset == 0.0

    def test_configure_square(self, mock_awg):
        """Test square wave configuration convenience method."""
        mock_awg.channel1.configure_square(frequency=10e3, amplitude=3.3)

        assert mock_awg.channel1.function == "SQUARE"
        assert mock_awg.channel1.frequency == 10e3
        assert mock_awg.channel1.amplitude == 3.3

    def test_configure_pulse(self, mock_awg):
        """Test pulse wave configuration."""
        mock_awg.channel1.configure_pulse(
            frequency=1000.0, amplitude=5.0, duty_cycle=25.0
        )

        assert mock_awg.channel1.function == "PULSE"
        assert mock_awg.channel1.frequency == 1000.0
        assert mock_awg.channel1.amplitude == 5.0
        assert mock_awg.channel1.pulse_duty_cycle == 25.0

    def test_configure_ramp(self, mock_awg):
        """Test ramp wave configuration."""
        mock_awg.channel1.configure_ramp(
            frequency=500.0, amplitude=2.0, symmetry=50.0
        )

        assert mock_awg.channel1.function == "RAMP"
        assert mock_awg.channel1.frequency == 500.0
        assert mock_awg.channel1.amplitude == 2.0
        assert mock_awg.channel1.ramp_symmetry == 50.0

    def test_channel_configuration(self, mock_awg):
        """Test getting channel configuration."""
        mock_awg.channel1.function = "SINE"
        mock_awg.channel1.frequency = 1000.0
        mock_awg.channel1.amplitude = 5.0
        mock_awg.channel1.enabled = True

        config = mock_awg.channel1.get_configuration()

        assert config["channel"] == 1
        assert config["function"] == "SINE"
        assert config["frequency"] == 1000.0
        assert config["amplitude"] == 5.0
        assert config["enabled"] is True


class TestFunctionGeneratorOperations:
    """Test overall AWG operations."""

    @pytest.fixture
    def mock_awg(self):
        """Create mock AWG connection."""
        conn = MockConnection(
            awg_mode=True,
            awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1",
        )
        awg = FunctionGenerator("mock", connection=conn)
        awg.connect()
        return awg

    def test_all_outputs_off(self, mock_awg):
        """Test safety all-off feature."""
        # Enable all outputs
        mock_awg.channel1.enabled = True
        mock_awg.channel2.enabled = True

        # All off
        mock_awg.all_outputs_off()

        # All should be disabled
        assert mock_awg.channel1.enabled is False
        assert mock_awg.channel2.enabled is False

    def test_multiple_channels(self, mock_awg):
        """Test controlling multiple channels independently."""
        # Set different frequencies on each channel
        mock_awg.channel1.frequency = 1000.0
        mock_awg.channel2.frequency = 2000.0

        # Verify they're independent
        assert mock_awg.channel1.frequency == 1000.0
        assert mock_awg.channel2.frequency == 2000.0

    def test_sync_channels(self, mock_awg):
        """Test channel synchronization."""
        mock_awg.sync_channels(phase_offset=90.0)

        assert mock_awg.channel1.phase == 0.0
        assert mock_awg.channel2.phase == 90.0

    def test_typical_workflow(self, mock_awg):
        """Test typical AWG usage workflow."""
        # Configure sine wave
        mock_awg.channel1.configure_sine(frequency=1000.0, amplitude=5.0)

        # Enable output
        mock_awg.channel1.enable()

        # Verify settings
        assert mock_awg.channel1.enabled is True
        assert mock_awg.channel1.function == "SINE"
        assert mock_awg.channel1.frequency == 1000.0
        assert mock_awg.channel1.amplitude == 5.0

        # Turn off
        mock_awg.channel1.disable()
        assert mock_awg.channel1.enabled is False


class TestGenericAWG:
    """Test generic SCPI AWG support."""

    def test_generic_awg_connection(self):
        """Test connection to generic SCPI AWG."""
        conn = MockConnection(
            awg_mode=True,
            awg_idn="Keysight Technologies,33500B,MY000000,1.0.0",
            awg_channels={
                1: {
                    "function": "SINE",
                    "frequency": 1000.0,
                    "amplitude": 1.0,
                    "offset": 0.0,
                    "phase": 0.0,
                    "enabled": False,
                }
            },
        )
        awg = FunctionGenerator("mock", connection=conn)
        awg.connect()

        # Should detect as generic
        assert awg.model_capability.scpi_variant == "generic"
        assert awg.model_capability.manufacturer == "Keysight Technologies"

        # Should still have basic functionality
        assert hasattr(awg, "channel1")

    def test_generic_awg_basic_control(self):
        """Test basic control of generic AWG."""
        conn = MockConnection(
            awg_mode=True, awg_idn="Generic,AWG-1000,SERIAL,1.0"
        )
        awg = FunctionGenerator("mock", connection=conn)
        awg.connect()

        # Basic operations should work
        awg.channel1.function = "SINE"
        awg.channel1.frequency = 1000.0
        awg.channel1.amplitude = 5.0
        awg.channel1.enabled = True

        assert awg.channel1.function == "SINE"
        assert awg.channel1.frequency == 1000.0
        assert awg.channel1.amplitude == 5.0
        assert awg.channel1.enabled is True


class TestWaveformTypes:
    """Test all waveform types."""

    @pytest.fixture
    def mock_awg(self):
        """Create mock AWG connection."""
        conn = MockConnection(
            awg_mode=True,
            awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1",
        )
        awg = FunctionGenerator("mock", connection=conn)
        awg.connect()
        return awg

    @pytest.mark.parametrize(
        "waveform",
        ["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "DC"],
    )
    def test_waveform_types(self, mock_awg, waveform):
        """Test setting all basic waveform types."""
        mock_awg.channel1.function = waveform
        assert mock_awg.channel1.function == waveform

    def test_pulse_duty_cycle(self, mock_awg):
        """Test pulse duty cycle setting."""
        mock_awg.channel1.function = "PULSE"
        mock_awg.channel1.pulse_duty_cycle = 50.0
        assert mock_awg.channel1.pulse_duty_cycle == 50.0

        # Test invalid duty cycle
        with pytest.raises(Exception):  # InvalidParameterError
            mock_awg.channel1.pulse_duty_cycle = 150.0

    def test_ramp_symmetry(self, mock_awg):
        """Test ramp symmetry setting."""
        mock_awg.channel1.function = "RAMP"
        mock_awg.channel1.ramp_symmetry = 25.0  # Sawtooth-like
        assert mock_awg.channel1.ramp_symmetry == 25.0

        mock_awg.channel1.ramp_symmetry = 50.0  # Triangle
        assert mock_awg.channel1.ramp_symmetry == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
