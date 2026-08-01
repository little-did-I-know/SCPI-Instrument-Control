"""VISA-based connection for USB, GPIB, Serial, and TCP/IP instruments.

Supports multiple transport protocols using PyVISA:
- USB (USB-TMC)
- GPIB (IEEE-488)
- Serial (RS-232/RS-485)
- TCP/IP (VXI-11, raw socket)

Requires pyvisa package:
    pip install "SCPI-Instrument-Control[usb]"

For pure Python backend (no NI-VISA required):
    pip install pyvisa-py
"""

import logging
from typing import Optional

from scpi_control.connection.base import BaseConnection
from scpi_control.connection.framing import Framing, TransportClosed, TransportIdle, read_framed
from scpi_control.exceptions import CommandError, SiglentConnectionError, SiglentTimeoutError

logger = logging.getLogger(__name__)

# Milliseconds to wait for the tail of a headerless response: the bytes have
# stopped, but the framing reader only learns that from a read that comes back
# empty-handed. Mirrors SocketConnection's 0.5s on the same on_headerless hook.
_HEADERLESS_TAIL_TIMEOUT_MS = 500

# Milliseconds for a read that only asks "is anything queued?" -- the
# terminator behind a block, and the resync drain. Mirrors SocketConnection's
# 0.05s on both of its equivalents (_drain_terminator and resync).
_QUIET_PROBE_TIMEOUT_MS = 50

