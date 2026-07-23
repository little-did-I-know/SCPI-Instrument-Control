"""SDG key-value response parsing (PG02-E05B p.27-28)."""

import pytest

from scpi_control.awg_scpi_commands import parse_key_value_response


def test_parses_documented_bswv_response():
    fields = parse_key_value_response("C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,PHSE,0")
    assert fields["WVTP"] == "SINE"
    assert fields["FRQ"] == "1000HZ"
    assert fields["AMP"] == "1V"


def test_parses_documented_outp_response():
    # PG02-E05B p.27: C1:OUTP?  ->  C1:OUTP ON,LOAD,HZ,PLRT,NOR
    fields = parse_key_value_response("C1:OUTP ON,LOAD,HZ,PLRT,NOR")
    assert fields["STATE"] == "ON"
    assert fields["LOAD"] == "HZ"
    assert fields["PLRT"] == "NOR"


def test_header_is_always_stripped():
    """CHDR cannot be disabled on SDG1000X/2000X, so the header is never optional."""
    assert "C1" not in parse_key_value_response("C1:BSWV WVTP,SINE")


def test_garbage_raises():
    with pytest.raises(ValueError):
        parse_key_value_response("")
