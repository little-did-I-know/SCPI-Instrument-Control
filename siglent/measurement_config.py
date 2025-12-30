"""Configuration data models for visual measurement markers.

This module provides data structures for storing, loading, and saving
measurement marker configurations. Configurations can be saved to JSON
files and shared across sessions or between users.

Classes:
    MeasurementMarkerConfig: Single measurement marker configuration
    MeasurementConfigSet: Collection of markers with metadata

Example:
    >>> # Create a configuration
    >>> marker = MeasurementMarkerConfig(
    ...     id="M1",
    ...     measurement_type="FREQ",
    ...     channel=1,
    ...     gates={'start_x': 0.0, 'end_x': 0.001}
    ... )
    >>>
    >>> # Save to file
    >>> config_set = MeasurementConfigSet(
    ...     name="Power Analysis",
    ...     created_at=datetime.now(),
    ...     markers=[marker]
    ... )
    >>> config_set.save_to_file("power_analysis.json")
    >>>
    >>> # Load from file
    >>> loaded = MeasurementConfigSet.load_from_file("power_analysis.json")
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MeasurementMarkerConfig:
    """Configuration for a single measurement marker.

    Attributes:
        id: Unique identifier for the marker
        measurement_type: Type of measurement (FREQ, PKPK, RISE, etc.)
        channel: Channel number (1-4)
        enabled: Whether marker is currently active
        gates: Dictionary of gate positions (e.g., {'start_x': 0.1, 'end_x': 0.5})
        visual_style: Visual styling options (color, line style, etc.)
        result: Cached measurement result value
        unit: Unit of measurement (Hz, V, s, etc.)
    """

    id: str
    measurement_type: str
    channel: int
    enabled: bool = True
    gates: Dict[str, float] = field(default_factory=dict)
    visual_style: Dict[str, Any] = field(default_factory=dict)
    result: Optional[float] = None
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasurementMarkerConfig":
        """Create instance from dictionary.

        Args:
            data: Dictionary with marker configuration

        Returns:
            MeasurementMarkerConfig instance
        """
        return cls(**data)


@dataclass
class MeasurementConfigSet:
    """Collection of measurement configurations.

    Attributes:
        name: Configuration set name
        created_at: Timestamp when created
        markers: List of measurement marker configurations
        metadata: Additional metadata dictionary
    """

    name: str
    created_at: datetime
    markers: List[MeasurementMarkerConfig] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def save_to_file(self, filepath: str) -> None:
        """Save configuration to JSON file.

        Args:
            filepath: Path to save configuration file

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            # Build data dictionary
            data = {
                "name": self.name,
                "version": "1.0",
                "created_at": self.created_at.isoformat(),
                "metadata": self.metadata,
                "markers": [marker.to_dict() for marker in self.markers],
            }

            # Write to file
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved measurement configuration to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise IOError(f"Failed to save configuration to {filepath}: {e}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "MeasurementConfigSet":
        """Load configuration from JSON file.

        Args:
            filepath: Path to configuration file

        Returns:
            MeasurementConfigSet instance

        Raises:
            IOError: If file cannot be read
            ValueError: If file format is invalid
        """
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Validate version
            version = data.get("version", "1.0")
            if version != "1.0":
                logger.warning(f"Loading configuration with version {version}, expected 1.0")

            # Parse markers
            markers = [MeasurementMarkerConfig.from_dict(m) for m in data.get("markers", [])]

            # Create config set
            config_set = cls(
                name=data["name"],
                created_at=datetime.fromisoformat(data["created_at"]),
                markers=markers,
                metadata=data.get("metadata", {}),
            )

            logger.info(f"Loaded measurement configuration from {filepath} ({len(markers)} markers)")
            return config_set

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {filepath}")
            raise IOError(f"Configuration file not found: {filepath}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise ValueError(f"Invalid JSON format in {filepath}: {e}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise IOError(f"Failed to load configuration from {filepath}: {e}")

    def add_marker(self, marker: MeasurementMarkerConfig) -> None:
        """Add a marker to the configuration.

        Args:
            marker: Marker configuration to add
        """
        self.markers.append(marker)
        logger.debug(f"Added marker {marker.id} to configuration {self.name}")

    def remove_marker(self, marker_id: str) -> bool:
        """Remove a marker by ID.

        Args:
            marker_id: ID of marker to remove

        Returns:
            True if marker was removed, False if not found
        """
        original_count = len(self.markers)
        self.markers = [m for m in self.markers if m.id != marker_id]

        if len(self.markers) < original_count:
            logger.debug(f"Removed marker {marker_id} from configuration {self.name}")
            return True
        else:
            logger.warning(f"Marker {marker_id} not found in configuration {self.name}")
            return False

    def get_marker(self, marker_id: str) -> Optional[MeasurementMarkerConfig]:
        """Get a marker by ID.

        Args:
            marker_id: ID of marker to retrieve

        Returns:
            Marker configuration if found, None otherwise
        """
        for marker in self.markers:
            if marker.id == marker_id:
                return marker
        return None

    def get_default_config_dir(self) -> Path:
        """Get default directory for saving configurations.

        Returns:
            Path to configuration directory
        """
        # Use platform-appropriate config directory
        import platform

        system = platform.system()

        if system == "Windows":
            config_dir = Path.home() / "AppData" / "Local" / "siglent" / "measurement_configs"
        elif system == "Darwin":  # macOS
            config_dir = Path.home() / "Library" / "Application Support" / "siglent" / "measurement_configs"
        else:  # Linux and others
            config_dir = Path.home() / ".config" / "siglent" / "measurement_configs"

        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)

        return config_dir
