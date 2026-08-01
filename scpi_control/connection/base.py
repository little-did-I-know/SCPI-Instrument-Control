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

    def drain_input(self) -> int:
        """Discard bytes the instrument has already queued; return the count.

        "Throw away what is queued" and "abort what the instrument is doing"
        are DIFFERENT requests, which is why they are different methods. This
        one is passive: it consumes buffered bytes and takes no protocol-level
        action at all. Use it for housekeeping after a completed exchange --
        e.g. the terminator a scope sends behind a screen dump, which belongs
        to nobody and would otherwise become the next response. Use `resync()`
        when the session position is genuinely unknown and recovering it is
        worth interrupting the instrument for.

        No-op by default, returning 0: a transport with no readable buffer has
        nothing to discard. Overridden by SocketConnection and VISAConnection.

        Best-effort in what it RECOVERS: it can only discard bytes that have
        ARRIVED, so a reply still in flight is not covered. It does not promise
        never to RAISE -- a transport fault during the drain is a real fault
        and is reported rather than hidden. Callers for whom the drain is
        incidental to work already completed should guard the call.
        """
        return 0

    def resync(self) -> int:
        """Recover a session whose position is unknown; return bytes discarded.

        The active counterpart to `drain_input()`: this one MAY take a
        protocol-level action -- VISAConnection prefers a VISA device clear,
        which aborts the instrument's pending operation. That is not something
        a caller who merely wants the buffer emptied should trigger, so callers
        with buffered leftovers and nothing to recover want `drain_input()`.

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
