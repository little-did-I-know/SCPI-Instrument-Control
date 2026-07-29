"""What revocation means: tokens, streams and owned sessions, in one place."""

import asyncio

from scpi_control.server.auth import TokenStore
from scpi_control.server.revocation import StreamRegistry, identity_is_live, revoke_identity


class _FakeSession:
    def __init__(self, owner):
        self.owner = owner


class _FakeManager:
    def __init__(self, sessions):
        self._sessions = sessions

    def list(self):
        return list(self._sessions)


def test_identity_is_live_tracks_the_store(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("bob")
    assert identity_is_live(store, "bob") is True
    store.revoke("bob")
    assert identity_is_live(store, "bob") is False


def test_identity_is_live_sees_another_process(tmp_path):
    # This is the whole reason the backstop exists: `scpi-web token revoke`
    # runs in a different process, so nothing in this one gets an event.
    path = str(tmp_path / "tokens.json")
    gateway = TokenStore(path)
    gateway.mint("bob")
    TokenStore(path).revoke("bob")
    assert identity_is_live(gateway, "bob") is False


def test_identity_is_live_is_false_for_an_empty_identity(tmp_path):
    # A stream whose identity is "" never went through AuthMiddleware. It
    # cannot happen today, and if it ever does it must not be treated as live.
    store = TokenStore(str(tmp_path / "tokens.json"))
    assert identity_is_live(store, "") is False


def test_the_registry_sets_every_event_for_one_identity():
    registry = StreamRegistry()
    first, second, other = asyncio.Event(), asyncio.Event(), asyncio.Event()
    registry.add("bob", first)
    registry.add("bob", second)
    registry.add("robin", other)
    assert registry.revoke("bob") == 2
    assert first.is_set() and second.is_set()
    assert not other.is_set()


def test_unregistering_stops_a_closed_stream_being_signalled():
    registry = StreamRegistry()
    event = asyncio.Event()
    unregister = registry.add("bob", event)
    unregister()
    assert registry.revoke("bob") == 0
    assert not event.is_set()


def test_unregistering_twice_is_harmless():
    registry = StreamRegistry()
    unregister = registry.add("bob", asyncio.Event())
    unregister()
    unregister()
    assert registry.count("bob") == 0


def test_revoking_an_identity_reports_what_it_did(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("bob")
    store.mint("bob")
    registry = StreamRegistry()
    registry.add("bob", asyncio.Event())
    manager = _FakeManager([_FakeSession("bob"), _FakeSession("robin"), _FakeSession("bob")])

    result = revoke_identity(store, manager, registry, "bob")

    assert result == {"devices": 2, "streams": 1, "sessions": 2}
    assert store.names() == []


def test_revoking_releases_only_that_identitys_sessions(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("bob")
    mine, theirs = _FakeSession("bob"), _FakeSession("robin")
    revoke_identity(store, _FakeManager([mine, theirs]), StreamRegistry(), "bob")
    assert mine.owner == ""
    assert theirs.owner == "robin"


def test_revoking_an_unknown_identity_reports_none_and_changes_nothing(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("robin")
    session = _FakeSession("robin")
    assert revoke_identity(store, _FakeManager([session]), StreamRegistry(), "ghost") is None
    assert session.owner == "robin"
    assert store.names() == ["robin"]
