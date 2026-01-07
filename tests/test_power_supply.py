"""Unit tests for PowerSupply class and related modules."""

import pytest

from scpi_control import PowerSupply
from scpi_control.connection.mock import MockConnection
from scpi_control.psu_models import OutputSpec, PSUCapability, create_generic_psu_capability, detect_psu_from_idn
from scpi_control.psu_scpi_commands import PSUSCPICommandSet


class TestPSUModels:
    """Test PSU model detection and capabilities."""

    def test_detect_siglent_spd3303x(self):
        """Test detection of Siglent SPD3303X."""
        idn = "Siglent Technologies,SPD3303X,SPD123456,1.0"
        cap = detect_psu_from_idn(idn)

        assert cap.model_name == "SPD3303X"
        assert cap.manufacturer == "Siglent"
        assert cap.num_outputs == 3
        assert cap.scpi_variant == "siglent_spd"
        assert cap.has_ovp is True
        assert cap.has_timer is True

    def test_detect_siglent_spd3303x_e(self):
        """Test detection of Siglent SPD3303X-E variant."""
        idn = "Siglent Technologies,SPD3303X-E,SPD123456,1.0"
        cap = detect_psu_from_idn(idn)

        assert cap.model_name == "SPD3303X-E"
        assert cap.num_outputs == 3
        assert cap.scpi_variant == "siglent_spd"

    def test_detect_siglent_spd1305x(self):
        """Test detection of Siglent SPD1305X."""
        idn = "Siglent Technologies,SPD1305X,SPD123456,1.0"
        cap = detect_psu_from_idn(idn)

        assert cap.model_name == "SPD1305X"
        assert cap.num_outputs == 1
        assert len(cap.output_specs) == 1
        assert cap.output_specs[0].max_voltage == 30.0
        assert cap.output_specs[0].max_current == 5.0

    def test_detect_generic_psu(self):
        """Test detection of generic/unknown PSU."""
        idn = "RIGOL TECHNOLOGIES,DP832,DP8XXXX,1.0.0"
        cap = detect_psu_from_idn(idn)

        assert cap.model_name == "DP832"
        assert cap.manufacturer == "RIGOL TECHNOLOGIES"
        assert cap.scpi_variant == "generic"
        assert cap.num_outputs == 1  # Conservative default

    def test_output_spec_string(self):
        """Test OutputSpec string representation."""
        spec = OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001)
        assert "Output1" in str(spec)
        assert "30.0V" in str(spec)
        assert "3.0A" in str(spec)


class TestPSUSCPICommandSet:
    """Test SCPI command generation."""

    def test_generic_commands(self):
        """Test generic SCPI-99 command generation."""
        cmd_set = PSUSCPICommandSet("generic")

        assert cmd_set.get_command("identify") == "*IDN?"
        assert cmd_set.get_command("reset") == "*RST"
        assert cmd_set.get_command("set_voltage", ch=1, voltage=5.0) == "SOUR1:VOLT 5.0"
        assert cmd_set.get_command("get_voltage", ch=1) == "SOUR1:VOLT?"

    def test_siglent_spd_commands(self):
        """Test Siglent SPD command overrides."""
        cmd_set = PSUSCPICommandSet("siglent_spd")

        assert cmd_set.get_command("set_voltage", ch=1, voltage=5.0) == "CH1:VOLT 5.0"
        assert cmd_set.get_command("get_voltage", ch=1) == "CH1:VOLT?"
        assert cmd_set.get_command("set_output", ch=1, state="ON") == "OUTPut CH1,ON"
        assert cmd_set.get_command("measure_voltage", ch=1) == "MEASure1:VOLTage?"

    def test_fallback_to_generic(self):
        """Test that Siglent variant falls back to generic for unknown commands."""
        cmd_set = PSUSCPICommandSet("siglent_spd")

        # System commands should still use generic
        assert cmd_set.get_command("identify") == "*IDN?"
        assert cmd_set.get_command("reset") == "*RST"

    def test_unknown_command(self):
        """Test that unknown command raises KeyError."""
        cmd_set = PSUSCPICommandSet("generic")

        with pytest.raises(KeyError):
            cmd_set.get_command("nonexistent_command")

    def test_missing_parameter(self):
        """Test that missing parameter raises ValueError."""
        cmd_set = PSUSCPICommandSet("generic")

        with pytest.raises(ValueError):
            cmd_set.get_command("set_voltage", ch=1)  # Missing voltage parameter


