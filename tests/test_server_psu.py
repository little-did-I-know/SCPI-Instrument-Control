"""A PSU session must be a session in exactly the same way a scope session is.

The seam is only real if the shared lifecycle -- worker thread, error state,
close timeout, viewer counting -- behaves identically for a kind that shares
none of the scope's domain. These assertions are deliberately the same ones the
scope session is held to.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import SessionManager


def _psu_connection():
    return MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")


@pytest.fixture
def manager():
    m = SessionManager()
    yield m
    m.close_all()


def test_a_psu_session_connects_and_reports_its_kind(manager):
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    assert session.kind == "psu"
    assert session.state == "connected"
    assert "SPD3303X" in session.idn


def test_a_psu_session_closes_within_its_timeout(manager):
    """Shared lifecycle: the same close path the scope uses."""
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    session.close(timeout=10.0)
    assert session.state == "closed"


def test_a_psu_session_counts_viewers_like_any_other(manager):
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    assert session.viewers == 0
    unsubscribe = session.subscribe(lambda message: None)
    assert session.viewers == 1
    unsubscribe()
    assert session.viewers == 0


def test_the_default_kind_is_scope(manager):
    """The non-breaking guarantee: an existing caller that passes no kind gets
    exactly what it got before."""
    session = manager.create("scope", mock=True)
    assert session.kind == "scope"
    assert session.num_channels == 4
