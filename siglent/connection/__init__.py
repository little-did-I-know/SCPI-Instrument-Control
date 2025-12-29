"""Connection module for SCPI communication with oscilloscope."""

from siglent.connection.base import BaseConnection
from siglent.connection.mock import MockConnection
from siglent.connection.socket import SocketConnection

__all__ = ["BaseConnection", "MockConnection", "SocketConnection"]