class TestPowerSupplyConnection:
    """Test PowerSupply connection and initialization."""

    @pytest.fixture
    def mock_psu(self):
        """Create mock PSU connection."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()
        return psu

    def test_psu_connection(self, mock_psu):
        """Test PSU connects and initializes."""
        assert mock_psu.is_connected
        assert mock_psu.model_capability is not None
        assert mock_psu.model_capability.model_name == "SPD3303X"

    def test_psu_identification(self, mock_psu):
        """Test PSU identification."""
        idn = mock_psu.identify()
        assert "SPD3303X" in idn
        assert "Siglent" in idn

    def test_psu_device_info(self, mock_psu):
        """Test parsed device info."""
        info = mock_psu.device_info
        assert info["manufacturer"] == "Siglent"
        assert info["model"] == "SPD3303X"

    def test_psu_outputs_created(self, mock_psu):
        """Test that outputs are created dynamically."""
        assert hasattr(mock_psu, "output1")
        assert hasattr(mock_psu, "output2")
        assert hasattr(mock_psu, "output3")
        assert mock_psu.supported_outputs == [1, 2, 3]

    def test_psu_disconnect(self, mock_psu):
        """Test PSU disconnection."""
        mock_psu.disconnect()
        assert not mock_psu.is_connected
        assert mock_psu.model_capability is None

    def test_psu_context_manager(self):
        """Test PSU as context manager."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        with PowerSupply("mock", connection=conn) as psu:
            assert psu.is_connected
            assert psu.model_capability is not None

        # Should disconnect automatically
        assert not conn.is_connected


