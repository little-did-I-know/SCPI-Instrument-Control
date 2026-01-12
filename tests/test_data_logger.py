"""Unit tests for DataLogger class and related modules."""

import pytest

from scpi_control import DataLogger
from scpi_control.daq_models import (
    DAQCapability,
    MeasurementFunction,
    ModuleSpec,
    create_generic_daq_capability,
    detect_daq_from_idn,
)
from scpi_control.daq_scpi_commands import DAQSCPICommandSet, format_channel_list
from scpi_control.data_logger import Reading
from scpi_control.connection.mock import MockConnection


class TestDAQModels:
    """Test DAQ model detection and capabilities."""

    def test_detect_keysight_34970a(self):
        """Test detection of Keysight 34970A."""
        idn = "Keysight Technologies,34970A,MY12345678,A.01.02"
        cap = detect_daq_from_idn(idn)

        assert cap.model_name == "34970A"
        assert cap.manufacturer == "Keysight"
        assert cap.num_slots == 3
        assert cap.scpi_variant == "keysight_daq"
        assert cap.has_internal_dmm is True

    def test_detect_keysight_daq970a(self):
        """Test detection of Keysight DAQ970A."""
        idn = "Keysight Technologies,DAQ970A,MY12345678,1.0.0"
        cap = detect_daq_from_idn(idn)

        assert cap.model_name == "DAQ970A"
        assert cap.manufacturer == "Keysight"
        assert cap.scpi_variant == "keysight_daq"
        assert cap.max_sample_rate == 450.0  # Faster than 34970A

    def test_detect_agilent_34970a(self):
        """Test detection with Agilent branding (older models)."""
        idn = "Agilent Technologies,34970A,MY12345678,A.01.02"
        cap = detect_daq_from_idn(idn)

        # Should still match 34970A
        assert cap.model_name == "34970A"
        assert cap.scpi_variant == "keysight_daq"

    def test_detect_generic_daq(self):
        """Test detection of generic/unknown DAQ."""
        idn = "Unknown Manufacturer,DAQ-9000,SERIAL123,1.0.0"
        cap = detect_daq_from_idn(idn)

        assert cap.model_name == "DAQ-9000"
        assert cap.manufacturer == "Unknown Manufacturer"
        assert cap.scpi_variant == "generic"
        assert cap.num_slots == 1  # Conservative default

    def test_module_spec_channel_list(self):
        """Test ModuleSpec channel list generation."""
        module = ModuleSpec(
            slot=1,
            module_type="34901A",
            num_channels=20,
            channel_start=101,
            supported_functions=[MeasurementFunction.VOLTAGE_DC],
        )

        channels = module.get_channel_list()
        assert channels == list(range(101, 121))
        assert len(channels) == 20

    def test_daq_capability_total_channels(self):
        """Test total channel calculation."""
        cap = DAQCapability(
            model_name="Test",
            manufacturer="Test",
            num_slots=3,
            modules=[
                ModuleSpec(1, "34901A", 20, 101, [MeasurementFunction.VOLTAGE_DC]),
                ModuleSpec(2, "34901A", 20, 201, [MeasurementFunction.VOLTAGE_DC]),
            ],
        )

        assert cap.total_channels == 40
        all_channels = cap.get_all_channels()
        assert len(all_channels) == 40
        assert 101 in all_channels
        assert 201 in all_channels


class TestChannelListFormatting:
    """Test channel list formatting for SCPI commands."""

    def test_format_single_channel(self):
        """Test formatting single channel."""
        assert format_channel_list(101) == "(@101)"

    def test_format_channel_list(self):
        """Test formatting list of channels."""
        assert format_channel_list([101, 102, 103]) == "(@101,102,103)"

    def test_format_already_formatted(self):
        """Test passing already formatted string."""
        assert format_channel_list("(@101:110)") == "(@101:110)"

    def test_format_string_number(self):
        """Test passing string number."""
        assert format_channel_list("101") == "(@101)"


