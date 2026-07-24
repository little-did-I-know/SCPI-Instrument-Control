"""SPD3303X has no OVP/OCP subsystem (QS0503X-E01B p.36) -- audit H18.

Until v5.0.0 the capability flags stay True for compatibility, but the call must
not look successful: someone raising voltage on a 12V DUT believing protection is
armed is the failure this warning exists to prevent.
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


def test_setting_ovp_warns_that_nothing_is_armed(spd):
    with pytest.warns(FutureWarning, match="no.*protection subsystem"):
        spd.output1.ovp_level = 12.0


def test_setting_ocp_warns_that_nothing_is_armed(spd):
    with pytest.warns(FutureWarning, match="no.*protection subsystem"):
        spd.output1.ocp_level = 2.5
