"""Main Oscilloscope class for controlling Siglent oscilloscopes.

Supports multiple Siglent oscilloscope series including SDS800X HD, SDS1000X-E,
SDS2000X Plus, and SDS5000X.
"""

import logging
from typing import Any, Dict, List, Optional

from siglent import exceptions
from siglent.analysis import FFTAnalyzer
from siglent.channel import Channel
from siglent.connection import BaseConnection, SocketConnection
from siglent.math_channel import MathChannel
from siglent.measurement import Measurement
from siglent.models import ModelCapability, detect_model_from_idn
from siglent.scpi_commands import SCPICommandSet
from siglent.screen_capture import ScreenCapture
from siglent.trigger import Trigger
from siglent.waveform import Waveform, WaveformData

logger = logging.getLogger(__name__)


class Oscilloscope:
    """Main class for controlling Siglent oscilloscopes.

    This class provides a high-level interface for controlling oscilloscope
    functions including channels, triggers, waveform acquisition, and measurements.

    Supports multiple Siglent oscilloscope series with automatic model detection
    and capability-based feature availability.

    Example:
        >>> scope = Oscilloscope('192.168.1.100')
        >>> scope.connect()
        >>> print(scope.identify())
        >>> print(f"Model: {scope.model_capability.model_name}")
        >>> print(f"Channels: {scope.model_capability.num_channels}")
        >>> scope.disconnect()

        Or using context manager:
        >>> with Oscilloscope('192.168.1.100') as scope:
        ...     print(scope.identify())
    """

    def __init__(
        self,
        host: str,
        port: int = 5024,
        timeout: float = 5.0,
        connection: Optional[BaseConnection] = None,
    ):
        """Initialize oscilloscope connection.

        Args:
            host: IP address or hostname of the oscilloscope
            port: TCP port for SCPI communication (default: 5024)
            timeout: Command timeout in seconds (default: 5.0)
            connection: Optional custom connection object (uses SocketConnection if None)

        Note:
            Channels are created dynamically after connection based on model capabilities.
            Call connect() to establish connection and initialize channels.
        """
        self.host = host
        self.port = port
        self.timeout = timeout

        # Create connection
        if connection is not None:
            self._connection = connection
        else:
            self._connection = SocketConnection(host, port, timeout)

        # Model capability and SCPI commands (populated after connection)
        self.model_capability: Optional[ModelCapability] = None
        self._scpi_commands: Optional[SCPICommandSet] = None

        # Device information (populated after connection)
        self._device_info: Optional[Dict[str, str]] = None

        # Channels will be created dynamically based on model capability
        # After connection, channels will be available as self.channel1, self.channel2, etc.

        # Initialize trigger control
        self.trigger = Trigger(self)

        # Initialize waveform acquisition
        self.waveform = Waveform(self)

        # Initialize measurement control
        self.measurement = Measurement(self)

        # Initialize screen capture
        self.screen_capture = ScreenCapture(self)

        # Initialize math channels (available after connection)
        self.math1: Optional[MathChannel] = None
        self.math2: Optional[MathChannel] = None

        # Initialize FFT analyzer
        self.fft_analyzer = FFTAnalyzer()

        # Vector display (lazy-loaded, requires 'fun' extras)
        self._vector_display = None

    @property
    def vector_display(self):
        """Access vector graphics display functionality.

        Requires the 'fun' extras to be installed:
            pip install "Siglent-Oscilloscope[fun]"

        Returns:
            VectorDisplay instance for XY mode graphics

        Raises:
            ImportError: If 'fun' extras are not installed

        Example:
            >>> scope.vector_display.enable_xy_mode()
            >>> circle = Shape.circle(radius=0.8)
            >>> scope.vector_display.draw(circle)
        """
        if self._vector_display is None:
            try:
                from siglent.vector_graphics import VectorDisplay

                self._vector_display = VectorDisplay(self)
            except ImportError as e:
                raise ImportError("Vector graphics features require the 'fun' extras.\n" 'Install with: pip install "Siglent-Oscilloscope[fun]"') from e
        return self._vector_display

    def connect(self) -> None:
        """Establish connection to the oscilloscope.

        This method connects to the oscilloscope, detects the model, and initializes
        model-specific capabilities and channels.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        logger.info(f"Connecting to oscilloscope at {self.host}:{self.port}")
        self._connection.connect()
        logger.info("Connected successfully")

        # Verify connection by getting device identification
        try:
            idn_string = self.identify()
            self._device_info = self._parse_idn(idn_string)
            logger.info(f"Connected to: {self._device_info.get('model', 'Unknown')}")

            # Detect model capability
            self.model_capability = detect_model_from_idn(idn_string)
            logger.info(f"Model capability: {self.model_capability}")

            # Initialize SCPI command set for this model
            self._scpi_commands = SCPICommandSet(self.model_capability.scpi_variant)
            logger.info(f"Using SCPI variant: {self.model_capability.scpi_variant}")

            # Create channels dynamically based on model capability
            self._create_channels()

            # Create math channels
            self._create_math_channels()

            # Update device info with capability information
            self._device_info["series"] = self.model_capability.series
            self._device_info["num_channels"] = str(self.model_capability.num_channels)
            self._device_info["bandwidth_mhz"] = str(self.model_capability.bandwidth_mhz)

        except Exception as e:
            logger.error(f"Failed to identify device or initialize: {e}")
            self.disconnect()
            raise exceptions.SiglentConnectionError(f"Connected but failed to identify device: {e}")

    def disconnect(self) -> None:
        """Close connection to the oscilloscope."""
        logger.info("Disconnecting from oscilloscope")
        self._connection.disconnect()
        self._device_info = None
        self.model_capability = None
        self._scpi_commands = None

        # Remove dynamically created channels
        for i in range(1, 5):  # Check all possible channels
            channel_attr = f"channel{i}"
            if hasattr(self, channel_attr):
                delattr(self, channel_attr)

        # Clear math channels
        self.math1 = None
        self.math2 = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to oscilloscope.

        Returns:
            True if connected, False otherwise
        """
        return self._connection.is_connected

    def write(self, command: str) -> None:
        """Send a SCPI command to the oscilloscope.

        Args:
            command: SCPI command string

        Raises:
            SiglentConnectionError: If not connected
            CommandError: If command contains invalid characters
        """
        logger.debug(f"Write: {command}")
        self._connection.write(command)

    def query(self, command: str) -> str:
        """Send a SCPI query and get the response.

        Args:
            command: SCPI query command

        Returns:
            Response string from oscilloscope

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If query times out
            CommandError: If command contains invalid characters
        """
        logger.debug(f"Query: {command}")
        response = self._connection.query(command)
        logger.debug(f"Response: {response}")
        return response

    def read_raw(self, size: Optional[int] = None) -> bytes:
        """Read raw binary data from oscilloscope.

        Args:
            size: Number of bytes to read (None for all available)

        Returns:
            Raw binary data
        """
        return self._connection.read_raw(size)

    def identify(self) -> str:
        """Get device identification string.

        Returns:
            Device identification string (manufacturer, model, serial, firmware)

        Example:
            'Siglent Technologies,SDS824X HD,SERIAL123,1.0.0.0'
        """
        return self.query("*IDN?")

    def reset(self) -> None:
        """Reset oscilloscope to default settings.

        Note: This may take several seconds to complete.
        """
        logger.info("Resetting oscilloscope to defaults")
        self.write("*RST")

    def clear_status(self) -> None:
        """Clear status registers."""
        self.write("*CLS")

    def get_error(self) -> str:
        """Get the last error from the error queue.

        Returns:
            Error string (format: "code,description")
        """
        return self.query("SYST:ERR?")

    def wait_complete(self) -> None:
        """Wait for all pending operations to complete."""
        self.query("*OPC?")

    def trigger_single(self) -> None:
        """Set trigger mode to single and force a trigger."""
        self.write("TRIG_MODE SINGLE")
        self.write("ARM")

    def trigger_force(self) -> None:
        """Force a trigger event."""
        self.write("FRTR")

    def run(self) -> None:
        """Start acquisition (set to AUTO trigger mode)."""
        self.write("TRIG_MODE AUTO")

    def stop(self) -> None:
        """Stop acquisition."""
        self.write("STOP")

    @property
    def timebase(self) -> float:
        """Get timebase setting in seconds/division."""
        return self.waveform._get_timebase()

    @timebase.setter
    def timebase(self, seconds_per_div: float) -> None:
        """Set timebase (seconds/division)."""
        self.write(f"TDIV {seconds_per_div}")

    def set_timebase(self, seconds_per_div: float) -> None:
        """Set timebase (alias for timebase setter)."""
        self.timebase = seconds_per_div

    def auto_setup(self) -> None:
        """Perform automatic setup."""
        self.write("ASET")

    def get_waveform(self, channel: int) -> WaveformData:
        """Acquire waveform data from a channel.

        Convenience method that calls waveform.acquire().

        Args:
            channel: Channel number (1-4)

        Returns:
            WaveformData object with time and voltage arrays
        """
        return self.waveform.acquire(channel)

    @property
    def device_info(self) -> Optional[Dict[str, str]]:
        """Get parsed device information.

        Returns:
            Dictionary with keys: manufacturer, model, serial, firmware
            None if not connected
        """
        return self._device_info

    def _parse_idn(self, idn: str) -> Dict[str, str]:
        """Parse *IDN? response into dictionary.

        Args:
            idn: Identification string from *IDN? query

        Returns:
            Dictionary with manufacturer, model, serial, firmware
        """
        parts = idn.split(",")
        return {
            "manufacturer": parts[0].strip() if len(parts) > 0 else "",
            "model": parts[1].strip() if len(parts) > 1 else "",
            "serial": parts[2].strip() if len(parts) > 2 else "",
            "firmware": parts[3].strip() if len(parts) > 3 else "",
        }

    def _create_channels(self) -> None:
        """Create channel objects dynamically based on model capability.

        Channels are created as attributes (self.channel1, self.channel2, etc.)
        based on the number of channels supported by the model.
        """
        if self.model_capability is None:
            raise RuntimeError("Model capability not initialized. Call connect() first.")

        num_channels = self.model_capability.num_channels
        logger.info(f"Creating {num_channels} channel(s)")

        for i in range(1, num_channels + 1):
            channel = Channel(self, i)
            setattr(self, f"channel{i}", channel)
            logger.debug(f"Created channel{i}")

    def _create_math_channels(self) -> None:
        """Create math channel objects.

        Math channels are always created regardless of model, as they are
        client-side computations on acquired waveform data.
        """
        self.math1 = MathChannel(self, "M1")
        self.math2 = MathChannel(self, "M2")
        logger.info("Math channels M1 and M2 created")

    @property
    def supported_channels(self) -> List[int]:
        """Get list of supported channel numbers for this model.

        Returns:
            List of channel numbers (e.g., [1, 2, 3, 4] for 4-channel model)
            Empty list if not connected

        Example:
            >>> scope.connect()
            >>> print(scope.supported_channels)
            [1, 2, 3, 4]
        """
        if self.model_capability is None:
            return []
        return list(range(1, self.model_capability.num_channels + 1))

    def get_channel(self, channel_num: int) -> Optional[Channel]:
        """Get channel object by number.

        Args:
            channel_num: Channel number (1-based)

        Returns:
            Channel object or None if channel doesn't exist

        Example:
            >>> scope.connect()
            >>> ch1 = scope.get_channel(1)
        """
        channel_attr = f"channel{channel_num}"
        return getattr(self, channel_attr, None)

    def _get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string for this model.

        Uses the model-specific SCPI command set to retrieve the appropriate
        command syntax with parameter substitution.

        Args:
            command_name: Name of the command
            **kwargs: Parameters for command template substitution

        Returns:
            Formatted SCPI command string

        Raises:
            RuntimeError: If not connected or SCPI commands not initialized
            KeyError: If command_name is not found
            ValueError: If required parameters are missing

        Example:
            >>> scope.connect()
            >>> cmd = scope._get_command("set_voltage_div", ch=1, vdiv="1V")
        """
        if self._scpi_commands is None:
            raise RuntimeError("SCPI commands not initialized. Call connect() first.")

        return self._scpi_commands.get_command(command_name, **kwargs)

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
            model = self._device_info.get("model", "Unknown")
            return f"Oscilloscope({model} at {self.host}:{self.port})"
        return f"Oscilloscope({self.host}:{self.port}, disconnected)"
