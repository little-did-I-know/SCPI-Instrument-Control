"""TCP socket implementation for SCPI communication."""

import socket
import time
from typing import Optional

from siglent import exceptions
from siglent.connection.base import BaseConnection


class SocketConnection(BaseConnection):
    """TCP socket connection for SCPI commands over Ethernet."""

    def __init__(self, host: str, port: int = 5024, timeout: float = 5.0):
        """Initialize socket connection.

        Args:
            host: IP address or hostname of the oscilloscope
            port: TCP port number (default: 5024 for Siglent SCPI)
            timeout: Command timeout in seconds (default: 5.0)
        """
        super().__init__(host, port, timeout)
        self._socket: Optional[socket.socket] = None
        self._buffer_size = 4096
        self._last_command: Optional[str] = None

    def connect(self) -> None:
        """Establish TCP connection to the oscilloscope.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        if self._connected:
            return

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            self._connected = True
        except socket.timeout:
            raise exceptions.SiglentTimeoutError(f"Connection timeout: {self.host}:{self.port}")
        except socket.error as e:
            raise exceptions.SiglentConnectionError(f"Failed to connect to {self.host}:{self.port}: {e}")

    def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            finally:
                self._socket = None
                self._connected = False

    def write(self, command: str) -> None:
        """Send a SCPI command to the oscilloscope.

        Args:
            command: SCPI command string

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If command times out
            CommandError: If command contains non-ASCII characters or fails
        """
        if not self._connected or not self._socket:
            raise exceptions.SiglentConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        try:
            # Ensure command ends with newline
            if not command.endswith("\n"):
                command += "\n"

            # Track the most recent command for better error reporting
            self._last_command = command.strip()

            # Validate ASCII encoding before sending
            try:
                encoded_cmd = command.encode("ascii")
            except UnicodeEncodeError as e:
                raise exceptions.CommandError(f"SCPI command contains non-ASCII characters: {command!r}") from e

            self._socket.sendall(encoded_cmd)
        except socket.timeout:
            raise exceptions.SiglentTimeoutError(f"Command timeout for '{self._last_command}' on {self.host}:{self.port}")
        except socket.error as e:
            self._connected = False
            raise exceptions.SiglentConnectionError(f"Write error to {self.host}:{self.port} for command '{self._last_command}': {e}")

    def read(self) -> str:
        """Read response from the oscilloscope.

        Returns:
            Response string from oscilloscope

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If read times out
        """
        if not self._connected or not self._socket:
            raise exceptions.SiglentConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        try:
            data = b""
            start_time = time.time()

            while True:
                # Check for timeout in the read loop
                if time.time() - start_time > self.timeout:
                    command_context = f"for '{self._last_command}' " if self._last_command else ""
                    raise exceptions.SiglentTimeoutError(
                        f"Read timeout {command_context}after {self.timeout}s waiting for newline terminator " f"(received {len(data)} bytes so far) from {self.host}:{self.port}"
                    )

                chunk = self._socket.recv(self._buffer_size)
                if not chunk:
                    break
                data += chunk
                # Check if we received a complete response (ends with newline)
                if data.endswith(b"\n"):
                    break

            # Decode and strip whitespace and null bytes
            response = data.decode("ascii").strip()
            # Remove null bytes that some oscilloscopes prepend to responses
            response = response.lstrip("\x00")
            return response
        except socket.timeout:
            command_context = f"for '{self._last_command}' " if self._last_command else ""
            raise exceptions.SiglentTimeoutError(f"Read timeout {command_context}from {self.host}:{self.port}")
        except socket.error as e:
            self._connected = False
            command_context = f" while waiting for '{self._last_command}'" if self._last_command else ""
            raise exceptions.SiglentConnectionError(f"Read error from {self.host}:{self.port}{command_context}: {e}")

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
        self.write(command)
        # Small delay to allow oscilloscope to process
        time.sleep(0.01)
        return self.read()

    def read_raw(self, size: Optional[int] = None) -> bytes:
        """Read raw binary data from oscilloscope.

        Used for reading waveform data in binary format.

        Args:
            size: Number of bytes to read (None for all available)

        Returns:
            Raw binary data

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If read times out
        """
        if not self._connected or not self._socket:
            raise exceptions.SiglentConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        try:
            if size is not None:
                # Read exact number of bytes
                data = b""
                remaining = size
                while remaining > 0:
                    chunk = self._socket.recv(min(remaining, self._buffer_size))
                    if not chunk:
                        break
                    data += chunk
                    remaining -= len(chunk)
                return data
            else:
                # Read all available data
                data = b""
                self._socket.settimeout(0.5)  # Short timeout for binary reads
                try:
                    while True:
                        chunk = self._socket.recv(self._buffer_size)
                        if not chunk:
                            break
                        data += chunk
                except socket.timeout:
                    pass  # Expected when no more data
                finally:
                    self._socket.settimeout(self.timeout)  # Restore timeout
                return data
        except socket.error as e:
            self._connected = False
            command_context = f" after '{self._last_command}'" if self._last_command else ""
            raise exceptions.SiglentConnectionError(f"Read error from {self.host}:{self.port}{command_context}: {e}")

    def __repr__(self) -> str:
        """String representation of connection."""
        status = "connected" if self._connected else "disconnected"
        return f"SocketConnection({self.host}:{self.port}, {status})"
