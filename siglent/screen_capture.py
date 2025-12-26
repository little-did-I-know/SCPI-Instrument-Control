"""Screen capture functionality for Siglent oscilloscopes.

This module provides functionality to capture screenshots from the oscilloscope's
display in various image formats.
"""

import logging
from typing import Optional
from io import BytesIO

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Handles screenshot capture from oscilloscope display.

    Supports capturing the oscilloscope screen in PNG, BMP, and JPEG formats.
    """

    SUPPORTED_FORMATS = ["PNG", "BMP", "JPEG", "JPG"]

    def __init__(self, oscilloscope):
        """Initialize screen capture.

        Args:
            oscilloscope: Parent Oscilloscope instance
        """
        self._scope = oscilloscope

    def capture_screenshot(self, image_format: str = "PNG") -> bytes:
        """Capture screenshot from oscilloscope display.

        Args:
            image_format: Image format ("PNG", "BMP", "JPEG")

        Returns:
            Binary image data

        Raises:
            ValueError: If format is not supported
            RuntimeError: If capture fails

        Example:
            >>> scope = Oscilloscope('192.168.1.100')
            >>> scope.connect()
            >>> image_data = scope.screen_capture.capture_screenshot("PNG")
            >>> with open("screenshot.png", "wb") as f:
            ...     f.write(image_data)
        """
        # Validate format
        image_format = image_format.upper()
        if image_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {image_format}. Supported: {', '.join(self.SUPPORTED_FORMATS)}")

        # Normalize JPEG format
        if image_format == "JPG":
            image_format = "JPEG"

        logger.info(f"Capturing screenshot in {image_format} format")

        try:
            # Set the hardcopy format
            # Note: Different models may use different commands
            # HCSU DEV,FORMAT,<format> - Set format
            self._scope.write(f"HCSU DEV,FORMAT,{image_format}")

            # Some models may need a small delay
            import time
            time.sleep(0.1)

            # Trigger screen capture and get data
            # Method 1: Try SCDP command (used by HD series and some others)
            try:
                logger.debug("Attempting SCDP command")
                image_data = self._capture_with_scdp()
                if image_data:
                    logger.info(f"Screenshot captured successfully ({len(image_data)} bytes)")
                    return image_data
            except Exception as e:
                logger.debug(f"SCDP method failed: {e}")

            # Method 2: Try HCSU? command (used by some X series)
            try:
                logger.debug("Attempting HCSU? command")
                image_data = self._capture_with_hcsu()
                if image_data:
                    logger.info(f"Screenshot captured successfully ({len(image_data)} bytes)")
                    return image_data
            except Exception as e:
                logger.debug(f"HCSU? method failed: {e}")

            # If both methods fail
            raise RuntimeError("Failed to capture screenshot with available methods")

        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            raise RuntimeError(f"Failed to capture screenshot: {e}")

    def _capture_with_scdp(self) -> bytes:
        """Capture screenshot using SCDP command.

        Returns:
            Binary image data

        Raises:
            Exception: If capture fails
        """
        # Send SCDP command to get screen dump
        self._scope.write("SCDP")

        # Read the response - should be binary image data
        # The response format is typically IEEE 488.2 definite-length block
        # Format: #<N><length><data>
        # where N is the number of digits in <length>

        # Read the header
        header = self._scope._connection.read_raw(2)  # Read '#N'
        if not header or header[0:1] != b'#':
            raise Exception("Invalid response header")

        # Get number of length digits
        num_digits = int(chr(header[1]))
        if num_digits == 0:
            raise Exception("Invalid length format")

        # Read the length
        length_bytes = self._scope._connection.read_raw(num_digits)
        data_length = int(length_bytes.decode('ascii'))

        # Read the actual image data
        image_data = self._scope._connection.read_raw(data_length)

        if len(image_data) != data_length:
            raise Exception(f"Data length mismatch: expected {data_length}, got {len(image_data)}")

        return image_data

    def _capture_with_hcsu(self) -> bytes:
        """Capture screenshot using HCSU? command.

        Returns:
            Binary image data

        Raises:
            Exception: If capture fails
        """
        # Send HCSU PRINT to trigger capture
        self._scope.write("HCSU PRINT")

        # Small delay for capture to complete
        import time
        time.sleep(0.2)

        # Query for the image data
        response = self._scope.query("HCSU?")

        # Response should contain binary image data
        # May need to parse based on model-specific format
        if isinstance(response, str):
            # If response is string, it might be an error
            raise Exception(f"Unexpected string response: {response}")

        return response.encode() if isinstance(response, str) else response

    def save_screenshot(self, filename: str, image_format: Optional[str] = None) -> None:
        """Capture and save screenshot to file.

        Args:
            filename: Output file path
            image_format: Image format (default: auto-detect from filename extension)

        Example:
            >>> scope.screen_capture.save_screenshot("capture.png")
            >>> scope.screen_capture.save_screenshot("capture.bmp", "BMP")
        """
        # Auto-detect format from filename if not specified
        if image_format is None:
            import os
            ext = os.path.splitext(filename)[1].upper()
            format_map = {
                '.PNG': 'PNG',
                '.BMP': 'BMP',
                '.JPG': 'JPEG',
                '.JPEG': 'JPEG',
            }
            image_format = format_map.get(ext, 'PNG')
            logger.debug(f"Auto-detected format: {image_format} from extension {ext}")

        # Capture screenshot
        image_data = self.capture_screenshot(image_format)

        # Save to file
        with open(filename, 'wb') as f:
            f.write(image_data)

        logger.info(f"Screenshot saved to {filename}")

    def get_screenshot_pil(self, image_format: str = "PNG"):
        """Capture screenshot and return as PIL Image object.

        Requires PIL/Pillow to be installed.

        Args:
            image_format: Image format ("PNG", "BMP", "JPEG")

        Returns:
            PIL.Image object

        Raises:
            ImportError: If PIL is not installed

        Example:
            >>> from PIL import Image
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.show()
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("PIL/Pillow is required for this function. Install with: pip install Pillow")

        image_data = self.capture_screenshot(image_format)
        return Image.open(BytesIO(image_data))

    def __repr__(self) -> str:
        """String representation."""
        return f"ScreenCapture(formats={', '.join(self.SUPPORTED_FORMATS)})"
