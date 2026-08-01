"""The DAQ reading parser must survive the wire shapes real hardware sends.

Backend review 2026-07-31, finding High-8. Two independent defects, both
invisible against the old mock because it answered R? with the same bare CSV
it answered READ? with:

1. `R?` wraps its payload in an IEEE 488.2 definite-length block (34970A/34972A
   Command Reference p.40, worked example p.41: `R? 2` ->
   `#231+2.87536000E-04,+3.18131400E-03`). Splitting that on commas makes
   float("#231+2.87536000E-04") raise, and the old parser swallowed the failure
   at debug level -- silently dropping the FIRST reading of every batch. `R?`
   erases readings on the instrument, so the data is unrecoverable.
2. An overload reads back as +-9.9E+37 (p.251, 266, 275, 839, 905, 946, 1128:
   "the instrument gives an overload indication: +-OVLD from the front panel or
   +-9.9E+37 from the remote interface"). float() accepts it happily, so an
   impossible value entered the record as a real measurement.

DATA:REMove? / FETCh? / READ? are bare CSV (p.334-335, 16-17, 49-50), so the
block header is OPTIONAL -- the parser handles both.
"""

import math

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.data_logger import DataLogger

DAQ_IDN = "Agilent Technologies,34970A,MY12345678,1.0"

# The manual's own worked example, p.41.
MANUAL_R_RESPONSE = "#231+2.87536000E-04,+3.18131400E-03"


def _logger(**kwargs):
    conn = MockConnection(daq_mode=True, daq_idn=DAQ_IDN, **kwargs)
    dl = DataLogger("mock", connection=conn)
    dl.connect()
    return dl, conn


class TestDefiniteLengthBlock:
    def test_manual_example_yields_both_readings(self):
        dl, _ = _logger()
        readings = dl._parse_readings(MANUAL_R_RESPONSE)
        assert [r.value for r in readings] == [pytest.approx(2.87536e-04), pytest.approx(3.181314e-03)]

    def test_bare_csv_still_parses(self):
        # FETCh?/READ?/DATA:REMove? are documented bare CSV -- header is optional.
        dl, _ = _logger()
        readings = dl._parse_readings("+4.27150000E+02,+1.32130000E+03")
        assert [r.value for r in readings] == [pytest.approx(427.15), pytest.approx(1321.3)]

    def test_mock_r_query_is_block_wrapped_and_read_is_not(self):
        # Wire-level pin: this is the mock half of the fix. If the mock ever
        # goes back to answering R? bare, this fails even though the parser
        # would still "work" -- that is the point.
        dl, conn = _logger(daq_readings="1.234,2.345,3.456")
        assert conn.query("R? 3").startswith("#")
        assert not conn.query("READ?").startswith("#")

    def test_read_and_remove_keeps_every_reading(self):
        # End-to-end through the real command path (R? {max_readings}).
        dl, _ = _logger(daq_readings="1.234,2.345,3.456")
        readings = dl.read_and_remove(3)
        assert [r.value for r in readings] == [pytest.approx(1.234), pytest.approx(2.345), pytest.approx(3.456)]


class TestOverloadSentinel:
    @pytest.mark.parametrize("token", ["+9.9E+37", "-9.9E+37", "+9.90000000E+37"])
    def test_overload_is_marked_not_recorded_as_a_value(self, token):
        dl, _ = _logger()
        readings = dl._parse_readings(f"+1.00000000E+00,{token},+2.00000000E+00")
        assert len(readings) == 3
        assert readings[1].overload is True
        assert math.isnan(readings[1].value)
        # neighbours untouched
        assert readings[0].overload is False
        assert readings[2].value == pytest.approx(2.0)

    def test_ordinary_large_value_is_not_treated_as_overload(self):
        dl, _ = _logger()
        (reading,) = dl._parse_readings("+1.00000000E+30")
        assert reading.overload is False
        assert reading.value == pytest.approx(1e30)


class TestUnparseableTokens:
    def test_unparseable_token_is_visible_not_swallowed(self, caplog):
        dl, _ = _logger()
        with caplog.at_level("WARNING"):
            readings = dl._parse_readings("+1.00000000E+00,NOT_A_NUMBER")
        assert [r.value for r in readings] == [pytest.approx(1.0)]
        assert any("NOT_A_NUMBER" in rec.message for rec in caplog.records)
