"""Mock connection package: shared shell in base, one personality module per vendor."""

from scpi_control.connection.mock.base import MOCK_SCREENSHOT_BMP, MockConnection

__all__ = ["MockConnection", "MOCK_SCREENSHOT_BMP"]
