"""Screen capture functionality for Siglent oscilloscopes.

This module provides functionality to capture screenshots from the oscilloscope's
display in various image formats.
"""

import logging
from io import BytesIO
from typing import Optional

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

    def capture_screenshot(self, image_format: str = "BMP") -> bytes:
        """Capture screenshot from oscilloscope display using SCDP command.

        Note: The SCDP command returns the screen image in the oscilloscope's
        native format (typically BMP). The image_format parameter is ignored
        for Siglent scopes using SCDP. To convert to other formats, use PIL/Pillow
        after capture.

        Args:
            image_format: Desired format (currently ignored, SCDP returns BMP)

        Returns:
            Binary image data (typically BMP format)

        Raises:
            RuntimeError: If capture fails

        Example:
            >>> scope = Oscilloscope('192.168.1.100')
            >>> scope.connect()
            >>> image_data = scope.screen_capture.capture_screenshot()
            >>> with open("screenshot.bmp", "wb") as f:
            ...     f.write(image_data)
        """
        logger.info(f"Capturing screenshot using SCDP command")

        try:
            # For Siglent oscilloscopes, use SCDP command (Screen Dump)
            # This is the standard command per Siglent programming manual
            logger.debug("Using SCDP command for screenshot capture")
            image_data = self._capture_with_scdp()
            if image_data:
                logger.info(f"Screenshot captured successfully ({len(image_data)} bytes)")
                return image_data
            else:
                raise RuntimeError("SCDP returned empty data")

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
        import time

        # Try method 1: SCDP as a query command
        try:
            logger.debug("Attempting SCDP? query")

            # Query using SCDP?
            self._scope.write("SCDP?")
            time.sleep(0.2)  # Wait for scope to prepare data

            # Read response as raw bytes (up to 10MB)
            response = self._scope._connection.read_raw(10000000)

            if response and len(response) > 0:
                logger.debug(f"SCDP? returned {len(response)} bytes, first bytes: {response[:20]}")
                # Check if it starts with IEEE 488.2 format
                if response[0:1] == b"#":
                    logger.debug("Response is in IEEE 488.2 format")
                    return self._parse_ieee488_response(response)
                else:
                    # Might be raw BMP data
                    logger.debug("Response appears to be raw image data")
                    return response
        except Exception as e:
            logger.debug(f"SCDP? query failed: {e}")

        # Try method 2: SCDP as write then read
        try:
            logger.debug("Attempting SCDP write then read")
            self._scope.write("SCDP")
            time.sleep(0.2)  # Wait for scope to prepare data

            # Try to read response
            response = self._scope._connection.read_raw(2)  # Read first 2 bytes

            if not response:
                raise Exception("No response from SCDP command")

            logger.debug(f"Read header: {response}")

            # Check if it's IEEE 488.2 format
            if response[0:1] == b"#":
                # Put the header back and read the full response
                logger.debug("Detected IEEE 488.2 format, reading full response")
                num_digits = int(chr(response[1]))
                length_bytes = self._scope._connection.read_raw(num_digits)
                data_length = int(length_bytes.decode("ascii"))
                image_data = self._scope._connection.read_raw(data_length)

                if len(image_data) != data_length:
                    raise Exception(f"Data length mismatch: expected {data_length}, got {len(image_data)}")

                return image_data
            else:
                # Not IEEE format, might be raw data - read everything available
                logger.debug("Not IEEE 488.2 format, reading raw data")
                remaining = self._scope._connection.read_raw(10000000)  # Read up to 10MB
                return response + remaining

        except Exception as e:
            logger.error(f"SCDP command failed: {e}")
            raise Exception(f"SCDP screenshot capture failed: {e}")

    def _parse_ieee488_response(self, response: bytes) -> bytes:
        """Parse IEEE 488.2 definite-length block format.

        Args:
            response: Full response including header

        Returns:
            Extracted data
        """
        if response[0:1] != b"#":
            raise Exception("Not IEEE 488.2 format")

        num_digits = int(chr(response[1]))
        if num_digits == 0:
            raise Exception("Invalid length format")

        length_bytes = response[2 : 2 + num_digits]
        data_length = int(length_bytes.decode("ascii"))

        data_start = 2 + num_digits
        image_data = response[data_start : data_start + data_length]

        if len(image_data) != data_length:
            logger.warning(f"Data length mismatch: expected {data_length}, got {len(image_data)}")

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

        Note: The SCDP command returns images in BMP format. If you specify
        a different extension (e.g., .png), the file will still contain BMP
        data. Use get_screenshot_pil() and PIL to convert formats if needed.

        Args:
            filename: Output file path (recommend using .bmp extension)
            image_format: Ignored (SCDP always returns BMP)

        Example:
            >>> scope.screen_capture.save_screenshot("capture.bmp")

            To save as PNG (requires PIL/Pillow):
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.save("capture.png", "PNG")
        """
        # Capture screenshot using SCDP (returns BMP format)
        image_data = self.capture_screenshot()

        # Save to file (data will be in BMP format regardless of filename)
        with open(filename, "wb") as f:
            f.write(image_data)

        logger.info(f"Screenshot saved to {filename} (BMP format)")

    def get_screenshot_pil(self):
        """Capture screenshot and return as PIL Image object.

        Requires PIL/Pillow to be installed.
        Use this method to convert the BMP screenshot to other formats.

        Returns:
            PIL.Image object (loaded from BMP data)

        Raises:
            ImportError: If PIL is not installed

        Example:
            >>> # Capture and display
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.show()

            >>> # Capture and save as PNG
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.save("screenshot.png", "PNG")

            >>> # Capture and save as JPEG with quality
            >>> img = scope.screen_capture.get_screenshot_pil()
            >>> img.save("screenshot.jpg", "JPEG", quality=95)
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("PIL/Pillow is required for this function. Install with: pip install Pillow")

        # Capture screenshot (returns BMP format from SCDP)
        image_data = self.capture_screenshot()
        return Image.open(BytesIO(image_data))

    def __repr__(self) -> str:
        """String representation."""
        return f"ScreenCapture(formats={', '.join(self.SUPPORTED_FORMATS)})"