class TestPowerSupplyOutput:
    """Test PowerSupplyOutput control."""

    @pytest.fixture
    def mock_psu(self):
        """Create mock PSU connection."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()
        return psu

    def test_set_voltage(self, mock_psu):
        """Test voltage setting."""
        mock_psu.output1.voltage = 5.0
        assert mock_psu.output1.voltage == 5.0

    def test_set_current(self, mock_psu):
        """Test current limit setting."""
        mock_psu.output1.current = 2.0
        assert mock_psu.output1.current == 2.0

    def test_enable_output(self, mock_psu):
        """Test output enable."""
        mock_psu.output1.enabled = True
        assert mock_psu.output1.enabled is True

        mock_psu.output1.disable()
        assert mock_psu.output1.enabled is False

        mock_psu.output1.enable()
        assert mock_psu.output1.enabled is True

    def test_measure_voltage(self, mock_psu):
        """Test voltage measurement."""
        mock_psu.output1.voltage = 12.0
        measured = mock_psu.output1.measure_voltage()
        # Should be close to setpoint (mock adds small noise)
        assert 11.9 <= measured <= 12.1

    def test_measure_current(self, mock_psu):
        """Test current measurement."""
        mock_psu.output1.current = 1.5
        measured = mock_psu.output1.measure_current()
        assert 1.4 <= measured <= 1.6

    def test_measure_power(self, mock_psu):
        """Test power measurement."""
        mock_psu.output1.voltage = 10.0
        mock_psu.output1.current = 1.0
        power = mock_psu.output1.measure_power()
        # Power = V * I
        assert 9.5 <= power <= 10.5

    def test_voltage_limit_validation(self, mock_psu):
        """Test voltage limit validation."""
        # Output 1 max is 30V
        mock_psu.output1.voltage = 30.0  # Should work
        assert mock_psu.output1.voltage == 30.0

        # Exceeding max should raise error
        with pytest.raises(Exception):  # InvalidParameterError
            mock_psu.output1.voltage = 35.0

    def test_current_limit_validation(self, mock_psu):
        """Test current limit validation."""
        # Output 1 max is 3A
        mock_psu.output1.current = 3.0  # Should work
        assert mock_psu.output1.current == 3.0

        # Exceeding max should raise error
        with pytest.raises(Exception):  # InvalidParameterError
            mock_psu.output1.current = 5.0

    def test_output_configuration(self, mock_psu):
        """Test getting output configuration."""
        mock_psu.output1.voltage = 5.0
        mock_psu.output1.current = 1.0
        mock_psu.output1.enabled = True

        config = mock_psu.output1.get_configuration()

        assert config["output"] == 1
        assert config["voltage_setpoint"] == 5.0
        assert config["current_limit"] == 1.0
        assert config["enabled"] is True
        assert config["max_voltage"] == 30.0
        assert config["max_current"] == 3.0


class TestPowerSupplyOperations:
    """Test overall PSU operations."""

    @pytest.fixture
    def mock_psu(self):
        """Create mock PSU connection."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()
        return psu

    def test_all_outputs_off(self, mock_psu):
        """Test safety all-off feature."""
        # Enable all outputs
        mock_psu.output1.enabled = True
        mock_psu.output2.enabled = True
        mock_psu.output3.enabled = True

        # All off
        mock_psu.all_outputs_off()

        # All should be disabled
        assert mock_psu.output1.enabled is False
        assert mock_psu.output2.enabled is False
        assert mock_psu.output3.enabled is False

    def test_multiple_outputs(self, mock_psu):
        """Test controlling multiple outputs independently."""
        # Set different voltages on each output
        mock_psu.output1.voltage = 5.0
        mock_psu.output2.voltage = 12.0
        mock_psu.output3.voltage = 3.3

        # Verify they're independent
        assert mock_psu.output1.voltage == 5.0
        assert mock_psu.output2.voltage == 12.0
        assert mock_psu.output3.voltage == 3.3

    def test_typical_workflow(self, mock_psu):
        """Test typical PSU usage workflow."""
        # Set voltage and current limit
        mock_psu.output1.voltage = 5.0
        mock_psu.output1.current = 2.0

        # Enable output
        mock_psu.output1.enable()

        # Verify settings
        assert mock_psu.output1.enabled is True
        assert mock_psu.output1.voltage == 5.0
        assert mock_psu.output1.current == 2.0

        # Read measurements
        v_measured = mock_psu.output1.measure_voltage()
        i_measured = mock_psu.output1.measure_current()
        p_measured = mock_psu.output1.measure_power()

        assert v_measured > 0
        assert p_measured >= 0

        # Turn off
        mock_psu.output1.disable()
        assert mock_psu.output1.enabled is False


