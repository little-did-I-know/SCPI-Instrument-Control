"""Main FunctionGenerator class for controlling SCPI function generators and AWGs.

Supports generic SCPI-99 compliant arbitrary waveform generators and Siglent SDG series models.

Installation:
    pip install "Siglent-Oscilloscope"

Features:
    - Multiple connection types: Ethernet/LAN, USB, GPIB, Serial
    - Full control of waveform type, frequency, amplitude, and offset
    - Model-specific capability detection
    - Basic waveform generation (sine, square, ramp, pulse)
    - Context manager support for automatic connection management

Feedback:
    Please report issues and suggestions at:
    https://github.com/little-did-I-know/Siglent-Oscilloscope/issues
"""

import logging
from typing import Dict, List, Optional

from scpi_control import exceptions
from scpi_control.awg_models import AWGCapability, detect_awg_from_idn
from scpi_control.awg_output import AWGOutput
from scpi_control.awg_scpi_commands import AWGSCPICommandSet
from scpi_control.connection import BaseConnection, SocketConnection

logger = logging.getLogger(__name__)


class FunctionGenerator:
    """Main class for controlling SCPI function generators and arbitrary waveform generators.

    This class provides a high-level interface for controlling function generator
    operations including waveform type, frequency, amplitude, and output control.

    Supports both generic SCPI-99 function generators and Siglent SDG series models
    with automatic model detection and capability-based feature availability.

    Example:
        >>> awg = FunctionGenerator('192.168.1.100')
        >>> awg.connect()
        >>> print(awg.identify())
        >>> print(f"Model: {awg.model_capability.model_name}")
        >>> print(f"Channels: {awg.model_capability.num_channels}")
        >>> awg.channel1.configure_sine(frequency=1000, amplitude=5.0)
        >>> awg.channel1.enable()
        >>> awg.disconnect()

        Or using context manager:
        >>> with FunctionGenerator('192.168.1.100') as awg:
        ...     awg.channel1.configure_square(frequency=10e3, amplitude=3.0)
        ...     awg.channel1.enable()
    """

    def __init__(
        self,
        host: str,
        port: int = 5024,
        timeout: float = 5.0,
        connection: Optional[BaseConnection] = None,
    ):
        """Initialize function generator connection.

        Args:
            host: IP address or hostname of the function generator
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
        self.model_capability: Optional[AWGCapability] = None
        self._scpi_commands: Optional[AWGSCPICommandSet] = None

        # Device information (populated after connection)
        self._device_info: Optional[Dict[str, str]] = None

        # Channels will be created dynamically based on model capability
        # After connection, channels will be available as self.channel1, self.channel2, etc.

    def connect(self) -> None:
        """Establish connection to the function generator.

        This method connects to the function generator, detects the model, and initializes
        model-specific capabilities and output channels.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        logger.info(f"Connecting to function generator at {self.host}:{self.port}")
        self._connection.connect()
        logger.info("Connected successfully")

        # Verify connection by getting device identification
        try:
            idn_string = self.identify()
            self._device_info = self._parse_idn(idn_string)
            logger.info(f"Connected to: {self._device_info.get('manufacturer', 'Unknown')} " f"{self._device_info.get('model', 'Unknown')}")

            # Detect model capability
            self.model_capability = detect_awg_from_idn(idn_string)
            logger.info(f"Model capability: {self.model_capability}")

            # Initialize SCPI command set for this model
            self._scpi_commands = AWGSCPICommandSet(self.model_capability.scpi_variant)
            logger.info(f"Using SCPI variant: {self.model_capability.scpi_variant}")

            # Create channels dynamically based on model capability
            self._create_channels()

            # Update device info with capability information
            self._device_info["manufacturer"] = self.model_capability.manufacturer
            self._device_info["num_channels"] = str(self.model_capability.num_channels)

        except Exception as e:
            logger.error(f"Failed to identify device or initialize: {e}")
            self.disconnect()
            raise exceptions.SiglentConnectionError(f"Connected but failed to identify device: {e}")

    def disconnect(self) -> None:
        """Close connection to the function generator."""
        logger.info("Disconnecting from function generator")
        self._connection.disconnect()
        self._device_info = None
        self.model_capability = None
        self._scpi_commands = None

        # Remove dynamically created channels
        for i in range(1, 5):  # Check all possible channels
            channel_attr = f"channel{i}"
            if hasattr(self, channel_attr):
                delattr(self, channel_attr)

    @property
    def is_connected(self) -> bool:
        """Check if connected to function generator.

        Returns:
            True if connected, False otherwise
        """
        return self._connection.is_connected

    def write(self, command: str) -> None:
        """Send a SCPI command to the function generator.

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
            Response string from function generator

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If query times out
            CommandError: If command contains invalid characters
        """
        logger.debug(f"Query: {command}")
        response = self._connection.query(command)
        logger.debug(f"Response: {response}")
        return response

    def identify(self) -> str:
        """Get device identification string.

        Returns:
            Device identification string (manufacturer, model, serial, firmware)

        Example:
            'Siglent Technologies,SDG1032X,SDG1XXXXXXXXXXX,2.01.01.37R1'
        """
        return self.query("*IDN?")

    def reset(self) -> None:
        """Reset function generator to default settings.

        Note: This may take several seconds to complete and will turn off all outputs.
        """
        logger.info("Resetting function generator to defaults")
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

    def all_outputs_off(self) -> None:
        """Disable all outputs (safety feature).

        This is a safety method to quickly turn off all function generator outputs.
        """
        if self.model_capability is None:
            logger.warning("Cannot disable outputs - not connected")
            return

        logger.info("Disabling all outputs (safety)")
        for i in range(1, self.model_capability.num_channels + 1):
            channel = getattr(self, f"channel{i}", None)
            if channel:
                try:
                    channel.disable()
                except Exception as e:
                    logger.error(f"Failed to disable channel {i}: {e}")

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

        for i, spec in enumerate(self.model_capability.channel_specs, start=1):
            channel = AWGOutput(self, spec)
            setattr(self, f"channel{i}", channel)
            logger.debug(f"Created channel{i}: {spec}")

    @property
    def supported_channels(self) -> List[int]:
        """Get list of supported channel numbers for this model.

        Returns:
            List of channel numbers (e.g., [1, 2] for 2-channel model)
            Empty list if not connected

        Example:
            >>> awg.connect()
            >>> print(awg.supported_channels)
            [1, 2]
        """
        if self.model_capability is None:
            return []
        return list(range(1, self.model_capability.num_channels + 1))

    def get_channel(self, channel_num: int) -> Optional[AWGOutput]:
        """Get channel object by number.

        Args:
            channel_num: Channel number (1-based)

        Returns:
            AWGOutput object or None if channel doesn't exist

        Example:
            >>> awg.connect()
            >>> ch1 = awg.get_channel(1)
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
            >>> awg.connect()
            >>> cmd = awg._get_command("set_frequency", ch=1, frequency=1000.0)
        """
        if self._scpi_commands is None:
            raise RuntimeError("SCPI commands not initialized. Call connect() first.")

        return self._scpi_commands.get_command(command_name, **kwargs)

    # --- Convenience Methods ---

    def sync_channels(self, phase_offset: float = 0.0) -> None:
        """Synchronize multiple channels with optional phase offset.

        Args:
            phase_offset: Phase offset in degrees for channel 2 relative to channel 1
                         (only applicable for 2-channel models)

        Note:
            This sets channel 1 to 0 degrees and channel 2 to the specified offset.
            Both channels should be configured to the same frequency for best results.
        """
        if self.model_capability is None or self.model_capability.num_channels < 2:
            logger.warning("Channel synchronization requires multi-channel model")
            return

        logger.info(f"Synchronizing channels with {phase_offset}° offset")
        self.channel1.phase = 0.0
        self.channel2.phase = phase_offset

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
            return f"FunctionGenerator({manufacturer} {model} at {self.host}:{self.port})"
        return f"FunctionGenerator({self.host}:{self.port}, disconnected)"