class TestDAQSCPICommandSet:
    """Test SCPI command generation."""

    def test_generic_commands(self):
        """Test generic SCPI-99 command generation."""
        cmd_set = DAQSCPICommandSet("generic")

        assert cmd_set.get_command("identify") == "*IDN?"
        assert cmd_set.get_command("reset") == "*RST"
        assert cmd_set.get_command("initiate") == "INIT"
        assert cmd_set.get_command("abort") == "ABOR"

    def test_configure_voltage_dc(self):
        """Test voltage configuration command."""
        cmd_set = DAQSCPICommandSet("generic")

        cmd = cmd_set.get_command(
            "configure_voltage_dc",
            range="AUTO",
            resolution="AUTO",
            channels="(@101,102)",
        )
        assert "CONF:VOLT:DC" in cmd
        assert "AUTO" in cmd
        assert "(@101,102)" in cmd

    def test_scan_list_commands(self):
        """Test scan list management commands."""
        cmd_set = DAQSCPICommandSet("generic")

        cmd = cmd_set.get_command("set_scan_list", channels="(@101:105)")
        assert "ROUT:SCAN" in cmd
        assert "(@101:105)" in cmd

    def test_keysight_specific_commands(self):
        """Test Keysight-specific command overrides."""
        cmd_set = DAQSCPICommandSet("keysight_daq")

        # Sample count (Keysight-specific)
        cmd = cmd_set.get_command("set_sample_count", count=10)
        assert "SAMP:COUN" in cmd
        assert "10" in cmd

        # Alarm limits
        cmd = cmd_set.get_command("set_alarm_high", limit=10.0, channels="(@101)")
        assert "CALC:LIM:UPP" in cmd

    def test_unknown_command(self):
        """Test that unknown command raises KeyError."""
        cmd_set = DAQSCPICommandSet("generic")

        with pytest.raises(KeyError):
            cmd_set.get_command("nonexistent_command")

    def test_missing_parameter(self):
        """Test that missing parameter raises ValueError."""
        cmd_set = DAQSCPICommandSet("generic")

        with pytest.raises(ValueError):
            cmd_set.get_command("configure_voltage_dc", range="AUTO")  # Missing channels


class TestReading:
    """Test Reading dataclass."""

    def test_reading_basic(self):
        """Test basic Reading creation."""
        r = Reading(value=5.0)
        assert r.value == 5.0
        assert r.channel is None
        assert r.unit is None

    def test_reading_full(self):
        """Test Reading with all fields."""
        r = Reading(value=5.123, channel=101, timestamp=1.5, unit="V")
        assert r.value == 5.123
        assert r.channel == 101
        assert r.timestamp == 1.5
        assert r.unit == "V"

    def test_reading_repr(self):
        """Test Reading string representation."""
        r = Reading(value=5.0, channel=101, unit="V")
        repr_str = repr(r)
        assert "5.0" in repr_str
        assert "V" in repr_str
        assert "101" in repr_str


class TestDataLoggerConnection:
    """Test DataLogger connection and initialization."""

    @pytest.fixture
    def mock_daq(self):
        """Create mock DAQ connection."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()
        return daq

    def test_daq_connection(self, mock_daq):
        """Test DAQ connects and initializes."""
        assert mock_daq.is_connected
        assert mock_daq.model_capability is not None
        assert mock_daq.model_capability.model_name == "34970A"

    def test_daq_identification(self, mock_daq):
        """Test DAQ identification."""
        idn = mock_daq.identify()
        assert "34970A" in idn
        assert "Keysight" in idn

    def test_daq_device_info(self, mock_daq):
        """Test parsed device info."""
        info = mock_daq.device_info
        assert info["manufacturer"] == "Keysight Technologies"
        assert info["model"] == "34970A"

    def test_daq_disconnect(self, mock_daq):
        """Test DAQ disconnection."""
        mock_daq.disconnect()
        assert not mock_daq.is_connected
        assert mock_daq.model_capability is None

    def test_daq_context_manager(self):
        """Test DAQ as context manager."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        with DataLogger("mock", connection=conn) as daq:
            assert daq.is_connected
            assert daq.model_capability is not None

        # Should disconnect automatically
        assert not conn.is_connected


class TestDataLoggerConfiguration:
    """Test DataLogger configuration methods."""

    @pytest.fixture
    def mock_daq(self):
        """Create mock DAQ connection."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()
        return daq

    def test_configure_voltage_dc(self, mock_daq):
        """Test DC voltage configuration."""
        # Should not raise
        mock_daq.configure_voltage_dc([101, 102, 103])

    def test_configure_voltage_ac(self, mock_daq):
        """Test AC voltage configuration."""
        mock_daq.configure_voltage_ac([101, 102])

    def test_configure_current_dc(self, mock_daq):
        """Test DC current configuration."""
        mock_daq.configure_current_dc(101)

    def test_configure_resistance(self, mock_daq):
        """Test resistance configuration."""
        mock_daq.configure_resistance([101, 102], four_wire=False)
        mock_daq.configure_resistance([103, 104], four_wire=True)

    def test_configure_temperature(self, mock_daq):
        """Test temperature configuration."""
        mock_daq.configure_temperature([101, 102], sensor_type="TC", sensor_subtype="K")

    def test_set_scan_list(self, mock_daq):
        """Test scan list configuration."""
        mock_daq.set_scan_list([101, 102, 103, 104, 105])
        assert mock_daq._scan_list == [101, 102, 103, 104, 105]

    def test_clear_scan_list(self, mock_daq):
        """Test scan list clearing."""
        mock_daq.set_scan_list([101, 102])
        mock_daq.clear_scan_list()
        assert mock_daq._scan_list == []


class TestDataLoggerTrigger:
    """Test DataLogger trigger configuration."""

    @pytest.fixture
    def mock_daq(self):
        """Create mock DAQ connection."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()
        return daq

    def test_set_trigger_source(self, mock_daq):
        """Test trigger source setting."""
        mock_daq.set_trigger_source("IMM")
        mock_daq.set_trigger_source("TIM")
        mock_daq.set_trigger_source("BUS")

    def test_set_trigger_count(self, mock_daq):
        """Test trigger count setting."""
        mock_daq.set_trigger_count(10)
        mock_daq.set_trigger_count("INF")

    def test_set_trigger_timer(self, mock_daq):
        """Test trigger timer setting."""
        mock_daq.set_trigger_timer(1.0)


