"""Screen capture functionality for Siglent oscilloscopes.

Captures the oscilloscope's display via the SCDP (screen dump) command. Modern
Siglent scopes (e.g. SDS800X HD) return a raw BMP whose length is carried in the
BMP header; older/other models may return an IEEE-488.2 definite-length block.
Both are handled by reading exactly the number of bytes the response declares,
rather than over-reading a fixed large size (which times out and drops the
connection on the modern models).
"""

import logging
import struct
import time
from io import BytesIO
from typing import Callable, Optional

from scpi_control.connection.framing import Framing

logger = logging.getLogger(__name__)


def _read_bmp_by_header(read_exact: Callable[[int], bytes]) -> bytes:
    """Read a raw BMP whose total size is declared in its own header.

    Modern Siglent scopes (SDS800X HD) answer ``SCDP`` with a raw BMP: magic
    ``BM`` then a little-endian uint32 total size at byte offset 2. Reading
    exactly that many bytes avoids over-reading past the image (which times out
    and drops the connection).

    Args:
        read_exact: Callable that returns exactly ``n`` bytes (a real socket read).

    Raises:
        RuntimeError: If the response does not start with a BMP header.
    """
    head = read_exact(2)
    if head[:2] != b"BM":
        raise RuntimeError(f"Expected a BMP screen dump, got header {head!r}")
    size_bytes = read_exact(4)
    total = struct.unpack("<I", size_bytes)[0]
    return head + size_bytes + read_exact(total - 6)


def _extract_ieee_block(raw: bytes) -> bytes:
    """Extract the payload from a whole SCDP? response.

    Legacy scopes (and the mock) answer ``SCDP?`` with an IEEE-488.2
    definite-length block (``#<ndigits><length><payload>``). If the connection
    already stripped the block header (a socket read returns the bare payload),
    ``raw`` is the image and is returned unchanged.

    Raises:
        RuntimeError: On an empty response.
    """
    if not raw:
        raise RuntimeError("SCDP? returned no data")
    if raw[:1] != b"#":
        return raw  # already the bare image payload
    ndigits = int(chr(raw[1]))
    length = int(raw[2 : 2 + ndigits].decode("ascii"))
    start = 2 + ndigits
    return raw[start : start + length]


class ScreenCapture:
    """Handles screenshot capture from an oscilloscope display.

    The scope returns its screen as a BMP; use get_screenshot_pil() (requires
    Pillow) to convert to PNG/JPEG.
    """

    SUPPORTED_FORMATS = ["PNG", "BMP", "JPEG", "JPG"]

    def __init__(self, oscilloscope):
        """Initialize screen capture.

        Args:
            oscilloscope: Parent Oscilloscope instance
        """
        self._scope = oscilloscope

    def capture_screenshot(self, image_format: str = "BMP") -> bytes:
        """Capture a screenshot from the oscilloscope display via SCDP.

        The SCDP command returns the screen image in the scope's native format
        (BMP on current Siglent models). ``image_format`` is accepted for
        backwards compatibility but ignored; use get_screenshot_pil() to convert.

        Args:
            image_format: Ignored (SCDP returns the scope's native format).

        Returns:
            Binary image data (BMP).

        Raises:
            RuntimeError: If capture fails.

        Example:
            >>> scope = Oscilloscope('192.168.1.100')
            >>> scope.connect()
            >>> data = scope.screen_capture.capture_screenshot()
            >>> open("screenshot.bmp", "wb").write(data)
        """
        logger.info("Capturing screenshot using SCDP command")
        try:
            image_data = self._capture_with_scdp()
            if not image_data:
                raise RuntimeError("SCDP returned empty data")
            logger.info(f"Screenshot captured successfully ({len(image_data)} bytes)")
            return image_data
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            raise RuntimeError(f"Failed to capture screenshot: {e}")

    def _capture_with_scdp(self) -> bytes:
        """Send the screen-dump command and read the image, dialect-aware.

        Modern SDS800X HD scopes answer ``SCDP`` (no ``?``) with a raw BMP whose
        size is in its header, read by exact byte count. Legacy scopes (and the
        mock) answer ``SCDP?`` with an IEEE-488.2 block. The two forms are not
        interchangeable: ``SCDP?`` times out on the modern scope, and ``SCDP``
        is unanswered by the legacy path.
        """
        connection = self._scope._connection
        if getattr(self._scope, "dialect", None) == "modern":
            self._scope.write("SCDP")
            time.sleep(0.2)  # let the scope prepare the screen dump
            image_data = _read_bmp_by_header(connection.read_raw)
            self._drain(connection)  # discard any trailing terminator byte
            return image_data
        self._scope.write("SCDP?")
        time.sleep(0.2)
        return _extract_ieee_block(connection.read_raw(framing=Framing.BLOCK))

    @staticmethod
    def _drain(connection) -> None:
        """Discard any bytes the scope left buffered after the image.

        The SCDP BMP is typically followed by a single terminator byte; left
        unread, it would be returned as the start of the next query's response.
        Best-effort and non-fatal: a scope without a raw socket (e.g. a mock) is
        simply skipped.
        """
        sock = getattr(connection, "_socket", None)
        if sock is None:
            return
        previous_timeout = sock.gettimeout()
        try:
            sock.settimeout(0.2)
            while sock.recv(4096):
                pass
        except Exception:
            pass
        finally:
            try:
                sock.settimeout(previous_timeout)
            except Exception:
                pass

    def save_screenshot(self, filename: str, image_format: Optional[str] = None) -> None:
        """Capture and save a screenshot to a file.

        The SCDP command returns BMP data. If you pass a different extension
        (e.g. .png), the file will still contain BMP bytes -- use
        get_screenshot_pil() and Pillow to convert formats.

        Args:
            filename: Output file path (recommend a .bmp extension).
            image_format: Ignored (SCDP always returns BMP).

        Example:
            >>> scope.screen_capture.save_screenshot("capture.bmp")

            To save as PNG (requires Pillow):
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.save("capture.png", "PNG")
        """
        image_data = self.capture_screenshot()
        with open(filename, "wb") as f:
            f.write(image_data)
        logger.info(f"Screenshot saved to {filename} (BMP format)")

    def get_screenshot_pil(self):
        """Capture a screenshot and return it as a PIL Image.

        Requires Pillow. Use this to convert the BMP screen dump to other formats.

        Returns:
            PIL.Image loaded from the captured BMP data.

        Raises:
            ImportError: If Pillow is not installed.

        Example:
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.save("screenshot.png", "PNG")
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("PIL/Pillow is required for this function. Install with: pip install Pillow")

        image_data = self.capture_screenshot()
        return Image.open(BytesIO(image_data))

    def __repr__(self) -> str:
        """String representation."""
        return f"ScreenCapture(formats={', '.join(self.SUPPORTED_FORMATS)})"
