"""Main DataLogger class for controlling SCPI Data Acquisition systems.

Supports generic SCPI-99 compliant DAQ systems and Keysight 34970A/DAQ970A series.

Installation:
    pip install "SCPI-Instrument-Control"

Features:
    - Multiple connection types: Ethernet/LAN, USB, GPIB
    - Multi-channel scanning with configurable sample rates
    - Support for voltage, current, resistance, temperature measurements
    - Alarm/limit checking and scaling (mx+b)
    - Data logging with timestamps
    - Context manager support for automatic connection management

Feedback:
    Please report issues and suggestions at:
    https://github.com/little-did-I-know/SCPI-Instrument-Control/issues
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from scpi_control import exceptions
from scpi_control.connection import BaseConnection, SocketConnection
from scpi_control.daq_models import DAQCapability, MeasurementFunction, detect_daq_from_idn
from scpi_control.daq_scpi_commands import DAQSCPICommandSet, format_channel_list

logger = logging.getLogger(__name__)


@dataclass
class Reading:
    """A single measurement reading from the DAQ."""

    value: float
    channel: Optional[int] = None
    timestamp: Optional[float] = None
    unit: Optional[str] = None
    alarm_state: Optional[str] = None

    def __repr__(self) -> str:
        parts = [f"{self.value}"]
        if self.unit:
            parts[0] += f" {self.unit}"
        if self.channel:
            parts.append(f"ch={self.channel}")
        if self.timestamp:
            parts.append(f"t={self.timestamp:.3f}s")
        return f"Reading({', '.join(parts)})"


class DataLogger:
    """Main class for controlling SCPI Data Acquisition systems.

    This class provides a high-level interface for controlling DAQ
    functions including channel configuration, scanning, and data retrieval.

    Supports both generic SCPI-99 DAQs and Keysight 34970A/DAQ970A series
    with automatic model detection and capability-based feature availability.

    Example:
        >>> daq = DataLogger('192.168.1.100')
        >>> daq.connect()
        >>> print(daq.identify())
        >>> # Configure channels for voltage measurement
        >>> daq.configure_voltage_dc([101, 102, 103])
        >>> # Set up scan list
        >>> daq.set_scan_list([101, 102, 103])
        >>> # Take readings
        >>> readings = daq.read()
        >>> for r in readings:
        ...     print(f"Channel {r.channel}: {r.value} V")
        >>> daq.disconnect()

        Or using context manager:
        >>> with DataLogger('192.168.1.100') as daq:
        ...     daq.configure_voltage_dc([101, 102])
        ...     readings = daq.measure_voltage_dc([101, 102])
    """

    def __init__(
        self,
        host: str,
        port: int = 5025,
        timeout: float = 10.0,
        connection: Optional[BaseConnection] = None,
    ):
        """Initialize Data Logger connection.

        Args:
            host: IP address or hostname of the DAQ
            port: TCP port for SCPI communication (default: 5025)
            timeout: Command timeout in seconds (default: 10.0)
            connection: Optional custom connection object

        Note:
            Call connect() to establish connection and initialize capabilities.
        """
        self.host = host
        self.port = port
        self.timeout = timeout

        if connection is not None:
            self._connection = connection
        else:
            self._connection = SocketConnection(host, port, timeout)

        self.model_capability: Optional[DAQCapability] = None
        self._scpi_commands: Optional[DAQSCPICommandSet] = None
        self._device_info: Optional[Dict[str, str]] = None
        self._scan_list: List[int] = []

    def connect(self) -> None:
        """Establish connection to the Data Logger.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        logger.info(f"Connecting to Data Logger at {self.host}:{self.port}")
        self._connection.connect()
        logger.info("Connected successfully")

        try:
            idn_string = self.identify()
            self._device_info = self._parse_idn(idn_string)
            logger.info(f"Connected to: {self._device_info.get('manufacturer', 'Unknown')} " f"{self._device_info.get('model', 'Unknown')}")

            self.model_capability = detect_daq_from_idn(idn_string)
            logger.info(f"Model capability: {self.model_capability}")

            self._scpi_commands = DAQSCPICommandSet(self.model_capability.scpi_variant)
            logger.info(f"Using SCPI variant: {self.model_capability.scpi_variant}")

        except Exception as e:
            logger.error(f"Failed to identify device: {e}")
            self.disconnect()
            raise exceptions.SiglentConnectionError(f"Connected but failed to identify device: {e}")

    def disconnect(self) -> None:
        """Close connection to the Data Logger."""
        logger.info("Disconnecting from Data Logger")
        self._connection.disconnect()
        self._device_info = None
        self.model_capability = None
        self._scpi_commands = None
        self._scan_list = []

    @property
    def is_connected(self) -> bool:
        """Check if connected to Data Logger."""
        return self._connection.is_connected

    def write(self, command: str) -> None:
        """Send a SCPI command to the Data Logger."""
        logger.debug(f"Write: {command}")
        self._connection.write(command)

    def query(self, command: str) -> str:
        """Send a SCPI query and get the response."""
        logger.debug(f"Query: {command}")
        response = self._connection.query(command)
        logger.debug(f"Response: {response}")
        return response

    def identify(self) -> str:
        """Get device identification string."""
        return self.query("*IDN?")

    def reset(self) -> None:
        """Reset Data Logger to default settings."""
        logger.info("Resetting Data Logger to defaults")
        self.write("*RST")

    def clear_status(self) -> None:
        """Clear status registers."""
        self.write("*CLS")

    def get_error(self) -> str:
        """Get the last error from the error queue."""
        return self.query("SYST:ERR?")

    def abort(self) -> None:
        """Abort the current scan operation."""
        logger.info("Aborting current scan")
        cmd = self._get_command("abort")
        self.write(cmd)

    # --- Configuration Methods ---

    def configure_voltage_dc(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> None:
        """Configure channels for DC voltage measurement.

        Args:
            channels: Channel number(s) to configure
            range: Measurement range (AUTO, 0.1, 1, 10, 100, 300)
            resolution: Resolution (AUTO, MIN, MAX, or specific value)
        """
        ch_str = format_channel_list(channels)
        cmd = self._get_command("configure_voltage_dc", range=range, resolution=resolution, channels=ch_str)
        self.write(cmd)
        logger.info(f"Configured DC voltage on {ch_str}")

    def configure_voltage_ac(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> None:
        """Configure channels for AC voltage measurement."""
        ch_str = format_channel_list(channels)
        cmd = self._get_command("configure_voltage_ac", range=range, resolution=resolution, channels=ch_str)
        self.write(cmd)
        logger.info(f"Configured AC voltage on {ch_str}")

    def configure_current_dc(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> None:
        """Configure channels for DC current measurement."""
        ch_str = format_channel_list(channels)
        cmd = self._get_command("configure_current_dc", range=range, resolution=resolution, channels=ch_str)
        self.write(cmd)
        logger.info(f"Configured DC current on {ch_str}")

    def configure_current_ac(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> None:
        """Configure channels for AC current measurement."""
        ch_str = format_channel_list(channels)
        cmd = self._get_command("configure_current_ac", range=range, resolution=resolution, channels=ch_str)
        self.write(cmd)
        logger.info(f"Configured AC current on {ch_str}")

    def configure_resistance(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
        four_wire: bool = False,
    ) -> None:
        """Configure channels for resistance measurement.

        Args:
            channels: Channel number(s) to configure
            range: Measurement range (AUTO, 100, 1000, 10000, etc.)
            resolution: Resolution (AUTO, MIN, MAX)
            four_wire: Use 4-wire (Kelvin) measurement for accuracy
        """
        ch_str = format_channel_list(channels)
        cmd_name = "configure_resistance_4w" if four_wire else "configure_resistance_2w"
        cmd = self._get_command(cmd_name, range=range, resolution=resolution, channels=ch_str)
        self.write(cmd)
        logger.info(f"Configured {'4-wire' if four_wire else '2-wire'} resistance on {ch_str}")

    def configure_temperature(
        self,
        channels: Union[int, List[int]],
        sensor_type: str = "TC",
        sensor_subtype: str = "K",
    ) -> None:
        """Configure channels for temperature measurement.

        Args:
            channels: Channel number(s) to configure
            sensor_type: Sensor type (TC=thermocouple, RTD, THER=thermistor)
            sensor_subtype: Sensor subtype (e.g., K, J, T for TC; PT100 for RTD)
        """
        ch_str = format_channel_list(channels)

        if self._scpi_commands and self._scpi_commands.variant == "keysight_daq":
            if sensor_type.upper() == "TC":
                cmd = self._get_command("configure_temperature_tc", tc_type=sensor_subtype, channels=ch_str)
            elif sensor_type.upper() == "RTD":
                cmd = self._get_command("configure_temperature_rtd", rtd_type=sensor_subtype, channels=ch_str)
            elif sensor_type.upper() in ("THER", "THERM", "THERMISTOR"):
                cmd = self._get_command("configure_temperature_therm", therm_type=sensor_subtype, channels=ch_str)
            else:
                cmd = self._get_command("configure_temperature", sensor_type=sensor_type, channels=ch_str)
        else:
            cmd = self._get_command("configure_temperature", sensor_type=f"{sensor_type},{sensor_subtype}", channels=ch_str)

        self.write(cmd)
        logger.info(f"Configured temperature ({sensor_type} {sensor_subtype}) on {ch_str}")

    # --- Scan List Management ---

    def set_scan_list(self, channels: Union[int, List[int]]) -> None:
        """Set the scan list for automatic scanning.

        Args:
            channels: Channel number(s) to include in scan
        """
        ch_str = format_channel_list(channels)
        cmd = self._get_command("set_scan_list", channels=ch_str)
        self.write(cmd)

        # Update internal scan list tracking
        if isinstance(channels, int):
            self._scan_list = [channels]
        else:
            self._scan_list = list(channels)

        logger.info(f"Scan list set to {ch_str}")

    def get_scan_list(self) -> str:
        """Get the current scan list."""
        cmd = self._get_command("get_scan_list")
        return self.query(cmd)

    def clear_scan_list(self) -> None:
        """Clear the scan list."""
        cmd = self._get_command("clear_scan_list")
        self.write(cmd)
        self._scan_list = []
        logger.info("Scan list cleared")

    # --- Trigger Configuration ---

    def set_trigger_source(self, source: str = "IMM") -> None:
        """Set the trigger source.

        Args:
            source: Trigger source (IMM, TIM, BUS, EXT)
        """
        cmd = self._get_command("set_trigger_source", source=source)
        self.write(cmd)
        logger.info(f"Trigger source set to {source}")

    def set_trigger_count(self, count: Union[int, str] = 1) -> None:
        """Set number of triggers to accept.

        Args:
            count: Number of triggers (int or "INF" for infinite)
        """
        cmd = self._get_command("set_trigger_count", count=count)
        self.write(cmd)
        logger.info(f"Trigger count set to {count}")

    def set_trigger_timer(self, interval: float) -> None:
        """Set the trigger timer interval for timed scanning.

        Args:
            interval: Time between scans in seconds
        """
        cmd = self._get_command("set_trigger_timer", interval=interval)
        self.write(cmd)
        logger.info(f"Trigger timer set to {interval}s")

    def set_sample_count(self, count: Union[int, str] = 1) -> None:
        """Set the number of samples per trigger.

        Args:
            count: Number of samples (int or "INF")
        """
        if self._scpi_commands and self._scpi_commands.supports_command("set_sample_count"):
            cmd = self._get_command("set_sample_count", count=count)
            self.write(cmd)
            logger.info(f"Sample count set to {count}")
        else:
            logger.warning("Sample count command not supported on this model")

    # --- Data Acquisition ---

    def initiate(self) -> None:
        """Initiate a scan sequence."""
        cmd = self._get_command("initiate")
        self.write(cmd)
        logger.info("Scan initiated")

    def trigger(self) -> None:
        """Send a software trigger."""
        cmd = self._get_command("trigger")
        self.write(cmd)
        logger.debug("Software trigger sent")

    def read(self) -> List[Reading]:
        """Initiate scan and read results (blocking).

        Returns:
            List of Reading objects with measurement data
        """
        cmd = self._get_command("read")
        response = self.query(cmd)
        return self._parse_readings(response)

    def fetch(self) -> List[Reading]:
        """Fetch readings from memory (does not initiate new scan).

        Returns:
            List of Reading objects
        """
        cmd = self._get_command("fetch")
        response = self.query(cmd)
        return self._parse_readings(response)

    def read_and_remove(self, max_readings: int = 100) -> List[Reading]:
        """Read and remove readings from memory.

        Args:
            max_readings: Maximum number of readings to retrieve

        Returns:
            List of Reading objects
        """
        cmd = self._get_command("read_remove", max_readings=max_readings)
        response = self.query(cmd)
        return self._parse_readings(response)

    def get_data_points(self) -> int:
        """Get number of readings in memory."""
        cmd = self._get_command("get_data_points")
        response = self.query(cmd)
        return int(float(response.strip()))

    def clear_data(self) -> None:
        """Clear all readings from memory."""
        cmd = self._get_command("clear_data")
        self.write(cmd)
        logger.info("Data memory cleared")

    # --- Immediate Measurements ---

    def measure_voltage_dc(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> List[Reading]:
        """Measure DC voltage immediately.

        Args:
            channels: Channel(s) to measure
            range: Measurement range
            resolution: Resolution

        Returns:
            List of Reading objects
        """
        ch_str = format_channel_list(channels)
        cmd = self._get_command("measure_voltage_dc", range=range, resolution=resolution, channels=ch_str)
        response = self.query(cmd)
        readings = self._parse_readings(response)

        # Assign channel numbers if not included in response
        if isinstance(channels, int):
            channels = [channels]
        for i, reading in enumerate(readings):
            if reading.channel is None and i < len(channels):
                reading.channel = channels[i]
            if reading.unit is None:
                reading.unit = "V"

        return readings

    def measure_voltage_ac(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> List[Reading]:
        """Measure AC voltage immediately."""
        ch_str = format_channel_list(channels)
        cmd = self._get_command("measure_voltage_ac", range=range, resolution=resolution, channels=ch_str)
        response = self.query(cmd)
        readings = self._parse_readings(response)

        if isinstance(channels, int):
            channels = [channels]
        for i, reading in enumerate(readings):
            if reading.channel is None and i < len(channels):
                reading.channel = channels[i]
            if reading.unit is None:
                reading.unit = "V"

        return readings

    def measure_current_dc(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
    ) -> List[Reading]:
        """Measure DC current immediately."""
        ch_str = format_channel_list(channels)
        cmd = self._get_command("measure_current_dc", range=range, resolution=resolution, channels=ch_str)
        response = self.query(cmd)
        readings = self._parse_readings(response)

        if isinstance(channels, int):
            channels = [channels]
        for i, reading in enumerate(readings):
            if reading.channel is None and i < len(channels):
                reading.channel = channels[i]
            if reading.unit is None:
                reading.unit = "A"

        return readings

    def measure_resistance(
        self,
        channels: Union[int, List[int]],
        range: str = "AUTO",
        resolution: str = "AUTO",
        four_wire: bool = False,
    ) -> List[Reading]:
        """Measure resistance immediately."""
        ch_str = format_channel_list(channels)
        cmd_name = "measure_resistance_4w" if four_wire else "measure_resistance_2w"
        cmd = self._get_command(cmd_name, range=range, resolution=resolution, channels=ch_str)
        response = self.query(cmd)
        readings = self._parse_readings(response)

        if isinstance(channels, int):
            channels = [channels]
        for i, reading in enumerate(readings):
            if reading.channel is None and i < len(channels):
                reading.channel = channels[i]
            if reading.unit is None:
                reading.unit = "Ω"

        return readings

    def measure_temperature(
        self,
        channels: Union[int, List[int]],
        sensor_type: str = "TC,K",
    ) -> List[Reading]:
        """Measure temperature immediately."""
        ch_str = format_channel_list(channels)
        cmd = self._get_command("measure_temperature", sensor_type=sensor_type, channels=ch_str)
        response = self.query(cmd)
        readings = self._parse_readings(response)

        if isinstance(channels, int):
            channels = [channels]
        for i, reading in enumerate(readings):
            if reading.channel is None and i < len(channels):
                reading.channel = channels[i]
            if reading.unit is None:
                reading.unit = "°C"

        return readings

    # --- Alarm/Limit Configuration ---

    def set_alarm_limits(
        self,
        channels: Union[int, List[int]],
        high: Optional[float] = None,
        low: Optional[float] = None,
    ) -> None:
        """Set alarm limits for channels.

        Args:
            channels: Channel(s) to configure
            high: Upper limit (None to disable)
            low: Lower limit (None to disable)
        """
        if not self.model_capability or not self.model_capability.has_alarm:
            logger.warning("Alarm limits not supported on this model")
            return

        ch_str = format_channel_list(channels)

        if high is not None:
            cmd = self._get_command("set_alarm_high", limit=high, channels=ch_str)
            self.write(cmd)

        if low is not None:
            cmd = self._get_command("set_alarm_low", limit=low, channels=ch_str)
            self.write(cmd)

        logger.info(f"Alarm limits set on {ch_str}: low={low}, high={high}")

    def enable_alarm(self, channels: Union[int, List[int]], enable: bool = True) -> None:
        """Enable or disable alarm checking on channels."""
        if not self.model_capability or not self.model_capability.has_alarm:
            logger.warning("Alarm limits not supported on this model")
            return

        ch_str = format_channel_list(channels)
        state = "ON" if enable else "OFF"
        cmd = self._get_command("set_alarm_enable", state=state, channels=ch_str)
        self.write(cmd)
        logger.info(f"Alarm {'enabled' if enable else 'disabled'} on {ch_str}")

    # --- Scaling Configuration ---

    def set_scaling(
        self,
        channels: Union[int, List[int]],
        gain: float = 1.0,
        offset: float = 0.0,
        enable: bool = True,
    ) -> None:
        """Set mx+b scaling on channels.

        Args:
            channels: Channel(s) to configure
            gain: Gain multiplier (m)
            offset: Offset value (b)
            enable: Enable scaling
        """
        if not self.model_capability or not self.model_capability.has_math:
            logger.warning("Scaling not supported on this model")
            return

        ch_str = format_channel_list(channels)

        cmd = self._get_command("set_scaling_gain", gain=gain, channels=ch_str)
        self.write(cmd)

        cmd = self._get_command("set_scaling_offset", offset=offset, channels=ch_str)
        self.write(cmd)

        state = "ON" if enable else "OFF"
        cmd = self._get_command("set_scaling_enable", state=state, channels=ch_str)
        self.write(cmd)

        logger.info(f"Scaling set on {ch_str}: {gain}x + {offset}")

    # --- Continuous Logging ---

    def start_logging(
        self,
        channels: Union[int, List[int]],
        interval: float = 1.0,
        duration: Optional[float] = None,
        callback: Optional[callable] = None,
    ) -> List[List[Reading]]:
        """Start continuous data logging.

        Args:
            channels: Channels to log
            interval: Time between scans in seconds
            duration: Total logging duration (None for manual stop)
            callback: Optional callback function(readings) called after each scan

        Returns:
            List of reading lists (one per scan)
        """
        # Configure scan
        self.set_scan_list(channels)
        self.set_trigger_source("TIM")
        self.set_trigger_timer(interval)

        if duration:
            num_scans = int(duration / interval)
            self.set_trigger_count(num_scans)
        else:
            self.set_trigger_count("INF")

        all_readings = []
        self.initiate()

        try:
            start_time = time.time()
            while True:
                if duration and (time.time() - start_time) >= duration:
                    break

                # Wait for data
                time.sleep(interval * 0.9)

                # Read available data
                try:
                    points = self.get_data_points()
                    if points > 0:
                        readings = self.read_and_remove(points)
                        all_readings.append(readings)

                        if callback:
                            callback(readings)
                except Exception as e:
                    logger.warning(f"Error reading data: {e}")

        except KeyboardInterrupt:
            logger.info("Logging interrupted by user")
        finally:
            self.abort()

        return all_readings

    # --- Helper Methods ---

    def _parse_readings(self, response: str) -> List[Reading]:
        """Parse comma-separated readings from response string."""
        readings = []

        if not response or response.strip() == "":
            return readings

        # Split by comma and parse each value
        values = response.strip().split(",")

        for val in values:
            val = val.strip()
            if not val:
                continue

            try:
                # Try to parse as float
                reading = Reading(value=float(val))
                readings.append(reading)
            except ValueError:
                # May contain additional info like channel or alarm state
                logger.debug(f"Could not parse reading value: {val}")

        return readings

    def _parse_idn(self, idn: str) -> Dict[str, str]:
        """Parse *IDN? response into dictionary."""
        parts = idn.split(",")
        return {
            "manufacturer": parts[0].strip() if len(parts) > 0 else "",
            "model": parts[1].strip() if len(parts) > 1 else "",
            "serial": parts[2].strip() if len(parts) > 2 else "",
            "firmware": parts[3].strip() if len(parts) > 3 else "",
        }

    def _get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string for this model."""
        if self._scpi_commands is None:
            raise RuntimeError("SCPI commands not initialized. Call connect() first.")
        return self._scpi_commands.get_command(command_name, **kwargs)

    @property
    def device_info(self) -> Optional[Dict[str, str]]:
        """Get parsed device information."""
        return self._device_info

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

    def __repr__(self) -> str:
        """String representation."""
        if self.is_connected and self._device_info:
            manufacturer = self._device_info.get("manufacturer", "Unknown")
            model = self._device_info.get("model", "Unknown")
            return f"DataLogger({manufacturer} {model} at {self.host}:{self.port})"
        return f"DataLogger({self.host}:{self.port}, disconnected)"
