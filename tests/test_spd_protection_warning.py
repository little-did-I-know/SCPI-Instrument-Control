"""SPD3303X has no OVP/OCP subsystem (QS0503X-E01B p.36) -- audit H18.

As of v5.0.0, `has_ovp`/`has_ocp` are False for the SPD3303X/-E and ovp_level/
ocp_level raise NotImplementedError instead of silently discarding the command:
someone raising voltage on a 12V DUT believing protection is armed is the
failure this guard exists to prevent.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.power_supply import PowerSupply


@pytest.fixture
def spd():
    conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
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
