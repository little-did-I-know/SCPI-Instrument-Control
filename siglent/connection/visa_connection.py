"""VISA-based connection for USB, GPIB, Serial, and TCP/IP instruments.

Supports multiple transport protocols using PyVISA:
- USB (USB-TMC)
- GPIB (IEEE-488)
- Serial (RS-232/RS-485)
- TCP/IP (VXI-11, raw socket)

Requires pyvisa package:
    pip install "Siglent-Oscilloscope[usb]"

For pure Python backend (no NI-VISA required):
    pip install pyvisa-py
"""

import logging
from typing import Optional

from siglent.connection.base import BaseConnection
from siglent.exceptions import CommandError, SiglentConnectionError, SiglentTimeoutError

logger = logging.getLogger(__name__)

# Optional import - only required if user wants USB/VISA support
try:
    import pyvisa

    PYVISA_AVAILABLE = True
except ImportError:
    PYVISA_AVAILABLE = False
    pyvisa = None


class VISAConnection(BaseConnection):
    """VISA-based connection supporting USB, GPIB, Serial, and Ethernet.

    Uses PyVISA to communicate with instruments over multiple transport protocols.
    Supports the same SCPI command interface as SocketConnection.

    Supported resource strings:
        - USB: "USB0::0xF4EC::0xEE38::SPD3XXXXXXXXXXX::INSTR"
        - GPIB: "GPIB0::12::INSTR"
        - Serial: "ASRL3::INSTR" or "COM3"
        - TCP/IP: "TCPIP0::192.168.1.100::5024::SOCKET"

    Example:
        >>> # USB connection
        >>> from siglent import PowerSupply
        >>> from siglent.connection import VISAConnection
        >>> conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X123456::INSTR")
        >>> psu = PowerSupply(host="", connection=conn)
        >>> psu.connect()
        >>> print(psu.identify())

        >>> # GPIB connection
        >>> conn = VISAConnection("GPIB0::12::INSTR")
        >>> psu = PowerSupply(host="", connection=conn)
        >>> psu.connect()

    Note:
        Requires PyVISA: pip install "Siglent-Oscilloscope[usb]"
        Optional: pip install pyvisa-py (pure Python backend, no NI-VISA needed)
    """

    def __init__(
        self,
        resource_string: str,
        timeout: float = 5.0,
        backend: str = "@py",
        read_termination: str = "\n",
        write_termination: str = "\n",
    ):
        """Initialize VISA connection.

        Args:
            resource_string: VISA resource identifier
                Examples:
                - "USB0::0xF4EC::0xEE38::SPD3XXXXXXXXXXX::INSTR"
                - "GPIB0::12::INSTR"
                - "ASRL3::INSTR"
                - "TCPIP0::192.168.1.100::INSTR"
            timeout: Command timeout in seconds (default: 5.0)
            backend: VISA backend to use (default: "@py" for pyvisa-py)
                - "@py": Pure Python backend (no NI-VISA needed)
                - "": Default system backend (usually NI-VISA)
                - "@sim": Simulation backend for testing
            read_termination: Read termination character(s) (default: "\\n")
            write_termination: Write termination character(s) (default: "\\n")

        Raises:
            ImportError: If pyvisa is not installed
            SiglentConnectionError: If backend initialization fails
        """
        if not PYVISA_AVAILABLE:
            raise ImportError("PyVISA is required for USB/VISA connections.\n" "Install with: pip install 'Siglent-Oscilloscope[usb]'\n" "For pure Python backend (no NI-VISA): pip install pyvisa-py")

        self.resource_string = resource_string
        self.timeout = timeout
        self.backend = backend
        self.read_termination = read_termination
        self.write_termination = write_termination

        self._resource_manager: Optional[pyvisa.ResourceManager] = None
        self._resource: Optional[pyvisa.resources.MessageBasedResource] = None

        logger.info(f"VISAConnection initialized: {resource_string}")
        logger.debug(f"Backend: {backend}, Timeout: {timeout}s")

    def connect(self) -> None:
        """Establish VISA connection to the instrument.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        try:
            # Initialize resource manager with specified backend
            logger.info(f"Opening VISA resource manager (backend: {self.backend})")
            self._resource_manager = pyvisa.ResourceManager(self.backend)

            # Open the resource
            logger.info(f"Connecting to VISA resource: {self.resource_string}")
            self._resource = self._resource_manager.open_resource(self.resource_string)

            # Configure resource
            self._resource.timeout = int(self.timeout * 1000)  # VISA uses milliseconds
            self._resource.read_termination = self.read_termination
            self._resource.write_termination = self.write_termination

            # For serial connections, configure additional parameters
            if "ASRL" in self.resource_string or "COM" in self.resource_string:
                self._configure_serial()

            logger.info(f"VISA connection established: {self.resource_string}")

        except pyvisa.errors.VisaIOError as e:
            error_msg = f"Failed to connect to VISA resource {self.resource_string}: {e}"
            logger.error(error_msg)
            raise SiglentConnectionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error connecting to {self.resource_string}: {e}"
            logger.error(error_msg)
            raise SiglentConnectionError(error_msg)

    def disconnect(self) -> None:
        """Close VISA connection to the instrument."""
        logger.info("Disconnecting from VISA resource")

        if self._resource is not None:
            try:
                self._resource.close()
                logger.debug("VISA resource closed")
            except Exception as e:
                logger.warning(f"Error closing VISA resource: {e}")
            finally:
                self._resource = None

        if self._resource_manager is not None:
            try:
                self._resource_manager.close()
                logger.debug("VISA resource manager closed")
            except Exception as e:
                logger.warning(f"Error closing resource manager: {e}")
            finally:
                self._resource_manager = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to the instrument.

        Returns:
            True if connected, False otherwise
        """
        return self._resource is not None

    def write(self, command: str) -> None:
        """Send a SCPI command to the instrument.

        Args:
            command: SCPI command string

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If write times out
            CommandError: If command contains invalid characters
        """
        if not self.is_connected:
            raise SiglentConnectionError("Not connected to VISA resource")

        # Validate command for ASCII-only
        try:
            command.encode("ascii")
        except UnicodeEncodeError:
            raise CommandError(f"SCPI command contains non-ASCII characters: {command!r}")

        try:
            logger.debug(f"VISA Write: {command}")
            self._resource.write(command)

        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                error_msg = f"Timeout writing command to {self.resource_string}: {command}"
                logger.error(error_msg)
                raise SiglentTimeoutError(error_msg)
            else:
                error_msg = f"VISA write error on {self.resource_string}: {e}"
                logger.error(error_msg)
                raise SiglentConnectionError(error_msg)

    def query(self, command: str) -> str:
        """Send a SCPI query and read the response.

        Args:
            command: SCPI query command

        Returns:
            Response string from instrument (stripped of whitespace)

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If query times out
            CommandError: If command contains invalid characters
        """
        if not self.is_connected:
            raise SiglentConnectionError("Not connected to VISA resource")

        # Validate command for ASCII-only
        try:
            command.encode("ascii")
        except UnicodeEncodeError:
            raise CommandError(f"SCPI command contains non-ASCII characters: {command!r}")

        try:
            logger.debug(f"VISA Query: {command}")
            response = self._resource.query(command)
            logger.debug(f"VISA Response: {response!r}")
            return response.strip()

        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                error_msg = f"Timeout querying {self.resource_string}: {command}"
                logger.error(error_msg)
                raise SiglentTimeoutError(error_msg)
            else:
                error_msg = f"VISA query error on {self.resource_string}: {e}"
                logger.error(error_msg)
                raise SiglentConnectionError(error_msg)

    def query_binary(self, command: str, max_bytes: int = 1000000) -> bytes:
        """Send a SCPI query and read binary response.

        Args:
            command: SCPI query command
            max_bytes: Maximum bytes to read (default: 1MB)

        Returns:
            Binary response data

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If query times out
        """
        if not self.is_connected:
            raise SiglentConnectionError("Not connected to VISA resource")

        try:
            logger.debug(f"VISA Binary Query: {command}")
            self._resource.write(command)

            # Read binary data
            response = self._resource.read_bytes(max_bytes)
            logger.debug(f"VISA Binary Response: {len(response)} bytes")
            return response

        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                error_msg = f"Timeout on binary query {self.resource_string}: {command}"
                logger.error(error_msg)
                raise SiglentTimeoutError(error_msg)
            else:
                error_msg = f"VISA binary query error: {e}"
                logger.error(error_msg)
                raise SiglentConnectionError(error_msg)

    def _configure_serial(self) -> None:
        """Configure serial port parameters for ASRL/COM resources.

        Sets common defaults for Siglent instruments:
        - Baud rate: 9600
        - Data bits: 8
        - Parity: None
        - Stop bits: 1
        - Flow control: None
        """
        try:
            # These are typical defaults for Siglent instruments
            self._resource.baud_rate = 9600
            self._resource.data_bits = 8
            self._resource.parity = pyvisa.constants.Parity.none
            self._resource.stop_bits = pyvisa.constants.StopBits.one
            self._resource.flow_control = pyvisa.constants.ControlFlow.none

            logger.info(f"Serial port configured: 9600 8N1, resource={self.resource_string}")

        except Exception as e:
            logger.warning(f"Could not configure serial parameters: {e}")

    def __repr__(self) -> str:
        """String representation of the connection."""
        status = "connected" if self.is_connected else "disconnected"
        return f"VISAConnection({self.resource_string!r}, {status})"


