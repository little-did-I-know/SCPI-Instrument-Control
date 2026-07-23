"""SI magnitude letters in legacy Siglent responses (RC01020-E01C p.117)."""

import pytest

from scpi_control import exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope


@pytest.fixture
def legacy_scope():
    conn = MockConnection(idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0")
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope


@pytest.mark.parametrize(
    "response,expected",
    [
        ("SARA 500.0kSa", 500_000.0),
        ("SARA 1.00GSa", 1e9),
        ("SARA 2.50MSa", 2.5e6),
        ("SARA 1.00E+03Sa/s", 1000.0),  # scientific form still accepted
    ],
)
def test_sample_rate_accepts_si_magnitude(legacy_scope, response, expected):
    legacy_scope._connection.custom_responses["SARA?"] = response
    assert legacy_scope.waveform._get_sample_rate() == pytest.approx(expected)


def test_unparseable_sample_rate_still_raises(legacy_scope):
    legacy_scope._connection.custom_responses["SARA?"] = "SARA banana"
    with pytest.raises(exceptions.CommandError):
        legacy_scope.waveform._get_sample_rate()
