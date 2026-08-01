"""Transport-neutral IEEE 488.2 framing.

Both SocketConnection and VISAConnection have to answer the same question --
"is this response a definite-length block, and where does it end?" -- and both
got it wrong, differently (backend review 2026-07-31, High-4 and High-6). This
module answers it once, with no I/O of its own: the caller injects a
`read_chunk(hint)` callable, which makes every case testable against a list of
byte strings instead of a socket.

The rule that fixes High-6: a `#` only starts a header when every byte before
it is printable ASCII. A command echo (`C1:WF DAT2,#9000000070`) satisfies
that; binary content does not, because a payload reaches a non-printable byte
almost immediately.
"""

from enum import Enum
from typing import Callable, NamedTuple, Optional

from scpi_control import exceptions

# Inherited from the pre-existing scan (socket.py:276): with no '#' this deep
# into a printable response there is no block, but below it we keep waiting
# rather than risk truncating a header that arrived split across two reads.
_MAX_HEADER_PREFIX = 128
# Enough to cover the longest legal header (`#9` + 9 digits) plus a short echo
# prefix in one or two reads, while the length is still unknown.
_HEADER_PROBE = 16


class Framing(Enum):
    """What the caller knows about the response it is about to read."""

    AUTO = "auto"  # infer (tightened); the default, for callers we do not control
    BLOCK = "block"  # a definite-length block is REQUIRED; anything else is an error
    STREAM = "stream"  # no inference at all; drain until the line goes idle


class BlockScan(NamedTuple):
    """Outcome of looking for a definite-length block header.

    total: full response size (prefix + header + payload) once known.
    verdict: "block" | "absent" | "incomplete"
    """

    total: Optional[int]
    verdict: str


class FramedRead(NamedTuple):
    """A completed read. block_total is None when nothing was framed."""

    data: bytes
    block_total: Optional[int]


class TransportIdle(Exception):
    """read_chunk: nothing arrived within the transport's idle window."""


class TransportClosed(Exception):
    """read_chunk: the peer closed the connection.

    Raised rather than returning b"" so the reader can tell "the response
    ended" from "the response was cut off", which are different faults with
    different recovery. The transport sets its own connection state before
    raising -- it knows, this module does not.
    """


def _is_printable(byte_value: int) -> bool:
    return 0x20 <= byte_value <= 0x7E


def parse_block_header(data: bytes) -> BlockScan:
    """Locate a definite-length block header and compute the total response size."""
    limit = min(len(data), _MAX_HEADER_PREFIX)
    index = -1
    for position in range(limit):
        if data[position : position + 1] == b"#":
            index = position
            break
        if not _is_printable(data[position]):
            # Binary before any '#': this response is not a block, and a '#'
            # further in is payload content, not a header (High-6).
            return BlockScan(None, "absent")
    if index == -1:
        return BlockScan(None, "absent" if len(data) >= _MAX_HEADER_PREFIX else "incomplete")

    if len(data) < index + 2:
        return BlockScan(None, "incomplete")
    digit_char = data[index + 1 : index + 2]
    if not digit_char.isdigit() or digit_char == b"0":
        # '#0' is indefinite-length, and a stray '#' is not a header at all.
        return BlockScan(None, "absent")
    num_digits = int(digit_char)
    if len(data) < index + 2 + num_digits:
        return BlockScan(None, "incomplete")
    length_field = data[index + 2 : index + 2 + num_digits]
    if not length_field.isdigit():
        return BlockScan(None, "absent")
    return BlockScan(index + 2 + num_digits + int(length_field), "block")


def read_framed(
    read_chunk: Callable[[int], bytes],
    framing: Framing = Framing.AUTO,
    *,
    max_chunk: int = 4096,
    on_headerless: Optional[Callable[[], None]] = None,
    context: str = "",
) -> FramedRead:
    """Read one response, framed as the caller declared.

    Args:
        read_chunk: returns up to `hint` bytes; raises TransportIdle when
            nothing arrives in time and TransportClosed when the peer hangs up.
        framing: see Framing.
        max_chunk: largest read to request once the length is known or while
            draining.
        on_headerless: called once when AUTO gives up on finding a header, so
            the transport can loosen its timeout for the drain that follows.
        context: host/command detail folded into error messages.
    """
    where = f" ({context})" if context else ""
    data = b""
    total: Optional[int] = None
    streaming = framing is Framing.STREAM

    while True:
        if total is not None:
            hint = min(total - len(data), max_chunk)
        elif streaming:
            hint = max_chunk
        else:
            hint = _HEADER_PROBE

        try:
            chunk = read_chunk(hint)
        except TransportClosed:
            if total is not None:
                raise exceptions.SiglentConnectionError(f"Response truncated by peer close: received {len(data)} of {total} declared bytes{where}")
            if framing is Framing.BLOCK:
                raise exceptions.CommandError(f"Expected a definite-length block; peer closed after {len(data)} bytes{where}")
            return FramedRead(data, None)
        except TransportIdle:
            if total is not None:
                raise exceptions.SiglentTimeoutError(f"Binary read stalled: received {len(data)} of {total} declared bytes{where}")
            if framing is Framing.BLOCK:
                raise exceptions.CommandError(f"Expected a definite-length block, got {len(data)} bytes with no usable header{where}")
            if data:
                return FramedRead(data, None)
            raise exceptions.SiglentTimeoutError(f"Read timeout - no data received{where}")

        if chunk:
            data += chunk

        if total is None and not streaming:
            scan = parse_block_header(data)
            if scan.verdict == "block":
                total = scan.total
            elif scan.verdict == "absent":
                if framing is Framing.BLOCK:
                    raise exceptions.CommandError(f"Expected a definite-length block, got {data[:16]!r}...{where}")
                streaming = True
                if on_headerless is not None:
                    on_headerless()

        if total is not None and len(data) >= total:
            return FramedRead(data, total)
