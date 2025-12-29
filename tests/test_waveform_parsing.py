import struct

import numpy as np
import pytest

from siglent import exceptions
from siglent.waveform import Waveform


class FakeScope:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.written = []

    def query(self, command: str) -> str:
        return self.responses.get(command, "")

    def write(self, command: str) -> None:
        self.written.append(command)

    def read_raw(self) -> bytes:
        return self.responses.get("raw", b"")


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
    scope = FakeScope({query: response})
    waveform = Waveform(scope)

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
    scope = FakeScope({"C1:VDIV?": response})
    waveform = Waveform(scope)

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
    scope = FakeScope({query: "1.00E+00"})
    waveform = Waveform(scope)

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
    scope = FakeScope({"raw": raw})
    waveform = Waveform(scope)

    result = waveform._parse_waveform(raw, format="BYTE")
    assert np.array_equal(result, np.array([1, 2, 3, 4], dtype=np.int8))


def test_parse_waveform_valid_word_block():
    payload = struct.pack("<hh", 1, -1)
    raw = b"DESC,#14" + payload
    scope = FakeScope({"raw": raw})
    waveform = Waveform(scope)

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
    waveform = Waveform(FakeScope({"raw": raw}))

    with pytest.raises(exceptions.CommandError) as excinfo:
        waveform._parse_waveform(raw, format="BYTE")

    assert expected_message in str(excinfo.value)


def test_parse_waveform_rejects_word_with_odd_length():
    raw = b"DESC,#13abc"
    waveform = Waveform(FakeScope({"raw": raw}))

    with pytest.raises(exceptions.CommandError) as excinfo:
        waveform._parse_waveform(raw, format="WORD")

    assert "WORD data length must be even" in str(excinfo.value)