class TestDataLoggerMeasurement:
    """Test DataLogger measurement methods."""

    @pytest.fixture
    def mock_daq(self):
        """Create mock DAQ with measurement data."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
            daq_readings="1.234,2.345,3.456",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()
        return daq

    def test_measure_voltage_dc(self, mock_daq):
        """Test immediate DC voltage measurement."""
        readings = mock_daq.measure_voltage_dc([101, 102, 103])

        assert len(readings) == 3
        assert readings[0].value == 1.234
        assert readings[1].value == 2.345
        assert readings[2].value == 3.456

        # Check channel assignment
        assert readings[0].channel == 101
        assert readings[1].channel == 102
        assert readings[2].channel == 103

        # Check unit assignment
        assert readings[0].unit == "V"

    def test_measure_resistance(self, mock_daq):
        """Test immediate resistance measurement."""
        readings = mock_daq.measure_resistance([101, 102, 103])

        assert len(readings) == 3
        assert readings[0].unit == "Ω"

    def test_read(self, mock_daq):
        """Test read (initiate and fetch)."""
        readings = mock_daq.read()
        assert len(readings) == 3

    def test_fetch(self, mock_daq):
        """Test fetch without initiate."""
        readings = mock_daq.fetch()
        assert len(readings) == 3


class TestDataLoggerAlarms:
    """Test DataLogger alarm/limit features."""

    @pytest.fixture
    def mock_daq(self):
        """Create mock DAQ connection."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()
        return daq

    def test_set_alarm_limits(self, mock_daq):
        """Test alarm limit setting."""
        mock_daq.set_alarm_limits([101, 102], high=10.0, low=-10.0)

    def test_enable_alarm(self, mock_daq):
        """Test alarm enable/disable."""
        mock_daq.enable_alarm([101, 102], enable=True)
        mock_daq.enable_alarm([101, 102], enable=False)


class TestDataLoggerScaling:
    """Test DataLogger scaling (mx+b) features."""

    @pytest.fixture
    def mock_daq(self):
        """Create mock DAQ connection."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()
        return daq

    def test_set_scaling(self, mock_daq):
        """Test scaling configuration."""
        mock_daq.set_scaling([101, 102], gain=2.0, offset=0.5, enable=True)


class TestGenericDAQ:
    """Test generic SCPI DAQ support."""

    def test_generic_daq_connection(self):
        """Test connection to generic SCPI DAQ."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Unknown,DAQ-1000,SERIAL,1.0",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()

        # Should detect as generic
        assert daq.model_capability.scpi_variant == "generic"
        assert daq.model_capability.manufacturer == "Unknown"

    def test_generic_daq_basic_operations(self):
        """Test basic operations on generic DAQ."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Generic,DAQ-1000,SERIAL,1.0",
            daq_readings="1.0,2.0,3.0",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()

        # Basic operations should work
        daq.configure_voltage_dc([101, 102, 103])
        daq.set_scan_list([101, 102, 103])
        readings = daq.read()

        assert len(readings) == 3


class TestDataLoggerRepr:
    """Test DataLogger string representation."""

    def test_repr_disconnected(self):
        """Test repr when disconnected."""
        daq = DataLogger("192.168.1.100")
        repr_str = repr(daq)
        assert "192.168.1.100" in repr_str
        assert "disconnected" in repr_str

    def test_repr_connected(self):
        """Test repr when connected."""
        conn = MockConnection(
            daq_mode=True,
            daq_idn="Keysight Technologies,34970A,MY12345678,A.01.02",
        )
        daq = DataLogger("mock", connection=conn)
        daq.connect()

        repr_str = repr(daq)
        assert "Keysight" in repr_str
        assert "34970A" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