def list_visa_resources(backend: str = "@py") -> list:
    """List all available VISA resources.

    Args:
        backend: VISA backend to use (default: "@py" for pyvisa-py)

    Returns:
        List of VISA resource strings

    Raises:
        ImportError: If pyvisa is not installed

    Example:
        >>> from siglent.connection.visa_connection import list_visa_resources
        >>> resources = list_visa_resources()
        >>> for res in resources:
        ...     print(res)
        USB0::0xF4EC::0xEE38::SPD3X123456::INSTR
        GPIB0::12::INSTR
    """
    if not PYVISA_AVAILABLE:
        raise ImportError("PyVISA is required for VISA resource discovery.\n" "Install with: pip install 'Siglent-Oscilloscope[usb]'")

    try:
        rm = pyvisa.ResourceManager(backend)
        resources = rm.list_resources()
        rm.close()
        return list(resources)
    except Exception as e:
        logger.error(f"Error listing VISA resources: {e}")
        return []


def find_siglent_devices(backend: str = "@py") -> list:
    """Find all connected Siglent devices via VISA.

    Args:
        backend: VISA backend to use (default: "@py")

    Returns:
        List of tuples: (resource_string, device_info)

    Example:
        >>> from siglent.connection.visa_connection import find_siglent_devices
        >>> devices = find_siglent_devices()
        >>> for resource, info in devices:
        ...     print(f"{resource}: {info}")
        USB0::0xF4EC::...: Siglent Technologies,SPD3303X-E,...
    """
    if not PYVISA_AVAILABLE:
        raise ImportError("PyVISA is required.\n" "Install with: pip install 'Siglent-Oscilloscope[usb]'")

    siglent_devices = []

    try:
        rm = pyvisa.ResourceManager(backend)
        resources = rm.list_resources()

        for resource in resources:
            try:
                # Try to open and query *IDN?
                instr = rm.open_resource(resource)
                instr.timeout = 2000  # 2 second timeout for discovery
                idn = instr.query("*IDN?").strip()
                instr.close()

                # Check if Siglent device
                if "siglent" in idn.lower():
                    siglent_devices.append((resource, idn))
                    logger.info(f"Found Siglent device: {resource} - {idn}")

            except Exception as e:
                logger.debug(f"Could not query {resource}: {e}")
                continue

        rm.close()

    except Exception as e:
        logger.error(f"Error finding Siglent devices: {e}")

    return siglent_devices
