"""An AWG session must be a session in exactly the same way the others are.

The seam is only real if the shared lifecycle -- worker thread, error state,
close timeout, viewer counting -- behaves identically for a third kind that
shares neither the scope's nor the PSU's domain. These assertions are
deliberately the same ones both existing kinds are held to.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import SessionManager


def _awg_connection():
    return MockConnection("mock", awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")


@pytest.fixture
def manager():
    m = SessionManager()
    yield m
    m.close_all()


def test_an_awg_session_connects_and_reports_its_kind(manager):
    session = manager.create("awg", mock=True, kind="awg", _connection=_awg_connection())
    assert session.kind == "awg"
    assert session.state == "connected"
    assert "SDG1032X" in session.idn


def test_an_awg_session_closes_within_its_timeout(manager):
    session = manager.create("awg", mock=True, kind="awg", _connection=_awg_connection())
    session.close(timeout=10.0)
    assert session.state == "closed"


def test_an_awg_session_counts_viewers_like_any_other(manager):
    session = manager.create("awg", mock=True, kind="awg", _connection=_awg_connection())
    assert session.viewers == 0
    unsubscribe = session.subscribe(lambda message: None)
    assert session.viewers == 1
    unsubscribe()
    assert session.viewers == 0
