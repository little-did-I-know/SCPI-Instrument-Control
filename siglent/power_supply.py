"""Main PowerSupply class for controlling SCPI power supplies.

Supports generic SCPI-99 compliant power supplies and Siglent SPD series models.

Installation:
    pip install "Siglent-Oscilloscope"
    # Or with power supply examples:
    pip install "Siglent-Oscilloscope[power-supply-beta]"

Features:
    - Multiple connection types: Ethernet/LAN, USB, GPIB, Serial
    - Full control of voltage, current, and output state
    - Model-specific capability detection
    - Data logging and automation support
    - Context manager support for automatic connection management

Feedback:
    Please report issues and suggestions at:
    https://github.com/little-did-I-know/Siglent-Oscilloscope/issues
"""

import logging
from typing import Any, Dict, List, Optional

from siglent import exceptions
from siglent.connection import BaseConnection, SocketConnection
from siglent.power_supply_output import PowerSupplyOutput
from siglent.psu_models import PSUCapability, detect_psu_from_idn
from siglent.psu_scpi_commands import PSUSCPICommandSet

logger = logging.getLogger(__name__)


class PowerSupply:
    """Main class for controlling SCPI power supplies.

    This class provides a high-level interface for controlling power supply
    functions including voltage/current settings, output control, and measurements.

    Supports both generic SCPI-99 power supplies and Siglent SPD series models
    with automatic model detection and capability-based feature availability.

    Example:
        >>> psu = PowerSupply('192.168.1.200')
        >>> psu.connect()
        >>> print(psu.identify())
        >>> print(f"Model: {psu.model_capability.model_name}")
        >>> print(f"Outputs: {psu.model_capability.num_outputs}")
        >>> psu.output1.voltage = 5.0
        >>> psu.output1.current = 1.0
        >>> psu.output1.enabled = True
        >>> print(f"Actual voltage: {psu.output1.measure_voltage()}V")
        >>> psu.disconnect()

        Or using context manager:
        >>> with PowerSupply('192.168.1.200') as psu:
        ...     psu.output1.voltage = 12.0
        ...     psu.output1.enable()
    """

    def __init__(
        self,
        host: str,
        port: int = 5024,
        timeout: float = 5.0,
        connection: Optional[BaseConnection] = None,
    ):
        """Initialize power supply connection.

        Args:
            host: IP address or hostname of the power supply
            port: TCP port for SCPI communication (default: 5024)
            timeout: Command timeout in seconds (default: 5.0)
            connection: Optional custom connection object (uses SocketConnection if None)

        Note:
            Outputs are created dynamically after connection based on model capabilities.
            Call connect() to establish connection and initialize outputs.
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
        self.model_capability: Optional[PSUCapability] = None
        self._scpi_commands: Optional[PSUSCPICommandSet] = None

        # Device information (populated after connection)
        self._device_info: Optional[Dict[str, str]] = None

        # Outputs will be created dynamically based on model capability
        # After connection, outputs will be available as self.output1, self.output2, etc.

    def connect(self) -> None:
        """Establish connection to the power supply.

        This method connects to the power supply, detects the model, and initializes
        model-specific capabilities and outputs.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        logger.info(f"Connecting to power supply at {self.host}:{self.port}")
        self._connection.connect()
        logger.info("Connected successfully")

        # Verify connection by getting device identification
        try:
            idn_string = self.identify()
            self._device_info = self._parse_idn(idn_string)
            logger.info(f"Connected to: {self._device_info.get('manufacturer', 'Unknown')} " f"{self._device_info.get('model', 'Unknown')}")

            # Detect model capability
            self.model_capability = detect_psu_from_idn(idn_string)
            logger.info(f"Model capability: {self.model_capability}")

            # Initialize SCPI command set for this model
            self._scpi_commands = PSUSCPICommandSet(self.model_capability.scpi_variant)
            logger.info(f"Using SCPI variant: {self.model_capability.scpi_variant}")

            # Create outputs dynamically based on model capability
            self._create_outputs()

            # Update device info with capability information
            self._device_info["manufacturer"] = self.model_capability.manufacturer
            self._device_info["num_outputs"] = str(self.model_capability.num_outputs)

        except Exception as e:
            logger.error(f"Failed to identify device or initialize: {e}")
            self.disconnect()
            raise exceptions.SiglentConnectionError(f"Connected but failed to identify device: {e}")

    def disconnect(self) -> None:
        """Close connection to the power supply."""
        logger.info("Disconnecting from power supply")
        self._connection.disconnect()
        self._device_info = None
        self.model_capability = None
        self._scpi_commands = None

        # Remove dynamically created outputs
        for i in range(1, 4):  # Check all possible outputs
            output_attr = f"output{i}"
            if hasattr(self, output_attr):
                delattr(self, output_attr)

    @property
    def is_connected(self) -> bool:
        """Check if connected to power supply.

        Returns:
            True if connected, False otherwise
        """
        return self._connection.is_connected

    def write(self, command: str) -> None:
        """Send a SCPI command to the power supply.

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
            Response string from power supply

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
            'Siglent Technologies,SPD3303X,SPD3XXXXXXXXXXX,V1.01'
        """
        return self.query("*IDN?")

    def reset(self) -> None:
        """Reset power supply to default settings.

        Note: This may take several seconds to complete and will turn off all outputs.
        """
        logger.info("Resetting power supply to defaults")
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

        This is a safety method to quickly turn off all power supply outputs.
        """
        if self.model_capability is None:
            logger.warning("Cannot disable outputs - not connected")
            return

        logger.info("Disabling all outputs (safety)")
        for i in range(1, self.model_capability.num_outputs + 1):
            output = getattr(self, f"output{i}", None)
            if output:
                try:
                    output.disable()
                except Exception as e:
                    logger.error(f"Failed to disable output {i}: {e}")

    # --- Advanced Features ---

    @property
    def tracking_mode(self) -> str:
        """Get tracking mode for multi-output PSUs.

        Returns:
            Tracking mode: 'INDEPENDENT', 'SERIES', or 'PARALLEL'

        Raises:
            NotImplementedError: If tracking is not supported by this model
        """
        if not self.model_capability.has_tracking:
            raise NotImplementedError(f"Tracking mode not supported on {self.model_capability.model_name}")

        cmd = self._get_command("get_tracking")
        response = self.query(cmd)
        return response.strip().upper()

    @tracking_mode.setter
    def tracking_mode(self, mode: str) -> None:
        """Set tracking mode for multi-output PSUs.

        Args:
            mode: Tracking mode - 'INDEPENDENT', 'SERIES', or 'PARALLEL'

        Raises:
            NotImplementedError: If tracking is not supported by this model
            ValueError: If mode is invalid
        """
        if not self.model_capability.has_tracking:
            raise NotImplementedError(f"Tracking mode not supported on {self.model_capability.model_name}")

        mode = mode.upper()
        valid_modes = ["INDEPENDENT", "SERIES", "PARALLEL"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid tracking mode: {mode}. Must be one of {valid_modes}")

        cmd = self._get_command("set_tracking", mode=mode)
        self.write(cmd)
        logger.info(f"Tracking mode set to {mode}")

    def set_independent_mode(self) -> None:
        """Set outputs to independent mode (default)."""
        self.tracking_mode = "INDEPENDENT"

    def set_series_mode(self) -> None:
        """Set outputs to series tracking mode.

        In series mode, output voltages add up while current remains the same.
        """
        self.tracking_mode = "SERIES"

    def set_parallel_mode(self) -> None:
        """Set outputs to parallel tracking mode.

        In parallel mode, output currents add up while voltage remains the same.
        """
        self.tracking_mode = "PARALLEL"

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

    def _create_outputs(self) -> None:
        """Create output objects dynamically based on model capability.

        Outputs are created as attributes (self.output1, self.output2, etc.)
        based on the number of outputs supported by the model.
        """
        if self.model_capability is None:
            raise RuntimeError("Model capability not initialized. Call connect() first.")

        num_outputs = self.model_capability.num_outputs
        logger.info(f"Creating {num_outputs} output(s)")

        for i, spec in enumerate(self.model_capability.output_specs, start=1):
            output = PowerSupplyOutput(self, spec)
            setattr(self, f"output{i}", output)
            logger.debug(f"Created output{i}: {spec}")

    @property
    def supported_outputs(self) -> List[int]:
        """Get list of supported output numbers for this model.

        Returns:
            List of output numbers (e.g., [1, 2, 3] for 3-output model)
            Empty list if not connected

        Example:
            >>> psu.connect()
            >>> print(psu.supported_outputs)
            [1, 2, 3]
        """
        if self.model_capability is None:
            return []
        return list(range(1, self.model_capability.num_outputs + 1))

    def get_output(self, output_num: int) -> Optional[PowerSupplyOutput]:
        """Get output object by number.

        Args:
            output_num: Output number (1-based)

        Returns:
            PowerSupplyOutput object or None if output doesn't exist

        Example:
            >>> psu.connect()
            >>> out1 = psu.get_output(1)
        """
        output_attr = f"output{output_num}"
        return getattr(self, output_attr, None)

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
            >>> psu.connect()
            >>> cmd = psu._get_command("set_voltage", ch=1, voltage=5.0)
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
            manufacturer = self._device_info.get("manufacturer", "Unknown")
            model = self._device_info.get("model", "Unknown")
            return f"PowerSupply({manufacturer} {model} at {self.host}:{self.port})"
        return f"PowerSupply({self.host}:{self.port}, disconnected)"