class TestGenericPSU:
    """Test generic SCPI PSU support."""

    def test_generic_psu_connection(self):
        """Test connection to generic SCPI PSU."""
        conn = MockConnection(psu_mode=True, psu_idn="RIGOL TECHNOLOGIES,DP832,DP8XXXX,1.0", psu_outputs={1: {"voltage": 0.0, "current": 0.0, "enabled": False}})
        psu = PowerSupply("mock", connection=conn)
        psu.connect()

        # Should detect as generic
        assert psu.model_capability.scpi_variant == "generic"
        assert psu.model_capability.manufacturer == "RIGOL TECHNOLOGIES"

        # Should still have basic functionality
        assert hasattr(psu, "output1")

    def test_generic_psu_basic_control(self):
        """Test basic control of generic PSU."""
        conn = MockConnection(psu_mode=True, psu_idn="Generic,PSU-3000,SERIAL,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()

        # Basic operations should work
        psu.output1.voltage = 12.0
        psu.output1.current = 1.5
        psu.output1.enabled = True

        assert psu.output1.voltage == 12.0
        assert psu.output1.current == 1.5
        assert psu.output1.enabled is True


class TestAdvancedFeatures:
    """Test advanced PSU features (tracking, OVP/OCP, timer, waveform)."""

    @pytest.fixture
    def siglent_psu(self):
        """Create connected Siglent PSU."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()
        yield psu
        psu.disconnect()

    def test_tracking_mode_independent(self, siglent_psu):
        """Test independent tracking mode."""
        psu = siglent_psu
        assert psu.model_capability.has_tracking is True

        psu.set_independent_mode()
        # Mock doesn't actually change mode, but method should not error
        assert psu.tracking_mode in ["INDEPENDENT", "SERIES", "PARALLEL"]

    def test_tracking_mode_series(self, siglent_psu):
        """Test series tracking mode."""
        psu = siglent_psu
        psu.set_series_mode()
        assert psu.tracking_mode in ["INDEPENDENT", "SERIES", "PARALLEL"]

    def test_tracking_mode_parallel(self, siglent_psu):
        """Test parallel tracking mode."""
        psu = siglent_psu
        psu.set_parallel_mode()
        assert psu.tracking_mode in ["INDEPENDENT", "SERIES", "PARALLEL"]

    def test_tracking_mode_setter(self, siglent_psu):
        """Test tracking mode property setter."""
        psu = siglent_psu
        psu.tracking_mode = "SERIES"
        # Should not raise error

    def test_tracking_mode_not_supported(self):
        """Test tracking mode on PSU without support."""
        conn = MockConnection(psu_mode=True, psu_idn="Generic,PSU-1000,SERIAL,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()

        # Generic PSU doesn't have tracking
        assert psu.model_capability.has_tracking is False

        with pytest.raises(NotImplementedError):
            _ = psu.tracking_mode

    def test_ovp_level(self, siglent_psu):
        """Test OVP (over-voltage protection) level."""
        psu = siglent_psu
        output = psu.output1

        assert psu.model_capability.has_ovp is True

        # Set OVP level
        output.ovp_level = 25.0
        # Mock doesn't store this, but should not error
        assert isinstance(output.ovp_level, float)

    def test_ocp_level(self, siglent_psu):
        """Test OCP (over-current protection) level."""
        psu = siglent_psu
        output = psu.output1

        assert psu.model_capability.has_ocp is True

        # Set OCP level
        output.ocp_level = 2.5
        assert isinstance(output.ocp_level, float)

    def test_ovp_generic_support(self):
        """Test OVP on generic PSU (SCPI-99 standard supports it)."""
        conn = MockConnection(psu_mode=True, psu_idn="Generic,PSU-1000,SERIAL,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()

        # Generic SCPI-99 PSUs support OVP/OCP (VOLT:PROT, CURR:PROT)
        assert psu.model_capability.has_ovp is True
        assert psu.model_capability.has_ocp is True

        # Should work without error
        psu.output1.ovp_level = 25.0
        assert isinstance(psu.output1.ovp_level, float)

    def test_timer_enable(self, siglent_psu):
        """Test timer enable/disable."""
        psu = siglent_psu
        output = psu.output1

        assert psu.model_capability.has_timer is True

        # Enable timer
        output.timer_enabled = True
        # Mock doesn't track timer state, but should not error
        assert isinstance(output.timer_enabled, bool)

        # Disable timer
        output.timer_enabled = False
        assert isinstance(output.timer_enabled, bool)

    def test_timer_not_supported(self):
        """Test timer on PSU without support."""
        conn = MockConnection(psu_mode=True, psu_idn="Generic,PSU-1000,SERIAL,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()

        assert psu.model_capability.has_timer is False

        with pytest.raises(NotImplementedError):
            _ = psu.output1.timer_enabled

        with pytest.raises(NotImplementedError):
            psu.output1.timer_enabled = True

    def test_waveform_enable(self, siglent_psu):
        """Test waveform generation enable/disable."""
        psu = siglent_psu
        output = psu.output1

        assert psu.model_capability.has_waveform is True

        # Enable waveform
        output.waveform_enabled = True
        assert isinstance(output.waveform_enabled, bool)

        # Disable waveform
        output.waveform_enabled = False
        assert isinstance(output.waveform_enabled, bool)

    def test_waveform_not_supported(self):
        """Test waveform on PSU without support."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD1305X,SPD123456,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()

        # SPD1305X doesn't have waveform generation
        assert psu.model_capability.has_waveform is False

        with pytest.raises(NotImplementedError):
            _ = psu.output1.waveform_enabled

        with pytest.raises(NotImplementedError):
            psu.output1.waveform_enabled = True


class TestDataLogging:
    """Test PSU data logging functionality."""

    @pytest.fixture
    def mock_psu(self):
        """Create connected mock PSU."""
        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        psu = PowerSupply("mock", connection=conn)
        psu.connect()
        psu.output1.voltage = 5.0
        psu.output1.current = 1.0
        psu.output1.enabled = True
        yield psu
        psu.disconnect()

    def test_psu_data_logger_basic(self, mock_psu, tmp_path):
        """Test basic PSU data logger."""
        from scpi_control import PSUDataLogger

        log_file = tmp_path / "test_log.csv"
        logger = PSUDataLogger(mock_psu, str(log_file))

        assert logger.is_logging is False

        logger.start()
        assert logger.is_logging is True

        # Log a few measurements
        logger.log_measurement()
        logger.log_measurement()

        logger.stop()
        assert logger.is_logging is False

        # Verify file was created
        assert log_file.exists()

        # Read and verify contents
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 3  # Header + 2 measurements
            assert "timestamp" in lines[0]
            assert "output1_voltage_V" in lines[0]

    def test_psu_data_logger_context_manager(self, mock_psu, tmp_path):
        """Test PSU data logger as context manager."""
        from scpi_control import PSUDataLogger

        log_file = tmp_path / "test_log_context.csv"

        with PSUDataLogger(mock_psu, str(log_file)) as logger:
            assert logger.is_logging is True
            logger.log_measurement()

        # Logger should be stopped after context exit
        assert logger.is_logging is False
        assert log_file.exists()

    def test_psu_data_logger_selective_outputs(self, mock_psu, tmp_path):
        """Test logging only specific outputs."""
        from scpi_control import PSUDataLogger

        log_file = tmp_path / "test_log_selective.csv"

        # Log only output 1
        logger = PSUDataLogger(mock_psu, str(log_file), outputs=[1])
        logger.start()
        logger.log_measurement()
        logger.stop()

        # Verify only output1 columns are present
        with open(log_file, "r") as f:
            header = f.readline()
            assert "output1_voltage_V" in header
            assert "output2_voltage_V" not in header
            assert "output3_voltage_V" not in header

    def test_timed_psu_logger(self, mock_psu, tmp_path):
        """Test timed PSU logger."""
        import time

        from scpi_control import TimedPSULogger

        log_file = tmp_path / "test_timed_log.csv"

        # Create logger with short interval
        timed_logger = TimedPSULogger(mock_psu, str(log_file), interval=0.1)

        assert timed_logger.is_logging is False

        timed_logger.start()
        assert timed_logger.is_logging is True

        # Let it run for a short time
        time.sleep(0.35)  # Should get ~3 measurements

        timed_logger.stop()
        assert timed_logger.is_logging is False

        # Verify file was created with multiple measurements
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) >= 2  # Header + at least 1 measurement

    def test_timed_psu_logger_context_manager(self, mock_psu, tmp_path):
        """Test timed PSU logger as context manager."""
        import time

        from scpi_control import TimedPSULogger

        log_file = tmp_path / "test_timed_context.csv"

        with TimedPSULogger(mock_psu, str(log_file), interval=0.1) as logger:
            assert logger.is_logging is True
            time.sleep(0.25)

        assert logger.is_logging is False
        assert log_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
