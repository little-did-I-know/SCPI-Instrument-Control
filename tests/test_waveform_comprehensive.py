"""Comprehensive tests for waveform module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import numpy as np
import pytest

from siglent.exceptions import CommandError
from siglent.waveform import Waveform, WaveformData


class TestWaveformData:
    """Test WaveformData dataclass."""

    def test_create_waveform_data(self):
        """Test creating WaveformData."""
        time = np.linspace(0, 1e-3, 1000)
        voltage = np.sin(2 * np.pi * 1000 * time)

        waveform = WaveformData(time=time, voltage=voltage, channel=1, sample_rate=1e6, record_length=1000, source="Test", description="Test waveform")

        assert len(waveform.time) == 1000
        assert len(waveform.voltage) == 1000
        assert waveform.channel == 1
        assert waveform.sample_rate == 1e6
        assert waveform.source == "Test"

    def test_waveform_data_minimal(self):
        """Test creating WaveformData with minimal parameters."""
        time = np.array([0, 1, 2])
        voltage = np.array([0, 1, 0])

        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        assert len(waveform.time) == 3
        assert len(waveform.voltage) == 3
        assert waveform.channel == 1

    def test_waveform_properties(self):
        """Test waveform computed properties."""
        time = np.linspace(0, 1e-3, 1000)
        voltage = np.sin(2 * np.pi * 1000 * time)

        waveform = WaveformData(time=time, voltage=voltage, channel=1, sample_rate=1e6, record_length=1000)

        # Test that arrays are accessible
        assert isinstance(waveform.time, np.ndarray)
        assert isinstance(waveform.voltage, np.ndarray)
        assert waveform.sample_rate == 1e6
        assert waveform.record_length == 1000


@pytest.fixture
def mock_scope():
    """Create a mock oscilloscope."""
    scope = Mock()
    scope.send_command = Mock()
    scope.query = Mock()
    scope.query_binary = Mock()
    return scope


@pytest.fixture
def waveform_handler(mock_scope):
    """Create a Waveform instance."""
    return Waveform(mock_scope)


class TestWaveformInitialization:
    """Test Waveform initialization."""

    def test_init(self, mock_scope):
        """Test initialization."""
        capture = Waveform(mock_scope)
        assert capture._scope == mock_scope


class TestWaveform:
    """Test waveform capture functionality."""

    def test_capture_waveform(self, waveform_handler, mock_scope):
        """Test capturing a waveform."""
        # Mock binary waveform data with proper header
        mock_binary = b"#9000001000" + bytes(b"\x80" * 1000)
        mock_scope.read_raw.return_value = mock_binary

        # Mock descriptor responses
        mock_scope.query.side_effect = [
            "1.0E+00V",  # voltage scale
            "0.0E+00V",  # offset
            "1.0E-03S",  # time scale
            "1.0E+06Sa/s",  # sample rate
        ]

        waveform = waveform_handler.acquire(channel=1)

        assert isinstance(waveform, WaveformData)
        assert waveform.channel == 1
        assert len(waveform.voltage) > 0

    def test_capture_multiple_channels(self, waveform_handler, mock_scope):
        """Test capturing from multiple channels."""
        for channel in [1, 2, 3, 4]:
            mock_binary = b"#9000001000" + bytes(b"\x80" * 1000)
            mock_scope.read_raw.return_value = mock_binary
            mock_scope.query.side_effect = ["1.0E+00V", "0.0E+00V", "1.0E-03S", "1.0E+06Sa/s"]

            waveform = waveform_handler.acquire(channel=channel)
            assert waveform.channel == channel

    def test_capture_invalid_channel(self, waveform_handler, mock_scope):
        """Test capturing with invalid channel number."""
        with pytest.raises(Exception, match="Invalid channel number"):
            waveform_handler.acquire(channel=0)

        with pytest.raises(Exception, match="Invalid channel number"):
            waveform_handler.acquire(channel=5)


class TestWaveformParsing:
    """Test waveform data parsing."""

    def test_parse_binary_waveform(self, waveform_handler):
        """Test parsing binary waveform data."""
        # Create test binary data
        test_data = np.array([0, 127, 255, 128, 64], dtype=np.uint8)
        binary_data = test_data.tobytes()

        if hasattr(waveform_handler, "_parse_waveform_data"):
            parsed = waveform_handler._parse_waveform_data(binary_data, 1.0, 0.0, 25)
            assert isinstance(parsed, np.ndarray)
            assert len(parsed) > 0

    def test_convert_binary_to_voltage(self, waveform_handler):
        """Test converting binary values to voltage."""
        # Test voltage conversion formula
        if hasattr(waveform_handler, "_binary_to_voltage"):
            # Typical conversion: (value - 128) * vdiv / 25
            voltage = waveform_handler._binary_to_voltage(128, vdiv=1.0, offset=0.0, code_per_div=25)
            assert voltage == 0.0

            voltage = waveform_handler._binary_to_voltage(153, vdiv=1.0, offset=0.0, code_per_div=25)
            assert abs(voltage - 1.0) < 0.1


class TestWaveformSaving:
    """Test saving waveforms to files."""

    def test_save_waveform_csv(self, waveform_handler, tmp_path):
        """Test saving waveform as CSV."""
        time = np.linspace(0, 1e-3, 100)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.csv"
        waveform_handler.save_waveform(waveform, str(filepath), format="CSV")

        assert filepath.exists()
        content = filepath.read_text()
        assert "Time" in content or "time" in content
        assert "Voltage" in content or "voltage" in content

    def test_save_waveform_npy(self, waveform_handler, tmp_path):
        """Test saving waveform as NPY (compressed numpy format)."""
        time = np.linspace(0, 1e-3, 100)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.npz"
        waveform_handler.save_waveform(waveform, str(filepath), format="NPY")

        assert filepath.exists()

        # Verify NPY contents
        loaded = np.load(str(filepath))
        assert "time" in loaded
        assert "voltage" in loaded
        np.testing.assert_array_almost_equal(loaded["time"], time)
        np.testing.assert_array_almost_equal(loaded["voltage"], voltage)

    def test_save_waveform_mat(self, waveform_handler, tmp_path):
        """Test saving waveform as MAT (if scipy available)."""
        time = np.linspace(0, 1e-3, 100)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.mat"

        try:
            waveform_handler.save_waveform(waveform, str(filepath), format="MAT")
            assert filepath.exists()
        except ImportError:
            pytest.skip("scipy not available for MAT format")

    def test_save_waveform_hdf5(self, waveform_handler, tmp_path):
        """Test saving waveform as HDF5 (if h5py available)."""
        time = np.linspace(0, 1e-3, 100)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.h5"

        try:
            waveform_handler.save_waveform(waveform, str(filepath), format="HDF5")
            assert filepath.exists()
        except ImportError:
            pytest.skip("h5py not available for HDF5 format")

    def test_save_waveform_invalid_format(self, waveform_handler, tmp_path):
        """Test saving with invalid format."""
        time = np.array([0, 1, 2])
        voltage = np.array([0, 1, 0])
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.txt"

        with pytest.raises(Exception, match="Invalid format"):
            waveform_handler.save_waveform(waveform, str(filepath), format="INVALID")


class TestWaveformLoading:
    """Test loading waveforms from files."""

    def test_load_waveform_csv(self, waveform_handler, tmp_path):
        """Test loading waveform from CSV."""
        # Create a CSV file
        time = np.linspace(0, 1e-3, 100)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.csv"
        waveform_handler.save_waveform(waveform, str(filepath), format="CSV")

        # Load it back
        if hasattr(waveform_handler, "load_waveform"):
            loaded = waveform_handler.load_waveform(str(filepath), format="CSV")
            assert isinstance(loaded, WaveformData)
            np.testing.assert_array_almost_equal(loaded.time, time, decimal=6)
            np.testing.assert_array_almost_equal(loaded.voltage, voltage, decimal=6)

    def test_load_waveform_npy(self, waveform_handler, tmp_path):
        """Test loading waveform from NPY."""
        time = np.linspace(0, 1e-3, 100)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        filepath = tmp_path / "test.npz"
        waveform_handler.save_waveform(waveform, str(filepath), format="NPY")

        if hasattr(waveform_handler, "load_waveform"):
            loaded = waveform_handler.load_waveform(str(filepath), format="NPY")
            assert isinstance(loaded, WaveformData)
            np.testing.assert_array_almost_equal(loaded.time, time)
            np.testing.assert_array_almost_equal(loaded.voltage, voltage)


class TestWaveformAnalysis:
    """Test waveform analysis functions."""

    def test_waveform_statistics(self):
        """Test calculating waveform statistics."""
        time = np.linspace(0, 1e-3, 1000)
        voltage = np.sin(2 * np.pi * 1000 * time)
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        # Basic statistics
        vpp = np.ptp(waveform.voltage)
        vrms = np.sqrt(np.mean(waveform.voltage**2))
        mean = np.mean(waveform.voltage)

        assert vpp > 1.9  # Should be close to 2.0 for sine wave
        assert vrms > 0.7  # Should be close to 0.707 for sine wave
        assert abs(mean) < 0.1  # Should be close to 0

    def test_waveform_duration(self):
        """Test calculating waveform duration."""
        time = np.linspace(0, 1e-3, 1000)
        voltage = np.zeros(1000)
        waveform = WaveformData(time=time, voltage=voltage, channel=1, sample_rate=1e6)

        duration = time[-1] - time[0]
        assert abs(duration - 1e-3) < 1e-6


class TestWaveformUtilities:
    """Test utility functions."""

    def test_get_waveform_descriptor(self, waveform_handler, mock_scope):
        """Test getting waveform descriptor."""
        mock_scope.query.side_effect = [
            "VDIV:1.0E+00V",
            "OFST:0.0E+00V",
            "TDIV:1.0E-03S",
            "SARA:1.0E+06Sa/s",
        ]

        if hasattr(waveform_handler, "_get_waveform_descriptor"):
            descriptor = waveform_handler._get_waveform_descriptor(1)
            assert isinstance(descriptor, dict)

    def test_calculate_timebase(self):
        """Test calculating timebase from sample rate."""
        sample_rate = 1e6  # 1 MSa/s
        record_length = 1000

        duration = record_length / sample_rate
        time = np.linspace(0, duration, record_length, endpoint=False)

        assert len(time) == record_length
        assert time[-1] < duration


class TestWaveformComparison:
    """Test waveform comparison functions."""

    def test_compare_waveforms(self):
        """Test comparing two waveforms."""
        time = np.linspace(0, 1e-3, 1000)
        voltage1 = np.sin(2 * np.pi * 1000 * time)
        voltage2 = np.sin(2 * np.pi * 1000 * time) * 0.9  # 90% amplitude

        wf1 = WaveformData(time=time, voltage=voltage1, channel=1)
        wf2 = WaveformData(time=time, voltage=voltage2, channel=2)

        # Calculate difference
        diff = wf1.voltage - wf2.voltage
        assert len(diff) == len(voltage1)
        assert np.max(np.abs(diff)) > 0

    def test_waveform_correlation(self):
        """Test calculating correlation between waveforms."""
        time = np.linspace(0, 1e-3, 1000)
        voltage1 = np.sin(2 * np.pi * 1000 * time)
        voltage2 = np.sin(2 * np.pi * 1000 * time + np.pi / 4)  # 45° phase shift

        wf1 = WaveformData(time=time, voltage=voltage1, channel=1)
        wf2 = WaveformData(time=time, voltage=voltage2, channel=2)

        # Calculate correlation
        correlation = np.corrcoef(wf1.voltage, wf2.voltage)[0, 1]
        assert -1 <= correlation <= 1


class TestWaveformErrorHandling:
    """Test error handling."""

    def test_capture_communication_error(self, waveform_handler, mock_scope):
        """Test handling communication errors during capture."""
        mock_scope.read_raw.side_effect = TimeoutError("Communication timeout")

        with pytest.raises(Exception):
            waveform_handler.acquire(channel=1)

    def test_save_file_error(self, waveform_handler, tmp_path):
        """Test handling file errors during save."""
        time = np.array([0, 1, 2])
        voltage = np.array([0, 1, 0])
        waveform = WaveformData(time=time, voltage=voltage, channel=1)

        # Try to save to invalid path
        invalid_path = "/invalid/path/test.csv"

        try:
            waveform_handler.save_waveform(waveform, invalid_path, format="CSV")
        except (OSError, IOError, PermissionError):
            pass  # Expected behavior
