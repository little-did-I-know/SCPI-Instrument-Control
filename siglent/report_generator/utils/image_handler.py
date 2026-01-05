"""
Image handling utilities for report generation.

Handles importing, resizing, and managing images (screenshots, setup photos, etc.)
for inclusion in reports.
"""

import io
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


class ImageHandler:
    """Handler for image operations in reports."""

    SUPPORTED_FORMATS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"]

    @staticmethod
    def is_supported(filepath: Path) -> bool:
        """
        Check if an image format is supported.

        Args:
            filepath: Path to the image file

        Returns:
            True if supported, False otherwise
        """
        return filepath.suffix.lower() in ImageHandler.SUPPORTED_FORMATS

    @staticmethod
    def load_image(filepath: Path) -> Image.Image:
        """
        Load an image from a file.

        Args:
            filepath: Path to the image file

        Returns:
            PIL Image object

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If image format is not supported
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Image file not found: {filepath}")

        if not ImageHandler.is_supported(filepath):
            raise ValueError(f"Unsupported image format: {filepath.suffix}. " f"Supported formats: {', '.join(ImageHandler.SUPPORTED_FORMATS)}")

        return Image.open(filepath)

    @staticmethod
    def resize_image(
        image: Image.Image,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        maintain_aspect: bool = True,
    ) -> Image.Image:
        """
        Resize an image to fit within specified dimensions.

        Args:
            image: PIL Image object
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            maintain_aspect: Whether to maintain aspect ratio

        Returns:
            Resized PIL Image object
        """
        if max_width is None and max_height is None:
            return image

        current_width, current_height = image.size

        if not maintain_aspect:
            new_width = max_width if max_width else current_width
            new_height = max_height if max_height else current_height
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Calculate new dimensions maintaining aspect ratio
        if max_width and max_height:
            # Fit within both dimensions
            width_ratio = max_width / current_width
            height_ratio = max_height / current_height
            ratio = min(width_ratio, height_ratio)
        elif max_width:
            ratio = max_width / current_width
        else:  # max_height
            ratio = max_height / current_height

        new_width = int(current_width * ratio)
        new_height = int(current_height * ratio)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    @staticmethod
    def convert_to_format(image: Image.Image, format: str = "PNG") -> bytes:
        """
        Convert image to specified format and return as bytes.

        Args:
            image: PIL Image object
            format: Target format (PNG, JPEG, etc.)

        Returns:
            Image data as bytes
        """
        buffer = io.BytesIO()

        # Convert RGBA to RGB for JPEG
        if format.upper() == "JPEG" and image.mode == "RGBA":
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])
            rgb_image.save(buffer, format=format)
        else:
            image.save(buffer, format=format)

        return buffer.getvalue()

    @staticmethod
    def get_image_info(filepath: Path) -> dict:
        """
        Get information about an image file.

        Args:
            filepath: Path to the image file

        Returns:
            Dictionary with image information
        """
        image = ImageHandler.load_image(filepath)

        return {
            "filepath": str(filepath),
            "format": image.format,
            "mode": image.mode,
            "width": image.size[0],
            "height": image.size[1],
            "size_bytes": filepath.stat().st_size,
        }

    @staticmethod
    def create_thumbnail(
        filepath: Path,
        output_path: Path,
        size: Tuple[int, int] = (200, 200),
    ) -> None:
        """
        Create a thumbnail of an image.

        Args:
            filepath: Path to the source image
            output_path: Path to save the thumbnail
            size: Maximum dimensions for the thumbnail (width, height)
        """
        image = ImageHandler.load_image(filepath)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        image.save(output_path)

    @staticmethod
    def optimize_for_report(
        filepath: Path,
        max_width: int = 800,
        max_height: int = 600,
        quality: int = 85,
    ) -> Image.Image:
        """
        Optimize an image for inclusion in a report.

        Resizes large images and optimizes file size while maintaining quality.

        Args:
            filepath: Path to the image file
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            quality: JPEG quality (1-100)

        Returns:
            Optimized PIL Image object
        """
        image = ImageHandler.load_image(filepath)

        # Resize if too large
        if image.size[0] > max_width or image.size[1] > max_height:
            image = ImageHandler.resize_image(image, max_width=max_width, max_height=max_height)

        return image
