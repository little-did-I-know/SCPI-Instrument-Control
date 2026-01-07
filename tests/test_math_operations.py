"""Test math channel operations."""

import numpy as np
import pytest

from scpi_control.math_channel import MathChannel, MathOperations
from scpi_control.waveform import WaveformData


@pytest.fixture
def sample_waveforms():
    """Create sample waveforms for testing."""
    time = np.linspace(0, 1, 100)
    voltage1 = np.sin(2 * np.pi * time)
    voltage2 = np.cos(2 * np.pi * time)

    # Create WaveformData with all required parameters
    wf1 = WaveformData(
        time=time,
        voltage=voltage1,
        channel=1,
        sample_rate=100.0,
        record_length=100,
        timebase=0.1,
        voltage_scale=1.0,
        voltage_offset=0.0,
    )  # 100 samples per second  # 0.1 s/div  # 1 V/div
    wf2 = WaveformData(
        time=time,
        voltage=voltage2,
        channel=2,
        sample_rate=100.0,
        record_length=100,
        timebase=0.1,
        voltage_scale=1.0,
        voltage_offset=0.0,
    )

    return wf1, wf2


def test_math_add(sample_waveforms):
    """Test addition operation."""
    wf1, wf2 = sample_waveforms
    result = MathOperations.add(wf1, wf2)

    assert result is not None
    assert len(result.voltage) == len(wf1.voltage)
    np.testing.assert_array_almost_equal(result.voltage, wf1.voltage + wf2.voltage)


def test_math_subtract(sample_waveforms):
    """Test subtraction operation."""
    wf1, wf2 = sample_waveforms
    result = MathOperations.subtract(wf1, wf2)

    assert result is not None
    assert len(result.voltage) == len(wf1.voltage)
    np.testing.assert_array_almost_equal(result.voltage, wf1.voltage - wf2.voltage)


def test_math_multiply(sample_waveforms):
    """Test multiplication operation."""
    wf1, wf2 = sample_waveforms
    result = MathOperations.multiply(wf1, wf2)

    assert result is not None
    assert len(result.voltage) == len(wf1.voltage)
    np.testing.assert_array_almost_equal(result.voltage, wf1.voltage * wf2.voltage)


def test_math_divide(sample_waveforms):
    """Test division operation."""
    wf1, wf2 = sample_waveforms
    result = MathOperations.divide(wf1, wf2)

    assert result is not None
    assert len(result.voltage) == len(wf1.voltage)


def test_math_scale(sample_waveforms):
    """Test scale operation."""
    wf1, _ = sample_waveforms
    factor = 2.5
    result = MathOperations.scale(wf1, factor)

    assert result is not None
    np.testing.assert_array_almost_equal(result.voltage, wf1.voltage * factor)


def test_math_offset(sample_waveforms):
    """Test offset operation."""
    wf1, _ = sample_waveforms
    offset = 1.5
    result = MathOperations.offset(wf1, offset)

    assert result is not None
    np.testing.assert_array_almost_equal(result.voltage, wf1.voltage + offset)


def test_math_abs(sample_waveforms):
    """Test absolute value operation."""
    wf1, _ = sample_waveforms
    result = MathOperations.abs_value(wf1)

    assert result is not None
    np.testing.assert_array_almost_equal(result.voltage, np.abs(wf1.voltage))


def test_math_invert(sample_waveforms):
    """Test invert operation."""
    wf1, _ = sample_waveforms
    result = MathOperations.invert(wf1)

    assert result is not None
    np.testing.assert_array_almost_equal(result.voltage, -wf1.voltage)


def test_math_integrate(sample_waveforms):
    """Test integration operation."""
    wf1, _ = sample_waveforms
    result = MathOperations.integrate(wf1)

    assert result is not None
    assert len(result.voltage) == len(wf1.voltage)


def test_math_differentiate(sample_waveforms):
    """Test differentiation operation."""
    wf1, _ = sample_waveforms
    result = MathOperations.differentiate(wf1)

    assert result is not None
    assert len(result.voltage) == len(wf1.voltage)


def test_math_channel_creation():
    """Test MathChannel can be created."""
    from unittest.mock import Mock

    scope = Mock()
    channel = MathChannel(scope, "M1")

    assert channel is not None
    assert channel.name == "M1"
    assert channel.enabled is False


def test_math_channel_enable_disable():
    """Test MathChannel enable/disable."""
    from unittest.mock import Mock

    scope = Mock()
    channel = MathChannel(scope, "M1")

    channel.enable()
    assert channel.enabled is True

    channel.disable()
    assert channel.enabled is False


def test_math_channel_expression():
    """Test MathChannel expression setting."""
    from unittest.mock import Mock

    scope = Mock()
    channel = MathChannel(scope, "M1")

    channel.set_expression("C1 + C2")
    assert channel.expression == "C1 + C2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
