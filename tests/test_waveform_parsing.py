import struct

import numpy as np
import pytest

from siglent import exceptions
from siglent.connection.mock import MockConnection
from siglent.oscilloscope import Oscilloscope
from siglent.waveform import Waveform


@pytest.mark.parametrize(
    "query,response,expected",
    [
        ("C1:VDIV?", "C1:VDIV 2.00E+00V", 2.0),
        ("C1:VDIV?", "VDIV 2.00E+00V", 2.0),
        ("C1:VDIV?", "2.00E+00V", 2.0),
        ("C1:VDIV?", "2.00e+00v", 2.0),
        ("C1:OFST?", "C1:OFST 0.00E+00V", 0.0),
        ("C1:OFST?", "OFST 0.00E+00V", 0.0),
        ("C1:OFST?", "0.00E+00V", 0.0),
        ("TDIV?", "TDIV 1.00E-03S", 1e-3),
        ("TDIV?", "1.00E-03S", 1e-3),
        ("SARA?", "SARA 1.00E+09Sa/s", 1e9),
        ("SARA?", "1.00E+09Sa/s", 1e9),
        ("SARA?", "1.00E+09SA/S", 1e9),
    ],
)
def test_value_parsing_accepts_prefixes_and_units(query, response, expected):
    connection = MockConnection(custom_responses={query: response})
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        parser = {
            "C1:VDIV?": lambda: waveform._get_voltage_scale("C1"),
            "C1:OFST?": lambda: waveform._get_voltage_offset("C1"),
            "TDIV?": waveform._get_timebase,
            "SARA?": waveform._get_sample_rate,
        }[query]

        assert parser() == pytest.approx(expected)


@pytest.mark.parametrize(
    "response",
    [
        "C1:VDIV 2.00E+00V",
        "VDIV 2.00E+00V",
        "2.00E+00V",
        "2.00e+00v",
    ],
)
def test_voltage_scale_parsing_accepts_units(response):
    connection = MockConnection(custom_responses={"C1:VDIV?": response})
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        assert waveform._get_voltage_scale("C1") == pytest.approx(2.0)


@pytest.mark.parametrize(
    "query,expected_exception",
    [
        ("C1:VDIV?", "voltage scale"),
        ("C1:OFST?", "voltage offset"),
        ("TDIV?", "timebase"),
        ("SARA?", "sample rate"),
    ],
)
def test_value_parsing_requires_units(query, expected_exception):
    connection = MockConnection(custom_responses={query: "1.00E+00"})
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        parser = {
            "C1:VDIV?": lambda: waveform._get_voltage_scale("C1"),
            "C1:OFST?": lambda: waveform._get_voltage_offset("C1"),
            "TDIV?": waveform._get_timebase,
            "SARA?": waveform._get_sample_rate,
        }[query]

        with pytest.raises(exceptions.CommandError) as excinfo:
            parser()

        assert expected_exception in str(excinfo.value)


def test_parse_waveform_valid_byte_block():
    payload = bytes([1, 2, 3, 4])
    raw = b"DESC,#14" + payload
    connection = MockConnection()
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        result = waveform._parse_waveform(raw, format="BYTE")
        assert np.array_equal(result, np.array([1, 2, 3, 4], dtype=np.int8))


def test_parse_waveform_valid_word_block():
    payload = struct.pack("<hh", 1, -1)
    raw = b"DESC,#14" + payload
    connection = MockConnection()
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        result = waveform._parse_waveform(raw, format="WORD")
        assert np.array_equal(result, np.array([1, -1], dtype=np.int16))


@pytest.mark.parametrize(
    "raw,expected_message",
    [
        (b"", "empty response"),
        (b"DESC,8000000004", "no #"),
        (b"DESC,#X4", "non-numeric length digit"),
        (b"DESC,#04", "length digit must be positive"),
        (b"DESC,#1", "truncated length field"),
        (b"DESC,#1X", "non-numeric length field"),
        (b"DESC,#15abcd", "declared data length exceeds available data"),
    ],
)
def test_parse_waveform_rejects_invalid_blocks(raw, expected_message):
    connection = MockConnection()
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        with pytest.raises(exceptions.CommandError) as excinfo:
            waveform._parse_waveform(raw, format="BYTE")

        assert expected_message in str(excinfo.value)


def test_parse_waveform_rejects_word_with_odd_length():
    raw = b"DESC,#13abc"
    connection = MockConnection()
    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform

        with pytest.raises(exceptions.CommandError) as excinfo:
            waveform._parse_waveform(raw, format="WORD")

        assert "WORD data length must be even" in str(excinfo.value)


def test_acquire_uses_mock_connection_defaults():
    connection = MockConnection(
        channel_states={1: True},
        voltage_scales={1: 1.0},
        voltage_offsets={1: 0.0},
        waveform_payloads={1: bytes([0, 25, 50, 75])},
        sample_rate=1_000.0,
        timebase=1e-3,
    )

    with Oscilloscope("mock", connection=connection) as scope:
        waveform = scope.waveform.acquire(1)

    assert waveform.sample_rate == pytest.approx(1_000.0)
    assert waveform.timebase == pytest.approx(1e-3)
    assert waveform.record_length == 4
    assert waveform.voltage.tolist() == [0.0, 1.0, 2.0, 3.0]
    assert waveform.time.tolist() == [-0.002, -0.001, 0.0, 0.001]
