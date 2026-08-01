"""Abstract base class for oscilloscope connections."""

import threading
from abc import ABC, abstractmethod
from typing import Optional, Union

from scpi_control.connection.framing import Framing


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
        # Reentrant so query() can hold it across its own write()/read() calls.
        # Callers doing compound exchanges (write + read_raw) must hold it too.
        self.lock = threading.RLock()

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
    def read_raw(self, size: Optional[int] = None, framing: Framing = Framing.AUTO) -> bytes:
        """Read raw binary data from the instrument.

        Args:
            size: Number of bytes to read (None reads one whole response).
            framing: What the CALLER knows the response to be. Declaring it is
                what keeps the transport from inferring framing out of binary
                payload bytes (backend review 2026-07-31, High-6).

        Returns:
            Raw binary data

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If read times out
        """
        pass

    def resync(self) -> int:
        """Discard anything the instrument left unread; return the byte count.

        No-op by default. A transport that can be left mid-response overrides
        this -- see SocketConnection, where a reply that arrives after a
        timeout would otherwise be returned to the NEXT caller (High-7).
        """
        return 0

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
