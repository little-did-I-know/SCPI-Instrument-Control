"""TCP socket implementation for SCPI communication."""

import logging
import socket
import time
from typing import Optional

from scpi_control import exceptions
from scpi_control.connection.base import BaseConnection
from scpi_control.connection.framing import Framing, TransportClosed, TransportIdle, read_framed

logger = logging.getLogger(__name__)


class SocketConnection(BaseConnection):
    """TCP socket connection for SCPI commands over Ethernet."""

    def __init__(self, host: str, port: int = 5025, timeout: float = 5.0):
        """Initialize socket connection.

        Args:
            host: IP address or hostname of the oscilloscope
            port: TCP port number (default: 5025, the Siglent raw SCPI socket; 5024 is the telnet-style port with prompts and is not recommended)
            timeout: Command timeout in seconds (default: 5.0)
        """
        super().__init__(host, port, timeout)
        self._socket: Optional[socket.socket] = None
        self._buffer_size = 4096
        self._last_command: Optional[str] = None
        self._desynced = False

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
            # A fresh socket has nothing stranded on it from a prior session.
            self._desynced = False
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
                if self._desynced:
                    stranded = self._last_command
                    discarded = self.resync()
                    if discarded:
                        logger.warning("Discarded %d stale byte(s) left over from '%s' before sending on %s:%s", discarded, stranded, self.host, self.port)

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
                        self._desynced = True
                        command_context = f"for '{self._last_command}' " if self._last_command else ""
                        raise exceptions.SiglentTimeoutError(
                            f"Read timeout {command_context}after {self.timeout}s waiting for newline terminator " f"(received {len(data)} bytes so far) from {self.host}:{self.port}"
                        )

                    chunk = self._socket.recv(self._buffer_size)
                    if not chunk:
                        break
                    data += chunk
                    # Leading NUL and terminator bytes are both leftovers,
                    # never the start of this response: NUL is a normal
                    # prefix some instruments prepend to EVERY response, and
                    # a stray terminator is what's left behind by an earlier
                    # exchange. They must be stripped TOGETHER in one pass --
                    # a terminator can arrive ahead of a NUL-prefixed
                    # response in the SAME chunk, and stripping only one kind
                    # per iteration would break on endswith(b"\n") before the
                    # NUL underneath it was ever reached. Without stripping
                    # the terminator, a single stray "\n" satisfies the
                    # endswith() check below and returns an EMPTY response --
                    # which is how one late newline shifted every later
                    # answer by one query (High-7). Only warn when the run
                    # actually contained a terminator byte: a bare NUL prefix
                    # is normal and not worth logging on every query.
                    stripped = data.lstrip(b"\r\n\x00")
                    if stripped != data:
                        leftovers = data[: len(data) - len(stripped)]
                        if b"\n" in leftovers or b"\r" in leftovers:
                            logger.warning("Discarded %d stray terminator byte(s) left before the response to '%s' on %s:%s", len(leftovers), self._last_command, self.host, self.port)
                        data = stripped
                    if data.endswith(b"\n"):
                        break

                # Decode and strip whitespace and null bytes
                response = data.decode("ascii").strip()
                # Remove null bytes that some oscilloscopes prepend to responses
                response = response.lstrip("\x00")
                return response
            except socket.timeout:
                self._desynced = True
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

    def read_raw(self, size: Optional[int] = None, framing: Framing = Framing.AUTO) -> bytes:
        """Read raw binary data from oscilloscope.

        Used for reading waveform data in binary format.

        Args:
            size: Number of bytes to read (None for all available)
            framing: How to interpret the response when size is None (see
                connection.framing.Framing). Ignored when size is given.

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
                    return self._read_ieee_block(framing)
            except socket.timeout:
                self._desynced = True
                command_context = f"after '{self._last_command}' " if self._last_command else ""
                raise exceptions.SiglentTimeoutError(f"Raw read timeout {command_context}from {self.host}:{self.port}")
            except socket.error as e:
                self._connected = False
                command_context = f" after '{self._last_command}'" if self._last_command else ""
                raise exceptions.SiglentConnectionError(f"Read error from {self.host}:{self.port}{command_context}: {e}")

    def resync(self) -> int:
        """Discard anything the instrument left unread; return the byte count.

        Called automatically before the next send when a read has timed out.
        The bytes are gone either way -- the alternative is handing them to a
        caller who asked a different question (High-7).

        LIMIT, stated plainly: this discards what has ARRIVED. A reply still in
        flight when the next command goes out cannot be told apart from the
        answer to that command, and will still be misattributed. Callers that
        need certainty after a timeout should reconnect, or call resync()
        themselves once they are willing to wait for the straggler.
        """
        if not self._connected or not self._socket:
            self._desynced = False
            return 0
        discarded = 0
        with self.lock:
            previous = self._socket.gettimeout()
            self._socket.settimeout(0.05)
            try:
                while True:
                    try:
                        chunk = self._socket.recv(self._buffer_size)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    discarded += len(chunk)
            finally:
                self._socket.settimeout(previous if previous is not None else self.timeout)
                self._desynced = False
        return discarded

    def _read_chunk(self, hint: int) -> bytes:
        """Read up to `hint` bytes, translating socket states for read_framed.

        TransportIdle/TransportClosed are raised rather than returned so the
        framing module can tell a finished response from a cut-off one --
        the connection state that goes with a peer close is set here, because
        the transport is what knows about it.
        """
        try:
            chunk = self._socket.recv(min(hint, self._buffer_size))
        except socket.timeout:
            raise TransportIdle()
        if not chunk:
            logger.warning("Connection closed by %s:%s after '%s'", self.host, self.port, self._last_command)
            self._connected = False
            raise TransportClosed()
        return chunk

    def _read_ieee_block(self, framing: Framing = Framing.AUTO) -> bytes:
        """Read a response, framed as the caller declared (see connection.framing)."""
        context = f"{self.host}:{self.port}" + (f", after '{self._last_command}'" if self._last_command else "")
        try:
            result = read_framed(
                self._read_chunk,
                framing,
                max_chunk=self._buffer_size,
                # A headerless response has no length to read to, so fall back
                # to the pre-existing idle-drain: a shorter timeout is what
                # ends it.
                on_headerless=lambda: self._socket.settimeout(0.5),
                context=context,
            )
        except exceptions.SiglentTimeoutError:
            # A stalled or empty binary read leaves the stream position
            # unknown, exactly like a line-read timeout.
            self._desynced = True
            raise
        finally:
            self._socket.settimeout(self.timeout)

        if result.block_total is not None:
            # Task 1's reader never over-reads: while the header is unresolved
            # it asks for one byte at a time, and once the length is known the
            # hint is capped to exactly the remainder. So a completed block is
            # always exactly `block_total` bytes here, and the terminator is
            # deliberately still unread -- grab it so callers get the same
            # trailing bytes the legacy drain produced.
            return result.data + self._drain_terminator()
        return result.data

    def _drain_terminator(self) -> bytes:
        """Consume the terminator that follows a block -- and only that.

        The old fixed recv(2) was the bug: when the second "\\n" of "\\n\\n"
        arrived late, one newline stayed queued and became the entire next
        response. A single bounded peek fixes that without a loop: recv()
        returns as soon as ANY bytes are queued, so peeking never waits for a
        second terminator byte that may not have arrived yet -- a late
        partner is instead caught by read()'s leading-terminator skip. This
        still pays the 0.05s timeout only when nothing at all is queued yet,
        exactly like the old recv(2); unlike a peek-in-a-loop, it never pays
        that timeout a second time waiting for a byte that may never come
        (that would cost the live view 50ms on every single block read, not
        just a desynced one).

        Peeking 4 bytes rather than exactly 2 costs nothing extra (MSG_PEEK
        doesn't wait for a fuller buffer, same as any recv) but means real
        surplus right behind the terminator -- e.g. a queue of "\\n\\nXYZ" --
        is still visible in this one call, so the desync flag below still
        catches it instead of silently leaving it for whatever read() does
        next.
        """
        previous = self._socket.gettimeout()
        self._socket.settimeout(0.05)
        try:
            try:
                peeked = self._socket.recv(4, socket.MSG_PEEK)
            except socket.timeout:
                return b""
            terminator_run = len(peeked) - len(peeked.lstrip(b"\r\n"))
            if terminator_run < len(peeked):
                # Surplus beyond the terminator run belongs to nobody yet:
                # leave it and let the next write() drain it.
                self._desynced = True
            if terminator_run == 0:
                return b""
            return self._socket.recv(terminator_run)
        finally:
            self._socket.settimeout(previous if previous is not None else self.timeout)

    def __repr__(self) -> str:
        """String representation of connection."""
        status = "connected" if self._connected else "disconnected"
        return f"SocketConnection({self.host}:{self.port}, {status})"
