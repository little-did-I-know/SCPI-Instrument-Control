"""Connection module for SCPI communication with oscilloscopes and power supplies.

Supports multiple connection types:
- SocketConnection: TCP/IP Ethernet connection (default)
- VISAConnection: USB, GPIB, Serial via PyVISA (optional, requires [usb] extras)
- MockConnection: Mock connection for testing
"""

from siglent.connection.base import BaseConnection
from siglent.connection.mock import MockConnection
from siglent.connection.socket import SocketConnection

# Optional VISA connection (requires pyvisa)
# Import is attempted but won't fail if pyvisa not installed
try:
    from siglent.connection.visa_connection import VISAConnection, find_siglent_devices, list_visa_resources

    _VISA_AVAILABLE = True
except ImportError:
    _VISA_AVAILABLE = False
    VISAConnection = None
    list_visa_resources = None
    find_siglent_devices = None

# Export all available connections
__all__ = [
    "BaseConnection",
    "MockConnection",
    "SocketConnection",
]

# Add VISA exports if available
if _VISA_AVAILABLE:
    __all__.extend(
        [
            "VISAConnection",
            "list_visa_resources",
            "find_siglent_devices",
        ]
    )
