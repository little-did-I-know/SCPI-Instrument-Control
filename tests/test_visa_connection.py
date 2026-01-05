"""Tests for VISA connection (USB, GPIB, Serial).

These tests verify the VISAConnection class works correctly.
Most tests use mocking since PyVISA may not be installed.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

# Skip all tests if pyvisa not available
pyvisa_available = False
try:
    import pyvisa

    from siglent.connection.visa_connection import VISAConnection, list_visa_resources

    pyvisa_available = True
except ImportError:
    pass


@pytest.mark.skipif(not pyvisa_available, reason="PyVISA not installed")
class TestVISAConnectionImport:
    """Test that VISA connection can be imported when pyvisa is available."""

    def test_import_visa_connection(self):
        """Test VISAConnection import."""
        from siglent.connection import VISAConnection

        assert VISAConnection is not None

    def test_import_utilities(self):
        """Test utility function imports."""
        from siglent.connection import find_siglent_devices, list_visa_resources

        assert list_visa_resources is not None
        assert find_siglent_devices is not None


@pytest.mark.skipif(not pyvisa_available, reason="PyVISA not installed")
class TestVISAConnectionInitialization:
    """Test VISA connection initialization."""

    def test_init_usb_resource(self):
        """Test initialization with USB resource string."""
        conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X123456::INSTR")
        assert conn.resource_string == "USB0::0xF4EC::0xEE38::SPD3X123456::INSTR"
        assert conn.timeout == 5.0
        assert conn.backend == "@py"
        assert not conn.is_connected

    def test_init_gpib_resource(self):
        """Test initialization with GPIB resource string."""
        conn = VISAConnection("GPIB0::12::INSTR", timeout=10.0)
        assert conn.resource_string == "GPIB0::12::INSTR"
        assert conn.timeout == 10.0

    def test_init_serial_resource(self):
        """Test initialization with Serial resource string."""
        conn = VISAConnection("ASRL3::INSTR")
        assert conn.resource_string == "ASRL3::INSTR"

    def test_init_custom_backend(self):
        """Test initialization with custom backend."""
        conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR", backend="")
        assert conn.backend == ""


@pytest.mark.skipif(not pyvisa_available, reason="PyVISA not installed")
class TestVISAConnectionMocked:
    """Test VISA connection with mocked PyVISA."""

    @pytest.fixture
    def mock_visa_resource(self):
        """Create a mock VISA resource."""
        resource = MagicMock()
        resource.timeout = 5000
        resource.read_termination = "\n"
        resource.write_termination = "\n"
        return resource

    @pytest.fixture
    def mock_resource_manager(self, mock_visa_resource):
        """Create a mock VISA resource manager."""
        rm = MagicMock()
        rm.open_resource.return_value = mock_visa_resource
        return rm

    def test_connect_success(self, mock_resource_manager, mock_visa_resource):
        """Test successful connection."""
        with patch("pyvisa.ResourceManager", return_value=mock_resource_manager):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()

            assert conn.is_connected
            mock_resource_manager.open_resource.assert_called_once()

    def test_disconnect(self, mock_resource_manager, mock_visa_resource):
        """Test disconnection."""
        with patch("pyvisa.ResourceManager", return_value=mock_resource_manager):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()
            conn.disconnect()

            assert not conn.is_connected
            mock_visa_resource.close.assert_called_once()
            mock_resource_manager.close.assert_called_once()

    def test_write_command(self, mock_resource_manager, mock_visa_resource):
        """Test writing a SCPI command."""
        with patch("pyvisa.ResourceManager", return_value=mock_resource_manager):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()

            conn.write("*RST")

            mock_visa_resource.write.assert_called_once_with("*RST")

    def test_query_command(self, mock_resource_manager, mock_visa_resource):
        """Test querying a SCPI command."""
        mock_visa_resource.query.return_value = "Siglent,SPD3303X,SPD3X123,V1.0\n"

        with patch("pyvisa.ResourceManager", return_value=mock_resource_manager):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()

            response = conn.query("*IDN?")

            assert response == "Siglent,SPD3303X,SPD3X123,V1.0"
            mock_visa_resource.query.assert_called_once_with("*IDN?")

    def test_write_without_connection(self):
        """Test write raises error when not connected."""
        from siglent.exceptions import SiglentConnectionError

        conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")

        with pytest.raises(SiglentConnectionError):
            conn.write("*RST")

    def test_query_without_connection(self):
        """Test query raises error when not connected."""
        from siglent.exceptions import SiglentConnectionError

        conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")

        with pytest.raises(SiglentConnectionError):
            conn.query("*IDN?")

    def test_write_non_ascii_command(self, mock_resource_manager, mock_visa_resource):
        """Test write raises error for non-ASCII commands."""
        from siglent.exceptions import CommandError

        with patch("pyvisa.ResourceManager", return_value=mock_resource_manager):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()

            with pytest.raises(CommandError):
                conn.write("VOLT 5.0V\u2013")  # Contains en-dash

    def test_query_timeout(self, mock_resource_manager, mock_visa_resource):
        """Test query timeout raises SiglentTimeoutError."""
        from siglent.exceptions import SiglentTimeoutError

        mock_visa_resource.query.side_effect = pyvisa.errors.VisaIOError(-1073807339)  # Timeout error

        with patch("pyvisa.ResourceManager", return_value=mock_resource_manager):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()

            with pytest.raises(SiglentTimeoutError):
                conn.query("*IDN?")


@pytest.mark.skipif(not pyvisa_available, reason="PyVISA not installed")
class TestVISAUtilities:
    """Test VISA utility functions."""

    def test_list_visa_resources(self):
        """Test listing VISA resources."""
        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = [
            "USB0::0xF4EC::0xEE38::SPD3X123::INSTR",
            "GPIB0::12::INSTR",
        ]

        with patch("pyvisa.ResourceManager", return_value=mock_rm):
            resources = list_visa_resources()

            assert len(resources) == 2
            assert "USB0::0xF4EC::0xEE38::SPD3X123::INSTR" in resources
            assert "GPIB0::12::INSTR" in resources

    def test_find_siglent_devices(self):
        """Test finding Siglent devices."""
        from siglent.connection.visa_connection import find_siglent_devices

        mock_instr = MagicMock()
        mock_instr.query.return_value = "Siglent Technologies,SPD3303X,SPD3X123,V1.0"

        mock_rm = MagicMock()
        mock_rm.list_resources.return_value = ["USB0::0xF4EC::0xEE38::SPD3X123::INSTR"]
        mock_rm.open_resource.return_value = mock_instr

        with patch("pyvisa.ResourceManager", return_value=mock_rm):
            devices = find_siglent_devices()

            assert len(devices) == 1
            resource, idn = devices[0]
            assert resource == "USB0::0xF4EC::0xEE38::SPD3X123::INSTR"
            assert "Siglent Technologies" in idn


class TestVISAConnectionWithoutPyVISA:
    """Test behavior when PyVISA is not installed."""

    def test_import_fails_gracefully(self):
        """Test that connection module imports even without pyvisa."""
        # This should not raise an error
        from siglent import connection

        assert connection is not None

    def test_visa_connection_none_when_not_available(self):
        """Test VISAConnection is None in __all__ if pyvisa not installed."""
        # The connection module should still be importable
        try:
            from siglent.connection import VISAConnection

            # If we can import it, pyvisa is available
            assert VISAConnection is not None
        except ImportError:
            # Expected if pyvisa not installed
            pass


@pytest.mark.skipif(not pyvisa_available, reason="PyVISA not installed")
class TestVISAConnectionRepr:
    """Test string representation of VISA connection."""

    def test_repr_disconnected(self):
        """Test repr when disconnected."""
        conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
        repr_str = repr(conn)

        assert "VISAConnection" in repr_str
        assert "USB0::0xF4EC::0xEE38::SPD3X::INSTR" in repr_str
        assert "disconnected" in repr_str

    def test_repr_connected(self):
        """Test repr when connected."""
        mock_rm = MagicMock()
        mock_resource = MagicMock()
        mock_rm.open_resource.return_value = mock_resource

        with patch("pyvisa.ResourceManager", return_value=mock_rm):
            conn = VISAConnection("USB0::0xF4EC::0xEE38::SPD3X::INSTR")
            conn.connect()

            repr_str = repr(conn)

            assert "VISAConnection" in repr_str
            assert "connected" in repr_str