# A terminator run is "\n" or "\r\n"; nothing legitimate follows a block with
# more than that.
_MAX_TERMINATOR_BYTES = 2

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
        >>> from scpi_control import PowerSupply
        >>> from scpi_control.connection import VISAConnection
        >>> conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X123456::INSTR")
        >>> psu = PowerSupply(host="", connection=conn)
        >>> psu.connect()
        >>> print(psu.identify())

        >>> # GPIB connection
        >>> conn = VISAConnection("GPIB0::12::INSTR")
        >>> psu = PowerSupply(host="", connection=conn)
        >>> psu.connect()

    Note:
        Requires PyVISA: pip install "SCPI-Instrument-Control[usb]"
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
        super().__init__(host=resource_string, port=0, timeout=timeout)

        if not PYVISA_AVAILABLE:
            raise ImportError(
                "PyVISA is required for USB/VISA connections.\n" "Install with: pip install 'SCPI-Instrument-Control[usb]'\n" "For pure Python backend (no NI-VISA): pip install pyvisa-py"
            )

        self.resource_string = resource_string
        self.timeout = timeout
        self.backend = backend
        self.read_termination = read_termination
        self.write_termination = write_termination

        self._resource_manager: Optional[pyvisa.ResourceManager] = None
        self._resource: Optional[pyvisa.resources.MessageBasedResource] = None
        # Set when a read is abandoned part-way: whatever the instrument still
        # has queued would otherwise be handed to the NEXT caller as its answer.
        self._desynced = False
        # True only inside a read that has no length to read to; see _read_chunk.
        self._streaming = False

        logger.info(f"VISAConnection initialized: {resource_string}")
        logger.debug(f"Backend: {backend}, Timeout: {timeout}s")

    def _translate(self, exc: Exception, context: str) -> Exception:
        """Convert a VisaIOError into this library's exception vocabulary.

        Keyed on the status code, not on the message text: matching on an
        error string is not a contract. The string check stays as a fallback
        for backends that report a bare code.

        Which codes a given VISA backend actually reports is UNVERIFIED here --
        pyvisa is not installed in this environment, so the mapping is pinned
        against a stub, not against an instrument.
        """
        timed_out = getattr(exc, "error_code", None) == pyvisa.constants.StatusCode.error_timeout or "timeout" in str(exc).lower()
        if timed_out:
            self._desynced = True
            return SiglentTimeoutError(f"Timeout {context} on {self.resource_string}: {exc}")
        return SiglentConnectionError(f"VISA error {context} on {self.resource_string}: {exc}")

    def connect(self) -> None:
        """Establish VISA connection to the instrument.

        Raises:
            SiglentConnectionError: If connection fails
            SiglentTimeoutError: If connection times out
        """
        with self.lock:
            if self.is_connected:
                # Opening a second resource over the first leaks the first and
                # gives two half-owned sessions to the same instrument.
                logger.debug("Already connected to %s", self.resource_string)
                return

            try:
                logger.info(f"Opening VISA resource manager (backend: {self.backend})")
                self._resource_manager = pyvisa.ResourceManager(self.backend)

                logger.info(f"Connecting to VISA resource: {self.resource_string}")
                self._resource = self._resource_manager.open_resource(self.resource_string)

                self._resource.timeout = int(self.timeout * 1000)  # VISA uses milliseconds
                self._resource.read_termination = self.read_termination
                self._resource.write_termination = self.write_termination

                # For serial connections, configure additional parameters
                if "ASRL" in self.resource_string or "COM" in self.resource_string:
                    self._configure_serial()
            except Exception as e:
                # Anything after open_resource() succeeded used to leave
                # _resource set -- and is_connected was defined as "_resource
                # is not None", so a FAILED connect reported itself connected,
                # with the ResourceManager leaked on top.
                self._close_quietly()
                error_msg = f"Failed to connect to VISA resource {self.resource_string}: {e}"
                logger.error(error_msg)
                raise SiglentConnectionError(error_msg) from e

            self._connected = True
            # A freshly opened session has nothing stranded on it from before.
            self._desynced = False
            logger.info(f"VISA connection established: {self.resource_string}")

    def _close_quietly(self) -> None:
        """Release the resource and the manager, ignoring secondary failures."""
        for attribute in ("_resource", "_resource_manager"):
            handle = getattr(self, attribute)
            if handle is not None:
                try:
                    handle.close()
                except Exception as e:  # pragma: no cover - secondary failure
                    logger.warning("Error closing %s for %s: %s", attribute, self.resource_string, e)
                finally:
                    setattr(self, attribute, None)
        self._connected = False

    def disconnect(self) -> None:
        """Close VISA connection to the instrument."""
        with self.lock:
            logger.info("Disconnecting from VISA resource")
            self._close_quietly()

    @property
    def is_connected(self) -> bool:
        """Check if connected to the instrument.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._resource is not None

    def _resync_if_desynced(self) -> None:
        """Clear anything stranded by an earlier timeout before sending again.

        Mirrors SocketConnection.write(): a reply that arrives after its reader
        gave up becomes the answer to the NEXT command unless it is discarded
        first (backend review 2026-07-31, High-7).
        """
        if not self._desynced:
            return
        discarded = self.resync()
        if discarded:
            logger.warning("Discarded %d stale byte(s) before sending on %s", discarded, self.resource_string)

    @staticmethod
    def _require_ascii(command: str) -> None:
        """Reject a command VISA cannot put on the wire as SCPI."""
        try:
            command.encode("ascii")
        except UnicodeEncodeError as e:
            raise CommandError(f"SCPI command contains non-ASCII characters: {command!r}") from e

    def write(self, command: str) -> None:
        """Send a SCPI command to the instrument.

        Args:
            command: SCPI command string

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If write times out
            CommandError: If command contains invalid characters
        """
        with self.lock:
            if not self.is_connected:
                raise SiglentConnectionError("Not connected to VISA resource")

            # Validate before resyncing: a command that is about to be rejected
            # is not a reason to issue a device clear.
            self._require_ascii(command)
            self._resync_if_desynced()

            try:
                logger.debug(f"VISA Write: {command}")
                self._resource.write(command)
            except pyvisa.errors.VisaIOError as e:
                # _translate marks the session out of step on a timeout, which
                # SocketConnection.write does not do. Deliberate: a write that
                # timed out part-way leaves the instrument's parser mid-command,
                # and the next send has to clear that before it means anything.
                raise self._translate(e, f"writing '{command}'") from e

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
        with self.lock:
            if not self.is_connected:
                raise SiglentConnectionError("Not connected to VISA resource")

            self._require_ascii(command)
            self._resync_if_desynced()

            try:
                logger.debug(f"VISA Query: {command}")
                response = self._resource.query(command)
            except pyvisa.errors.VisaIOError as e:
                raise self._translate(e, f"querying '{command}'") from e

            logger.debug(f"VISA Response: {response!r}")
            return response.strip()

    def read(self) -> str:
        """Read a response string from the instrument.

        Returns:
            The response with trailing whitespace/terminators stripped.

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If the read times out
        """
        with self.lock:
            if not self.is_connected:
                raise SiglentConnectionError("Not connected to VISA resource")

            logger.debug("VISA Read")
            try:
                response = self._resource.read()
            except pyvisa.errors.VisaIOError as e:
                raise self._translate(e, "reading") from e

            logger.debug(f"VISA Response: {response!r}")
            return response.strip()

    def _begin_streaming(self) -> None:
        """Give up on reading to a length: read whole messages from here on."""
        self._streaming = True

    def _on_headerless(self) -> None:
        """read_framed's hook: AUTO looked, and this response has no header.

        The same switch as _begin_streaming, plus a shorter timeout, mirroring
        SocketConnection. Shortening is safe HERE and not for a declared
        STREAM, because read_framed only reaches this verdict after bytes have
        arrived: what remains is the idle read that proves the response ended,
        not the wait for it to begin. A declared STREAM keeps the full timeout
        precisely because its first read may still be waiting on a slow
        instrument.
        """
        self._begin_streaming()
        self._resource.timeout = _HEADERLESS_TAIL_TIMEOUT_MS

    def _read_chunk(self, hint: int) -> bytes:
        """Read for read_framed (see connection.framing).

        Two different VISA reads sit behind this, and the difference is the
        whole point. While a length is known -- one byte at a time until the
        header resolves, then exactly the remainder -- read_bytes(count) is
        the right call: pyvisa documents it as looping low-level reads until
        it holds `count` bytes ("if count > chunk_size multiple low level
        operations will be performed"), and those bytes are genuinely on their
        way. Once the response turns out to carry no header there is no such
        count, and asking read_bytes for a chunk bigger than the response is
        the same over-demand this task took out of query_binary -- per the
        same docs it waits out the entire timeout and then raises, dropping
        what it did read. So the headerless case uses read_raw() instead.

        LIMIT, since the whole of this module is stub-tested and none of it is
        hardware-verified: read_raw() ends a read on END/EOI, which USB-TMC,
        GPIB and VXI-11 sessions carry. A "TCPIP::...::SOCKET" resource does
        NOT, and read_termination is deliberately off for the duration of a
        binary read, so on that resource class a headerless read has nothing
        to end on but the timeout -- and pyvisa raises rather than returning
        the partial buffer, so the bytes are lost and the caller sees
        SiglentTimeoutError for a response that did arrive. Every call site in
        this library declares Framing.BLOCK, which does not take this branch;
        a caller that declares STREAM over a raw-socket VISA resource is the
        untested case.
        """
        try:
            chunk = self._resource.read_raw() if self._streaming else self._resource.read_bytes(max(1, hint))
        except pyvisa.errors.VisaIOError as e:
            if getattr(e, "error_code", None) == pyvisa.constants.StatusCode.error_timeout:
                raise TransportIdle() from e
            raise
        if not chunk:
            raise TransportClosed()
        return chunk

    def read_raw(self, size: Optional[int] = None, framing: Framing = Framing.AUTO) -> bytes:
        """Read raw bytes from the instrument (e.g. a waveform or screenshot block).

        Args:
            size: Exact number of bytes to read. None frames the response as
                `framing` declares.
            framing: What the CALLER knows the response to be (see
                connection.framing.Framing). Ignored when `size` is given.

        Returns:
            The raw bytes read from the instrument.

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If the read times out or stalls mid-block
            CommandError: If BLOCK was declared and no block arrived
        """
        with self.lock:
            if not self.is_connected:
                raise SiglentConnectionError("Not connected to VISA resource")

            logger.debug(f"VISA Read Raw: size={size}, framing={framing.value}")
            previous_termination = self._resource.read_termination
            previous_timeout = self._resource.timeout
            # A 0x0A inside a waveform is data, not a terminator. pyvisa
            # enforces read_termination for SOCKET/ASRL sessions, so it has to
            # come off for the duration of a binary read.
            self._resource.read_termination = None
            self._streaming = False
            try:
                if size is not None:
                    return self._resource.read_bytes(size)
                if framing is Framing.STREAM:
                    self._begin_streaming()
                result = read_framed(self._read_chunk, framing, context=self.resource_string, on_headerless=self._on_headerless)
                if result.block_total is not None:
                    # read_framed stops on the last payload byte, so the
                    # terminator behind the block is still queued.
                    return result.data + self._drain_terminator()
                return result.data
            except pyvisa.errors.VisaIOError as e:
                raise self._translate(e, "reading raw") from e
            except SiglentTimeoutError:
                # A stalled or empty binary read leaves the session position
                # unknown, exactly like a line read that timed out.
                self._desynced = True
                raise
            finally:
                self._resource.read_termination = previous_termination
                self._resource.timeout = previous_timeout
                self._streaming = False

    def _drain_terminator(self) -> bytes:
        """Consume the terminator that follows a completed block -- only that.

        read_framed returns the moment it holds the declared length, which
        counts the header and the payload and nothing else. The terminator the
        instrument sends after the block is still queued, and leaving it there
        is not harmless: it becomes the whole of the NEXT response. Nothing
        times out when that happens, so _desynced is never set and the
        resync-before-send cannot catch it either. SocketConnection records
        the same failure at its own _drain_terminator, which is why it has one.

        Deliberately NOT a copy of the socket's. VISA offers no MSG_PEEK
        equivalent, so this cannot look without consuming. When the read comes
        back as something other than terminator bytes, that byte is already
        eaten, and the only honest response left is to say so: the session is
        marked out of step and the byte is logged at WARNING, rather than
        quietly dropped. The trade is deliberate -- leaving the terminator
        corrupts the very next read EVERY time, while consuming a surplus byte
        can only happen on a session that is already out of step.

        One byte at a time on purpose: read_bytes(2) is a fixed-length read
        and would wait out the timeout, then raise, for a terminator run of
        one -- losing it, which is the exact bug this method exists to avoid.
        """
        drained = b""
        previous_timeout = self._resource.timeout
        self._resource.timeout = _QUIET_PROBE_TIMEOUT_MS
        try:
            for _ in range(_MAX_TERMINATOR_BYTES):
                try:
                    byte = self._resource.read_bytes(1)
                except pyvisa.errors.VisaIOError as e:
                    # Nothing queued. Normal for a resource whose own read
                    # already consumed the terminator, and the reason this is
                    # not an error.
                    logger.debug("No terminator queued after the block on %s: %s", self.resource_string, e)
                    break
                if not byte:
                    break
                if byte not in (b"\r", b"\n"):
                    self._desynced = True
                    logger.warning(
                        "Discarded %r found behind the block on %s: it is not a terminator, and VISA cannot look without consuming. Marking the session out of step.",
                        byte,
                        self.resource_string,
                    )
                    break
                drained += byte
        finally:
            self._resource.timeout = previous_timeout
        return drained

    def query_binary(self, command: str, max_bytes: int = 1000000) -> bytes:
        """Send a SCPI query and read a binary response.

        Args:
            command: SCPI query command
            max_bytes: Ceiling on the response this will RETURN. It is checked
                after the response has been read, not before: the framed reader
                cannot abandon a block part-way, so an oversized block is still
                transferred AND held in memory before it is rejected. That is a
                real loss against the old code, which passed max_bytes straight
                to read_bytes() and so bounded the allocation. It bounded
                nothing else: it demanded exactly that many bytes, so a 70 kB
                waveform blocked for the whole timeout and then raised with the
                data already in hand. A ceiling that cannot stop the transfer
                is worth less than one that can; a read that never returns the
                data is worth nothing at all.

        Returns:
            Binary response data

        Raises:
            SiglentConnectionError: If not connected
            SiglentTimeoutError: If the query times out
            CommandError: If the response is larger than max_bytes
        """
        with self.lock:
            if not self.is_connected:
                raise SiglentConnectionError("Not connected to VISA resource")

            logger.debug(f"VISA Binary Query: {command}")
            self.write(command)
            response = self.read_raw()
            if len(response) > max_bytes:
                raise CommandError(f"Binary response to '{command}' from {self.resource_string} is {len(response)} bytes, over the {max_bytes}-byte ceiling")

            logger.debug(f"VISA Binary Response: {len(response)} bytes")
            return response

    def resync(self) -> int:
        """Discard anything the instrument left unread; return the byte count.

        Called before the next send when a read has been abandoned. The bytes
        are gone either way -- the alternative is handing them to a caller who
        asked a different question (backend review 2026-07-31, High-7).

        Prefers a VISA device clear, the protocol-level way to say "abandon the
        current transfer". Two limits, stated plainly:

        - `clear()`'s effect is UNVERIFIED against hardware here. pyvisa is not
          installed in this environment, so it is known to be CALLED, not known
          to work.
        - a device clear reports no byte count, so a successful clear returns 0
          even when it discarded a full waveform. The return value is a floor,
          not a measurement, and is only used for a log line.
        """
        with self.lock:
            if not self.is_connected:
                self._desynced = False
                return 0

            clear = getattr(self._resource, "clear", None)
            if callable(clear):
                try:
                    clear()
                except Exception as e:
                    logger.warning("Device clear failed on %s, draining instead: %s", self.resource_string, e)
                else:
                    self._desynced = False
                    return 0
            return self._drain()

    def _drain(self) -> int:
        """Read whole messages until the session goes quiet; count what went.

        The fallback for a resource exposing no clear(). pyvisa documents
        clear() on MessageBasedResource, so this is expected to be the path for
        resources and test doubles that do not expose it rather than the normal
        route -- expected, not confirmed: nothing in this module is checked
        against a real backend.

        read_raw(), not read_bytes(): there is no length to ask for here, and a
        fixed-length read would wait out the timeout for bytes that are not
        coming (see _read_chunk). The count is still a FLOOR -- a message the
        instrument never terminates times out with what was read so far
        discarded uncounted -- but the bytes are gone either way, which is the
        point of a drain. The number only feeds a log line.
        """
        discarded = 0
        previous_timeout = self._resource.timeout
        previous_termination = self._resource.read_termination
        self._resource.timeout = _QUIET_PROBE_TIMEOUT_MS
        self._resource.read_termination = None
        try:
            while True:
                try:
                    chunk = self._resource.read_raw()
                except pyvisa.errors.VisaIOError:
                    break
                if not chunk:
                    break
                discarded += len(chunk)
        finally:
            self._resource.timeout = previous_timeout
            self._resource.read_termination = previous_termination
            self._desynced = False
        return discarded

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
        >>> from scpi_control.connection.visa_connection import list_visa_resources
        >>> resources = list_visa_resources()
        >>> for res in resources:
        ...     print(res)
        USB0::0xF4EC::0xEE38::SPD3X123456::INSTR
        GPIB0::12::INSTR
    """
    if not PYVISA_AVAILABLE:
        raise ImportError("PyVISA is required for VISA resource discovery.\n" "Install with: pip install 'SCPI-Instrument-Control[usb]'")

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
        >>> from scpi_control.connection.visa_connection import find_siglent_devices
        >>> devices = find_siglent_devices()
        >>> for resource, info in devices:
        ...     print(f"{resource}: {info}")
        USB0::0xF4EC::...: Siglent Technologies,SPD3303X-E,...
    """
    if not PYVISA_AVAILABLE:
        raise ImportError("PyVISA is required.\n" "Install with: pip install 'SCPI-Instrument-Control[usb]'")

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
