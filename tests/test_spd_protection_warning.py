"""Siglent SPD PSUs have no citable SCPI protection subsystem -- audit H18 + backend review 2026-07-31 finding High-3.

SPD3303X: QS0503X-E01B p.36 lists the full command set; no protection commands (v5.0.0).
SPD1305X/SPD1168X: no SPD1000X programming manual exists in docs/; the generic
SOURce:VOLTage:PROTection fallback they previously used is not documented for these
models anywhere we can cite, and the corpus gate requires citations. Front-panel
OVP/OCP exists on the SPD1000X series, so if a programming manual documenting
protection commands is added to docs/ later, implement them with citations and
flip has_ovp/has_ocp back. Until then: honesty gate. Believing OVP is armed when
the firmware discarded the command is the failure this guard prevents.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.power_supply import PowerSupply


@pytest.fixture(params=["SPD3303X", "SPD1305X", "SPD1168X"])
def spd(request):
    conn = MockConnection(psu_mode=True, psu_idn=f"Siglent Technologies,{request.param},SPD123456,1.0")
    psu = PowerSupply(connection=conn, host="mock")
    psu.connect()
    return psu


def test_setting_ovp_raises_not_implemented(spd):
    with pytest.raises(NotImplementedError, match="Over-voltage protection not supported"):
        spd.output1.ovp_level = 12.0


def test_getting_ovp_raises_not_implemented(spd):
    with pytest.raises(NotImplementedError, match="Over-voltage protection not supported"):
        _ = spd.output1.ovp_level


def test_setting_ocp_raises_not_implemented(spd):
    with pytest.raises(NotImplementedError, match="Over-current protection not supported"):
        spd.output1.ocp_level = 2.5


def test_getting_ocp_raises_not_implemented(spd):
    with pytest.raises(NotImplementedError, match="Over-current protection not supported"):
        _ = spd.output1.ocp_level
