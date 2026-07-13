"""TCP socket implementation for SCPI communication."""

import socket
import time
from typing import Optional, Tuple

from scpi_control import exceptions
from scpi_control.connection.base import BaseConnection


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

        with self.lock:
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

        with self.lock:
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
        with self.lock:
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

        with self.lock:
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
                    return self._read_ieee_block()
            except socket.error as e:
                self._connected = False
                command_context = f" after '{self._last_command}'" if self._last_command else ""
                raise exceptions.SiglentConnectionError(f"Read error from {self.host}:{self.port}{command_context}: {e}")

    def _read_ieee_block(self) -> bytes:
        """Read a response that may carry an IEEE 488.2 definite-length block.

        Once a '#<n><length>' header is seen, reads exactly the declared
        number of bytes (plus the trailing terminator when present) instead
        of draining until the line goes idle. Responses without a block
        header keep the legacy idle-drain behavior.

        Raises:
            SiglentTimeoutError: If no data arrives at all, or the line
                stalls before the declared byte count is received.
        """
        data = b""
        expected_total: Optional[int] = None
        header_absent = False

        try:
            while True:
                try:
                    chunk = self._socket.recv(self._buffer_size)
                except socket.timeout:
                    command_context = f"for '{self._last_command}' " if self._last_command else ""
                    if expected_total is not None:
                        raise exceptions.SiglentTimeoutError(f"Binary read stalled {command_context}(received {len(data)} of {expected_total} declared bytes) from {self.host}:{self.port}")
                    if data:
                        # Headerless response finished (line went idle)
                        return data
                    raise exceptions.SiglentTimeoutError(f"Binary read timeout {command_context}- no data received from {self.host}:{self.port}")

                if not chunk:
                    return data  # Peer closed the connection

                data += chunk

                if expected_total is None and not header_absent:
                    expected_total, header_absent = self._parse_block_total(data)
                    if header_absent:
                        # Legacy path: no way to know the length, drain until idle
                        self._socket.settimeout(0.5)

                if expected_total is not None and len(data) >= expected_total:
                    data += self._drain_terminator()
                    return data
        except socket.error as e:
            if not isinstance(e, socket.timeout):
                self._connected = False
                command_context = f" after '{self._last_command}'" if self._last_command else ""
                raise exceptions.SiglentConnectionError(f"Read error from {self.host}:{self.port}{command_context}: {e}")
            raise
        finally:
            self._socket.settimeout(self.timeout)

    def _parse_block_total(self, data: bytes) -> Tuple[Optional[int], bool]:
        """Locate an IEEE 488.2 block header and compute the total response size.

        Returns:
            (total_bytes, header_absent): total_bytes is prefix + '#' + digit
            count + length digits + payload, or None if the header has not
            fully arrived yet. header_absent is True when the response is
            judged to have no definite-length block at all.
        """
        idx = data.find(b"#")
        if idx == -1:
            # Command echo prefixes are short; if no '#' this deep in, there is no block
            return None, len(data) >= 128
        if len(data) < idx + 2:
            return None, False  # '#' seen, digit count not yet arrived
        digit_char = data[idx + 1 : idx + 2]
        if not digit_char.isdigit() or digit_char == b"0":
            # '#0' (indefinite length) or stray '#': not a definite-length block
            return None, True
        num_digits = int(digit_char)
        if len(data) < idx + 2 + num_digits:
            return None, False  # Length field not yet complete
        length_field = data[idx + 2 : idx + 2 + num_digits]
        if not length_field.isdigit():
            return None, True
        payload_length = int(length_field)
        return idx + 2 + num_digits + payload_length, False

    def _drain_terminator(self) -> bytes:
        """Opportunistically read the trailing terminator ("\\n\\n") after a block."""
        self._socket.settimeout(0.05)
        try:
            return self._socket.recv(2)
        except socket.timeout:
            return b""
        finally:
            self._socket.settimeout(self.timeout)

    def __repr__(self) -> str:
        """String representation of connection."""
        status = "connected" if self._connected else "disconnected"
        return f"SocketConnection({self.host}:{self.port}, {status})"
