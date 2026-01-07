"""Test protocol decoders."""

import numpy as np
import pytest

from scpi_control.protocol_decoders import I2CDecoder, SPIDecoder, UARTDecoder
from scpi_control.waveform import WaveformData


@pytest.fixture
def sample_waveform():
    """Create a sample waveform for testing."""
    time = np.linspace(0, 0.001, 1000)
    voltage = np.zeros_like(time)
    return WaveformData(time=time, voltage=voltage, channel=1)


def test_i2c_decoder_creation():
    """Test I2C decoder can be created."""
    decoder = I2CDecoder()
    assert decoder is not None
    assert decoder.name == "I2C"


def test_i2c_decoder_required_channels():
    """Test I2C decoder required channels."""
    decoder = I2CDecoder()
    channels = decoder.get_required_channels()
    assert "SDA" in channels
    assert "SCL" in channels


def test_i2c_decoder_parameters():
    """Test I2C decoder parameters."""
    decoder = I2CDecoder()
    params = decoder.get_parameters()
    assert "threshold" in params
    assert "address_bits" in params


def test_spi_decoder_creation():
    """Test SPI decoder can be created."""
    decoder = SPIDecoder()
    assert decoder is not None
    assert decoder.name == "SPI"


def test_spi_decoder_required_channels():
    """Test SPI decoder required channels."""
    decoder = SPIDecoder()
    channels = decoder.get_required_channels()
    assert "SCK" in channels
    assert "MOSI" in channels
    assert "MISO" in channels
    assert "CS" in channels


def test_spi_decoder_parameters():
    """Test SPI decoder parameters."""
    decoder = SPIDecoder()
    params = decoder.get_parameters()
    assert "threshold" in params
    assert "cpol" in params
    assert "cpha" in params
    assert "bits_per_word" in params


def test_uart_decoder_creation():
    """Test UART decoder can be created."""
    decoder = UARTDecoder()
    assert decoder is not None
    assert decoder.name == "UART"


def test_uart_decoder_required_channels():
    """Test UART decoder required channels."""
    decoder = UARTDecoder()
    channels = decoder.get_required_channels()
    assert "TX" in channels


def test_uart_decoder_parameters():
    """Test UART decoder parameters."""
    decoder = UARTDecoder()
    params = decoder.get_parameters()
    assert "baud_rate" in params
    assert "data_bits" in params
    assert "parity" in params
    assert "stop_bits" in params


def test_decoder_event_clearing():
    """Test that decoder events can be cleared."""
    decoder = I2CDecoder()
    decoder.events.append("test_event")
    assert len(decoder.events) > 0

    decoder.clear_events()
    assert len(decoder.events) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
