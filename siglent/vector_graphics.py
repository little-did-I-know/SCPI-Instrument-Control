"""Vector graphics generation for oscilloscope XY mode display.

This module enables drawing shapes, text, and animations on the oscilloscope screen
by generating synchronized waveforms for X and Y channels. Requires the 'fun' extras:
    pip install "Siglent-Oscilloscope[fun]"

Examples:
    >>> from siglent import Oscilloscope
    >>> from siglent.vector_graphics import VectorDisplay, Shape
    >>>
    >>> scope = Oscilloscope('192.168.1.100')
    >>> scope.connect()
    >>>
    >>> # Create vector display using CH1 (X) and CH2 (Y)
    >>> display = VectorDisplay(scope, ch_x=1, ch_y=2)
    >>> display.enable_xy_mode()
    >>>
    >>> # Draw a circle
    >>> circle = Shape.circle(radius=1.0, points=1000)
    >>> display.draw(circle)
    >>>
    >>> # Draw text
    >>> text = Shape.text("HELLO", font_size=0.5)
    >>> display.draw(text)
    >>>
    >>> # Animate rotation
    >>> for angle in range(0, 360, 5):
    ...     rotated = text.rotate(angle)
    ...     display.draw(rotated)
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

import numpy as np

from siglent import exceptions

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    from shapely import affinity
    from shapely.geometry import LineString, Point

    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import svgpathtools

    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False


def _check_fun_dependencies():
    """Check if fun extras are installed."""
    missing = []
    if not SHAPELY_AVAILABLE:
        missing.append("shapely>=2.0.0")
    if not PIL_AVAILABLE:
        missing.append("Pillow>=10.0.0")
    if not SVG_AVAILABLE:
        missing.append("svgpathtools>=1.6.0")

    if missing:
        raise ImportError(f"Vector graphics features require the 'fun' extras.\n" f"Missing packages: {', '.join(missing)}\n\n" f'Install with: pip install "Siglent-Oscilloscope[fun]"')


@dataclass
class VectorPath:
    """Represents a vector graphics path as X and Y coordinate arrays.

    Attributes:
        x: X coordinates (normalized to -1.0 to 1.0)
        y: Y coordinates (normalized to -1.0 to 1.0)
        connected: Whether to connect end to start (closed path)
    """

    x: np.ndarray
    y: np.ndarray
    connected: bool = False

    def scale(self, factor: float) -> "VectorPath":
        """Scale the path by a factor."""
        return VectorPath(x=self.x * factor, y=self.y * factor, connected=self.connected)

    def translate(self, dx: float, dy: float) -> "VectorPath":
        """Translate the path by (dx, dy)."""
        return VectorPath(x=self.x + dx, y=self.y + dy, connected=self.connected)

    def rotate(self, angle_degrees: float, origin: Tuple[float, float] = (0, 0)) -> "VectorPath":
        """Rotate the path around an origin point."""
        angle_rad = np.radians(angle_degrees)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # Translate to origin
        x_centered = self.x - origin[0]
        y_centered = self.y - origin[1]

        # Rotate
        x_rotated = x_centered * cos_a - y_centered * sin_a
        y_rotated = x_centered * sin_a + y_centered * cos_a

        # Translate back
        return VectorPath(x=x_rotated + origin[0], y=y_rotated + origin[1], connected=self.connected)

    def flip_x(self) -> "VectorPath":
        """Flip horizontally."""
        return VectorPath(x=-self.x, y=self.y, connected=self.connected)

    def flip_y(self) -> "VectorPath":
        """Flip vertically."""
        return VectorPath(x=self.x, y=-self.y, connected=self.connected)

    def combine(self, other: "VectorPath") -> "VectorPath":
        """Combine two paths (concatenate points)."""
        return VectorPath(
            x=np.concatenate([self.x, other.x]),
            y=np.concatenate([self.y, other.y]),
            connected=False,
        )  # Combined paths are typically not closed


class Shape:
    """Factory class for creating common vector graphics shapes."""

    @staticmethod
    def circle(radius: float = 1.0, points: int = 1000, center: Tuple[float, float] = (0, 0)) -> VectorPath:
        """Generate a circle.

        Args:
            radius: Circle radius (0.0 to 1.0 normalized)
            points: Number of points for smoothness
            center: Center coordinates (x, y)

        Returns:
            VectorPath representing the circle
        """
        theta = np.linspace(0, 2 * np.pi, points)
        x = radius * np.cos(theta) + center[0]
        y = radius * np.sin(theta) + center[1]
        return VectorPath(x=x, y=y, connected=True)

    @staticmethod
    def line(start: Tuple[float, float], end: Tuple[float, float], points: int = 100) -> VectorPath:
        """Generate a line segment.

        Args:
            start: Starting point (x, y)
            end: Ending point (x, y)
            points: Number of points along the line

        Returns:
            VectorPath representing the line
        """
        x = np.linspace(start[0], end[0], points)
        y = np.linspace(start[1], end[1], points)
        return VectorPath(x=x, y=y, connected=False)

    @staticmethod
    def rectangle(
        width: float,
        height: float,
        center: Tuple[float, float] = (0, 0),
        points_per_side: int = 100,
    ) -> VectorPath:
        """Generate a rectangle.

        Args:
            width: Rectangle width
            height: Rectangle height
            center: Center coordinates (x, y)
            points_per_side: Points per side for smoothness

        Returns:
            VectorPath representing the rectangle
        """
        half_w = width / 2
        half_h = height / 2
        cx, cy = center

        # Four corners
        corners = [
            (cx - half_w, cy - half_h),  # Bottom-left
            (cx + half_w, cy - half_h),  # Bottom-right
            (cx + half_w, cy + half_h),  # Top-right
            (cx - half_w, cy + half_h),  # Top-left
        ]

        # Generate points along each edge
        x_points = []
        y_points = []
        for i in range(4):
            start = corners[i]
            end = corners[(i + 1) % 4]
            x_edge = np.linspace(start[0], end[0], points_per_side, endpoint=False)
            y_edge = np.linspace(start[1], end[1], points_per_side, endpoint=False)
            x_points.extend(x_edge)
            y_points.extend(y_edge)

        return VectorPath(x=np.array(x_points), y=np.array(y_points), connected=True)

    @staticmethod
    def polygon(vertices: List[Tuple[float, float]], points_per_side: int = 100) -> VectorPath:
        """Generate a polygon from vertices.

        Args:
            vertices: List of (x, y) vertex coordinates
            points_per_side: Points per side for smoothness

        Returns:
            VectorPath representing the polygon
        """
        x_points = []
        y_points = []
        n = len(vertices)

        for i in range(n):
            start = vertices[i]
            end = vertices[(i + 1) % n]
            x_edge = np.linspace(start[0], end[0], points_per_side, endpoint=False)
            y_edge = np.linspace(start[1], end[1], points_per_side, endpoint=False)
            x_points.extend(x_edge)
            y_points.extend(y_edge)

        return VectorPath(x=np.array(x_points), y=np.array(y_points), connected=True)

    @staticmethod
    def star(
        num_points: int = 5,
        outer_radius: float = 1.0,
        inner_radius: float = 0.4,
        center: Tuple[float, float] = (0, 0),
        points_per_line: int = 50,
    ) -> VectorPath:
        """Generate a star shape.

        Args:
            num_points: Number of star points
            outer_radius: Radius to outer points
            inner_radius: Radius to inner points
            center: Center coordinates (x, y)
            points_per_line: Points per line segment

        Returns:
            VectorPath representing the star
        """
        vertices = []
        for i in range(num_points * 2):
            angle = (i * np.pi / num_points) - np.pi / 2
            radius = outer_radius if i % 2 == 0 else inner_radius
            x = center[0] + radius * np.cos(angle)
            y = center[1] + radius * np.sin(angle)
            vertices.append((x, y))

        return Shape.polygon(vertices, points_per_line)

    @staticmethod
    def text(
        text: str,
        font_size: float = 0.5,
        position: Tuple[float, float] = (0, 0),
        samples_per_unit: int = 200,
    ) -> VectorPath:
        """Generate text as vector paths.

        Note: Requires PIL (Pillow) to be installed.
        This creates simple text outlines. For better results, use SVG fonts.

        Args:
            text: Text string to render
            font_size: Font size (normalized)
            position: Position (x, y)
            samples_per_unit: Sampling density for contours

        Returns:
            VectorPath representing the text
        """
        _check_fun_dependencies()

        # Create image with text
        img_size = 512
        img = Image.new("L", (img_size, img_size), 0)
        draw = ImageDraw.Draw(img)

        # Try to use a reasonable font, fall back to default
        try:
            font = ImageFont.truetype("arial.ttf", int(font_size * 200))
        except (OSError, IOError):
            # Fallback to default font if arial.ttf not found
            font = ImageFont.load_default()

        # Draw text in center
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_pos = ((img_size - text_width) // 2, (img_size - text_height) // 2)
        draw.text(text_pos, text, fill=255, font=font)

        # Convert to numpy array
        img_array = np.array(img)

        # Find contours (simple edge detection)
        threshold = 128
        binary = img_array > threshold

        # Extract edge points
        x_coords = []
        y_coords = []
        for y in range(1, img_size - 1):
            for x in range(1, img_size - 1):
                # Check if this is an edge pixel
                if binary[y, x]:
                    neighbors = [
                        binary[y - 1, x],
                        binary[y + 1, x],
                        binary[y, x - 1],
                        binary[y, x + 1],
                    ]
                    if not all(neighbors):  # Edge pixel
                        # Normalize to -1 to 1 range
                        x_norm = (x / img_size - 0.5) * 2
                        y_norm = -(y / img_size - 0.5) * 2  # Flip Y
                        x_coords.append(x_norm * font_size + position[0])
                        y_coords.append(y_norm * font_size + position[1])

        if not x_coords:
            logger.warning(f"No text outline generated for '{text}'")
            return Shape.circle(0.01, 10)  # Return tiny dot as fallback

        return VectorPath(x=np.array(x_coords), y=np.array(y_coords), connected=False)

    @staticmethod
    def lissajous(a: int = 3, b: int = 2, delta: float = np.pi / 2, points: int = 2000) -> VectorPath:
        """Generate Lissajous curve.

        Args:
            a: Frequency ratio for X
            b: Frequency ratio for Y
            delta: Phase shift
            points: Number of points

        Returns:
            VectorPath representing the Lissajous curve
        """
        t = np.linspace(0, 2 * np.pi, points)
        x = np.sin(a * t + delta)
        y = np.sin(b * t)
        return VectorPath(x=x, y=y, connected=True)


class VectorDisplay:
    """Manages oscilloscope XY mode display for vector graphics.

    This class configures the oscilloscope for XY mode and provides methods
    to draw vector graphics by generating synchronized waveforms.

    Note: This requires an external AWG/DAC to feed signals into the scope channels,
    or the scope's built-in AWG if available. The VectorDisplay class generates the
    waveform data that should be loaded into the AWG.

    Examples:
        >>> display = VectorDisplay(scope, ch_x=1, ch_y=2)
        >>> display.enable_xy_mode()
        >>> circle = Shape.circle(radius=0.8)
        >>> display.draw(circle)
    """

    def __init__(self, oscilloscope, ch_x: int = 1, ch_y: int = 2):
        """Initialize vector display.

        Args:
            oscilloscope: Oscilloscope instance
            ch_x: Channel number for X axis (default: 1)
            ch_y: Channel number for Y axis (default: 2)
        """
        self._scope = oscilloscope
        self.ch_x = ch_x
        self.ch_y = ch_y
        self._xy_mode_enabled = False

        logger.info(f"Vector display initialized (X: CH{ch_x}, Y: CH{ch_y})")

    def enable_xy_mode(self, voltage_scale: float = 1.0):
        """Enable XY display mode on the oscilloscope.

        Args:
            voltage_scale: Voltage scale per division for both channels
        """
        try:
            # Enable both channels
            self._scope.write(f"C{self.ch_x}:TRA ON")
            self._scope.write(f"C{self.ch_y}:TRA ON")

            # Set voltage scales
            self._scope.write(f"C{self.ch_x}:VDIV {voltage_scale}")
            self._scope.write(f"C{self.ch_y}:VDIV {voltage_scale}")

            # Set AC coupling to remove DC offset
            self._scope.write(f"C{self.ch_x}:CPL DC")
            self._scope.write(f"C{self.ch_y}:CPL DC")

            # Set trigger to AUTO mode
            self._scope.write("TRIG_MODE AUTO")

            # TODO: Enable XY mode (command may vary by model)
            # Some Siglent scopes use: "XY_MODE ON" or "XYMODE ON"
            # For now, we'll note this in documentation
            try:
                self._scope.write("XY_MODE ON")
            except (exceptions.CommandError, exceptions.SiglentConnectionError, exceptions.SiglentTimeoutError) as e:
                logger.warning(f"Could not enable XY mode automatically: {e}. " "Please manually enable XY mode on the oscilloscope:\n" "  Display → XY Mode → ON")

            self._xy_mode_enabled = True
            logger.info("XY mode enabled")

        except Exception as e:
            logger.error(f"Failed to enable XY mode: {e}")
            raise

    def disable_xy_mode(self):
        """Disable XY mode and return to normal time-domain display."""
        try:
            try:
                self._scope.write("XY_MODE OFF")
            except (exceptions.CommandError, exceptions.SiglentConnectionError, exceptions.SiglentTimeoutError) as e:
                logger.warning(f"Could not disable XY mode automatically: {e}. Please disable manually.")

            self._xy_mode_enabled = False
            logger.info("XY mode disabled")
        except Exception as e:
            logger.error(f"Failed to disable XY mode: {e}")

    def draw(self, path: VectorPath, sample_rate: float = 1e6, duration: float = 0.1):
        """Draw a vector path on the oscilloscope.

        Note: This method generates waveform data that should be loaded into
        an external AWG or the scope's built-in AWG. It does not directly
        control the scope's display.

        Args:
            path: VectorPath to draw
            sample_rate: Desired sample rate (Hz) for the AWG
            duration: Duration to display (seconds)

        Returns:
            Tuple of (x_waveform, y_waveform) as numpy arrays ready for AWG upload
        """
        if not self._xy_mode_enabled:
            logger.warning("XY mode not enabled. Call enable_xy_mode() first.")

        # Resample path to match desired sample rate and duration
        num_samples = int(sample_rate * duration)

        # If path has fewer points, interpolate; if more, decimate
        if len(path.x) < num_samples:
            # Interpolate
            t_original = np.linspace(0, 1, len(path.x))
            t_new = np.linspace(0, 1, num_samples)
            x_resampled = np.interp(t_new, t_original, path.x)
            y_resampled = np.interp(t_new, t_original, path.y)
        else:
            # Decimate
            indices = np.linspace(0, len(path.x) - 1, num_samples, dtype=int)
            x_resampled = path.x[indices]
            y_resampled = path.y[indices]

        # If path is connected, ensure it loops
        if path.connected:
            # Repeat the waveform to fill duration
            repeats = max(1, int(duration * sample_rate / len(x_resampled)))
            x_waveform = np.tile(x_resampled, repeats)[:num_samples]
            y_waveform = np.tile(y_resampled, repeats)[:num_samples]
        else:
            x_waveform = x_resampled
            y_waveform = y_resampled

        logger.info(f"Generated waveforms: {len(x_waveform)} samples at {sample_rate/1e6:.1f} MHz, " f"duration {duration*1000:.1f} ms")

        return x_waveform, y_waveform

    def save_waveforms(
        self,
        path: VectorPath,
        filename_prefix: str,
        sample_rate: float = 1e6,
        duration: float = 0.1,
        format: str = "csv",
    ):
        """Generate and save waveforms to files for AWG upload.

        Args:
            path: VectorPath to draw
            filename_prefix: Prefix for output files (e.g., 'circle')
            sample_rate: Sample rate for AWG (Hz)
            duration: Duration (seconds)
            format: Output format ('csv', 'npy', or 'bin')
        """
        x_wave, y_wave = self.draw(path, sample_rate, duration)

        if format == "csv":
            # Save as CSV
            np.savetxt(f"{filename_prefix}_x.csv", x_wave, delimiter=",")
            np.savetxt(f"{filename_prefix}_y.csv", y_wave, delimiter=",")
            logger.info(f"Saved CSV files: {filename_prefix}_x.csv, {filename_prefix}_y.csv")

        elif format == "npy":
            # Save as NumPy binary
            np.save(f"{filename_prefix}_x.npy", x_wave)
            np.save(f"{filename_prefix}_y.npy", y_wave)
            logger.info(f"Saved NumPy files: {filename_prefix}_x.npy, {filename_prefix}_y.npy")

        elif format == "bin":
            # Save as raw binary (float32)
            x_wave.astype(np.float32).tofile(f"{filename_prefix}_x.bin")
            y_wave.astype(np.float32).tofile(f"{filename_prefix}_y.bin")
            logger.info(f"Saved binary files: {filename_prefix}_x.bin, {filename_prefix}_y.bin")

        else:
            raise ValueError(f"Unknown format: {format}. Use 'csv', 'npy', or 'bin'")

    def __repr__(self) -> str:
        """String representation."""
        mode_status = "enabled" if self._xy_mode_enabled else "disabled"
        return f"VectorDisplay(CH{self.ch_x}→X, CH{self.ch_y}→Y, XY mode: {mode_status})"
