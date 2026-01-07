"""Connection manager for storing and retrieving recent oscilloscope connections."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import QSettings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages recent oscilloscope connections using QSettings.

    Stores connection history persistently across application sessions,
    including IP addresses, ports, model information, and timestamps.
    """

    MAX_RECENT_CONNECTIONS = 10

    def __init__(self):
        """Initialize connection manager with QSettings."""
        self.settings = QSettings("Siglent", "OscilloscopeControl")
        logger.info("Connection manager initialized")

    def add_connection(self, host: str, port: int = 5024, model_name: Optional[str] = None) -> None:
        """Add a connection to the recent connections list.

        Args:
            host: IP address or hostname
            port: TCP port (default: 5024)
            model_name: Optional model name (e.g., "SDS824X HD")
        """
        # Get existing connections
        recent = self.get_recent_connections()

        # Create new connection entry
        new_connection = {
            "host": host,
            "port": port,
            "model_name": model_name or "Unknown",
            "timestamp": datetime.now().isoformat(),
        }

        # Remove duplicate if exists (update to latest)
        recent = [conn for conn in recent if not (conn["host"] == host and conn["port"] == port)]

        # Add new connection at the beginning
        recent.insert(0, new_connection)

        # Limit to max recent connections
        recent = recent[: self.MAX_RECENT_CONNECTIONS]

        # Save to settings
        self.settings.setValue("recent_connections", recent)
        logger.info(f"Added connection: {host}:{port} ({model_name})")

    def get_recent_connections(self) -> List[Dict[str, any]]:
        """Get list of recent connections.

        Returns:
            List of connection dictionaries with keys: host, port, model_name, timestamp
            Sorted by most recent first
        """
        recent = self.settings.value("recent_connections", [])

        # QSettings may return different types depending on platform/Qt version
        if recent is None:
            recent = []
        elif not isinstance(recent, list):
            recent = []

        return recent

    def clear_recent_connections(self) -> None:
        """Clear all recent connections."""
        self.settings.setValue("recent_connections", [])
        logger.info("Cleared all recent connections")

    def remove_connection(self, host: str, port: int = 5024) -> None:
        """Remove a specific connection from recent list.

        Args:
            host: IP address or hostname
            port: TCP port
        """
        recent = self.get_recent_connections()
        recent = [conn for conn in recent if not (conn["host"] == host and conn["port"] == port)]
        self.settings.setValue("recent_connections", recent)
        logger.info(f"Removed connection: {host}:{port}")

    def get_last_connection(self) -> Optional[Dict[str, any]]:
        """Get the most recent connection.

        Returns:
            Connection dictionary or None if no recent connections
        """
        recent = self.get_recent_connections()
        return recent[0] if recent else None

    def save_connection_profile(
        self,
        name: str,
        host: str,
        port: int = 5024,
        model_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Save a named connection profile.

        Args:
            name: Profile name
            host: IP address or hostname
            port: TCP port
            model_name: Optional model name
            notes: Optional notes about this connection
        """
        profiles = self.get_connection_profiles()

        profile = {
            "name": name,
            "host": host,
            "port": port,
            "model_name": model_name or "Unknown",
            "notes": notes or "",
            "created": datetime.now().isoformat(),
        }

        # Update if exists, otherwise add
        profiles[name] = profile

        self.settings.setValue("connection_profiles", profiles)
        logger.info(f"Saved connection profile: {name}")

    def get_connection_profiles(self) -> Dict[str, Dict[str, any]]:
        """Get all saved connection profiles.

        Returns:
            Dictionary of profile_name -> profile_data
        """
        profiles = self.settings.value("connection_profiles", {})

        if profiles is None:
            profiles = {}
        elif not isinstance(profiles, dict):
            profiles = {}

        return profiles

    def get_connection_profile(self, name: str) -> Optional[Dict[str, any]]:
        """Get a specific connection profile by name.

        Args:
            name: Profile name

        Returns:
            Profile dictionary or None if not found
        """
        profiles = self.get_connection_profiles()
        return profiles.get(name)

    def delete_connection_profile(self, name: str) -> None:
        """Delete a connection profile.

        Args:
            name: Profile name to delete
        """
        profiles = self.get_connection_profiles()
        if name in profiles:
            del profiles[name]
            self.settings.setValue("connection_profiles", profiles)
            logger.info(f"Deleted connection profile: {name}")

    def format_connection_display(self, connection: Dict[str, any]) -> str:
        """Format a connection for display in UI.

        Args:
            connection: Connection dictionary

        Returns:
            Formatted string for display
        """
        host = connection.get("host", "Unknown")
        port = connection.get("port", 5024)
        model = connection.get("model_name", "Unknown")

        # Parse timestamp if available
        timestamp_str = connection.get("timestamp", "")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                time_display = timestamp.strftime("%Y-%m-%d %H:%M")
            except:
                time_display = "Unknown time"
        else:
            time_display = "Unknown time"

        return f"{host}:{port} - {model} ({time_display})"

    def __repr__(self) -> str:
        """String representation."""
        num_recent = len(self.get_recent_connections())
        num_profiles = len(self.get_connection_profiles())
        return f"ConnectionManager(recent={num_recent}, profiles={num_profiles})"
