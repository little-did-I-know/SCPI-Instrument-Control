"""Abstract base class for oscilloscope connections."""

from abc import ABC, abstractmethod
from typing import Optional, Union


class BaseConnection(ABC):
    """Abstract base class defining the connection interface for SCPI communication."""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        """Initialize connection parameters.

        Args:
            host: IP address or hostname of the oscilloscope
            port: TCP port number for SCPI communication
            timeout: Command timeout in seconds (default: 5.0)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the oscilloscope.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the oscilloscope."""
        pass

    @abstractmethod
    def write(self, command: str) -> None:
        """Send a SCPI command to the oscilloscope.

        Args:
            command: SCPI command string

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If command times out
            CommandError: If command fails
        """
        pass

    @abstractmethod
    def read(self) -> str:
        """Read response from the oscilloscope.

        Returns:
            Response string from oscilloscope

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If read times out
        """
        pass

    @abstractmethod
    def query(self, command: str) -> str:
        """Send a command and read the response.

        Args:
            command: SCPI query command

        Returns:
            Response string from oscilloscope

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If command times out
            CommandError: If command fails
        """
        pass

    @abstractmethod
    def read_raw(self, size: Optional[int] = None) -> bytes:
        """Read raw binary data from oscilloscope.

        Args:
            size: Number of bytes to read (None for all available)

        Returns:
            Raw binary data

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If read times out
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if connected to oscilloscope.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
