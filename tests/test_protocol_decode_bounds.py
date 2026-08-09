"""Regression tests for out-of-range sample handling in protocol decoders.

`ProtocolDecoder._sample_at_time` used an unbounded `np.argmin` to resolve a
sample time to a buffer index, so a `sample_time` outside the captured
window silently clamped to whichever end sample was nearest instead of
signalling "this moment was never captured". That let truncated frames
(a byte that starts near the end of a capture) decode into phantom events
built from clamped end-of-buffer samples. See AUDIT.md 2026-08-09 (L1).
"""

import numpy as np
import pytest

from scpi_control.protocol_decoders import UARTDecoder
from scpi_control.waveform import WaveformData


@pytest.fixture
def decoder():
    """A concrete ProtocolDecoder to exercise the shared sampling helpers."""
    return UARTDecoder()


def test_sample_at_time_returns_none_past_buffer_end(decoder):
    """A sample_time after the last captured time returns None, not a clamped value."""
    time = np.linspace(0.0, 0.001, 100)
    signal = np.zeros_like(time)  # low throughout

    result = decoder._sample_at_time(signal, time, sample_time=1.0, threshold=1.4)

    assert result is None


def test_sample_at_time_returns_none_before_buffer_start(decoder):
    """A sample_time before the first captured time returns None, not a clamped value."""
    time = np.linspace(0.0, 0.001, 100)
    signal = np.zeros_like(time)  # low throughout

    result = decoder._sample_at_time(signal, time, sample_time=-0.005, threshold=1.4)

    assert result is None


def test_sample_at_time_in_range_still_resolves_correctly(decoder):
    """In-range probes still resolve to the correct digital level."""
    time = np.linspace(0.0, 0.001, 100)
    signal = np.where(time < 0.0005, 3.3, 0.0)  # high for first half, low for second half

    assert decoder._sample_at_time(signal, time, sample_time=0.0001, threshold=1.4) is True
    assert decoder._sample_at_time(signal, time, sample_time=0.0009, threshold=1.4) is False


def test_sample_at_time_boundaries_are_valid_not_rejected(decoder):
    """Exactly time[0] and time[-1] must remain valid probes (no off-by-one)."""
    time = np.linspace(0.0, 0.001, 100)
    signal = np.zeros_like(time)
    signal[0] = 3.3  # high only at the very first sample
    signal[-1] = 3.3  # high only at the very last sample

    assert decoder._sample_at_time(signal, time, sample_time=time[0], threshold=1.4) is True
    assert decoder._sample_at_time(signal, time, sample_time=time[-1], threshold=1.4) is True


def test_sample_at_time_empty_buffer_does_not_crash(decoder):
    """An empty time array is out of range everywhere -- it must not raise."""
    time = np.array([])
    signal = np.array([])

    result = decoder._sample_at_time(signal, time, sample_time=0.0, threshold=1.4)

    assert result is None


def test_get_bit_at_time_propagates_none(decoder):
    """_get_bit_at_time must propagate None rather than coercing it to 0."""
    time = np.linspace(0.0, 0.001, 100)
    signal = np.zeros_like(time)

    result = decoder._get_bit_at_time(signal, time, sample_time=1.0, threshold=1.4)

    assert result is None


def test_get_bit_at_time_in_range_still_returns_ints(decoder):
    """In-range probes still return plain 0/1 ints (not None, not bool)."""
    time = np.linspace(0.0, 0.001, 100)
    signal = np.where(time < 0.0005, 3.3, 0.0)

    assert decoder._get_bit_at_time(signal, time, sample_time=0.0001, threshold=1.4) == 1
    assert decoder._get_bit_at_time(signal, time, sample_time=0.0009, threshold=1.4) == 0


def test_uart_truncated_frame_at_buffer_end_decodes_no_phantom_byte():
    """A frame whose start bit falls past the buffer end must not decode a phantom byte.

    Regression for AUDIT.md 2026-08-09 L1: a UART capture ending shortly after
    a falling edge -- too soon for a full bit period to elapse -- used to have
    its start-bit and data-bit sample times clamp to the buffer's last (low)
    sample, which happened to satisfy the start-bit check and decode eight
    zero bits into a spurious 0x00 DATA event. The frame was never actually
    captured; the fix must abandon it instead of fabricating it.
    """
    baud_rate = 9600
    bit_period = 1.0 / baud_rate  # ~104.17 us

    # Buffer: idle high until 100us, then a falling edge, then low until the
    # buffer ends at 150us -- less than half a bit period after the edge, so
    # the start-bit sample time (edge + bit_period/2 = ~152.08us) falls past
    # the end of the capture, and every data-bit sample time falls further
    # still.
    time = np.linspace(0.0, 150e-6, 1500)
    voltage = np.where(time < 100e-6, 3.3, 0.0)

    waveform = WaveformData(time=time, voltage=voltage, channel=1)

    decoder = UARTDecoder()
    decoder.decode({"TX": waveform}, baud_rate=baud_rate)

    summary = decoder.get_event_summary()
    assert "DATA" not in summary, f"expected no phantom byte, got summary={summary}, events={decoder.events}"
