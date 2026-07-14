"""LAN discovery core. Loopback-only; no fastapi dependency."""

import socket
import threading

import pytest

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.discovery import _classify, _expand, _probe, discover

LEGACY_IDN_LINE = b"Siglent Technologies,SDS1104X-E,FAKE0001,1.0.0.0\n"


class FakeScpiServer:
    """Threaded loopback server answering *IDN? once per connection.

    response=None accepts the connection but never answers (silent device).
    Tracks how many connections it accepted (used to prove skip behavior).
    """

    def __init__(self, response=LEGACY_IDN_LINE):
        self.response = response
        self.connections = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.connections += 1
            with conn:
                try:
                    conn.settimeout(1.0)
                    data = conn.recv(1024)
                    if data.strip() == b"*IDN?" and self.response is not None:
                        conn.sendall(self.response)
                except OSError:
                    pass

    def close(self):
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=2)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class TestClassify:
    @pytest.mark.parametrize(
        "model,kind",
        [
            ("SDS824X HD", "scope"),
            ("SDS1104X-E", "scope"),
            ("SDS9999X", "scope"),  # SDS prefix, not in registry
            ("SPD3303X", "psu"),
            ("SDP5081X", "psu"),
            ("SDG2042X", "awg"),
            ("SDM3055", "daq"),
            ("DP832", "unknown"),
        ],
    )
    def test_kinds(self, model, kind):
        assert _classify(model) == kind


class TestExpand:
    def test_single_host_cidr(self):
        assert _expand("127.0.0.1/32") == ["127.0.0.1"]

    def test_malformed_cidr_raises(self):
        with pytest.raises(InvalidParameterError):
            _expand("not-a-network")

    def test_too_wide_cidr_raises(self):
        with pytest.raises(InvalidParameterError):
            _expand("10.0.0.0/8")

    def test_ipv6_raises(self):
        with pytest.raises(InvalidParameterError):
            _expand("::1/128")

    def test_slash24_yields_254_hosts(self):
        hosts = _expand("192.0.2.0/24")
        assert len(hosts) == 254
        assert hosts[0] == "192.0.2.1" and hosts[-1] == "192.0.2.254"


class TestProbe:
    def test_probe_parses_idn(self):
        with FakeScpiServer() as server:
            result = _probe("127.0.0.1", server.port, 0.5, 1.0)
        assert result == {
            "address": "127.0.0.1",
            "idn": "Siglent Technologies,SDS1104X-E,FAKE0001,1.0.0.0",
            "manufacturer": "Siglent Technologies",
            "model": "SDS1104X-E",
            "dialect": "legacy",
            "kind": "scope",
        }

    def test_probe_garbage_banner_returns_none(self):
        with FakeScpiServer(response=b"no commas here\n") as server:
            assert _probe("127.0.0.1", server.port, 0.5, 1.0) is None

    def test_probe_silent_device_returns_none(self):
        with FakeScpiServer(response=None) as server:
            assert _probe("127.0.0.1", server.port, 0.5, 0.3) is None

    def test_probe_refused_port_returns_none(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        unused_port = sock.getsockname()[1]
        sock.close()
        assert _probe("127.0.0.1", unused_port, 0.3, 0.3) is None


class TestDiscover:
    def test_finds_fake_instrument_on_loopback(self):
        with FakeScpiServer() as server:
            results = discover(cidr="127.0.0.1/32", port=server.port, connect_timeout=0.5)
        assert len(results) == 1
        assert results[0]["model"] == "SDS1104X-E"
        assert results[0]["kind"] == "scope"

    def test_skip_prevents_probe(self):
        with FakeScpiServer() as server:
            results = discover(cidr="127.0.0.1/32", port=server.port, skip=frozenset({"127.0.0.1"}))
            assert results == []
            assert server.connections == 0


def test_sort_key_orders_numerically_scopes_first():
    from scpi_control.server.discovery import _sort_key

    entries = [
        {"address": "10.0.0.10", "kind": "psu"},
        {"address": "10.0.0.9", "kind": "scope"},
        {"address": "10.0.0.10", "kind": "scope"},
        {"address": "10.0.0.2", "kind": "scope"},
    ]
    ordered = sorted(entries, key=_sort_key)
    assert [(e["address"], e["kind"]) for e in ordered] == [
        ("10.0.0.2", "scope"),
        ("10.0.0.9", "scope"),
        ("10.0.0.10", "scope"),
        ("10.0.0.10", "psu"),
    ]


def test_sort_key_tolerates_hostnames():
    from scpi_control.server.discovery import _sort_key

    entries = [
        {"address": "bench-scope.local", "kind": "scope"},
        {"address": "10.0.0.2", "kind": "scope"},
    ]
    ordered = sorted(entries, key=_sort_key)
    assert [e["address"] for e in ordered] == ["10.0.0.2", "bench-scope.local"]
