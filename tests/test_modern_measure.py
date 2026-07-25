"""Modern-dialect :MEASure:SIMPle subsystem (guide p.335-373).

The legacy PAVA? command does not exist on modern instruments -- it appears zero
times in the 855-page modern guide -- so measure() needs a separate wire path.
"""

import pytest

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.measurement import MeasurementType
from scpi_control.scpi_commands import measurement_to_wire
from typing import get_args

MODERN_IDN = "Siglent Technologies,SDS814X HD,MOCK0001,1.0.0.0"


def test_public_wid_maps_to_pwid_not_wid():
    """The trap: modern WID is BURST width (first rising -> last falling edge,
    guide p.345); positive PULSE width is PWID. Our public WID means positive
    pulse width -- it is labelled "Positive Width" in the GUI and the Tektronix
    map already encodes WID -> PWIdth. Mapping WID -> WID returns a
    plausible-looking wrong number on any multi-pulse capture."""
    assert measurement_to_wire("modern", "WID") == "PWID"


def test_negative_width_maps_to_nwid_not_nbwid():
    """NBWID is the negative BURST width (p.345); NWID is the pulse width."""
    assert measurement_to_wire("modern", "NWID") == "NWID"


def test_every_measurement_type_has_a_modern_token():
    for mtype in get_args(MeasurementType):
        token = measurement_to_wire("modern", mtype)
        assert token, "{0} has no modern token".format(mtype)
