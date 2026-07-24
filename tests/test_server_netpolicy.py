"""Address/port policy for session creation (audit H32)."""

import pytest

from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.netpolicy import DEFAULT_ALLOWED_PORTS, validate_target


def fake_resolver(mapping):
    def resolve(host):
        return mapping[host]

    return resolve


def test_ordinary_lan_address_is_allowed():
    validate_target("192.168.1.50", 5025, resolver=fake_resolver({"192.168.1.50": ["192.168.1.50"]}))


def test_loopback_is_rejected():
    with pytest.raises(InvalidParameterError):
        validate_target("127.0.0.1", 5025, resolver=fake_resolver({"127.0.0.1": ["127.0.0.1"]}))


def test_link_local_and_metadata_are_rejected():
    for address in ("169.254.1.1", "169.254.169.254"):
        with pytest.raises(InvalidParameterError):
            validate_target(address, 5025, resolver=fake_resolver({address: [address]}))


def test_hostname_resolving_to_loopback_is_rejected():
    with pytest.raises(InvalidParameterError):
        validate_target("evil.example.com", 5025, resolver=fake_resolver({"evil.example.com": ["127.0.0.1"]}))


def test_any_resolved_address_failing_policy_rejects_the_whole_target():
    resolver = fake_resolver({"mixed.example.com": ["192.168.1.50", "127.0.0.1"]})
    with pytest.raises(InvalidParameterError):
        validate_target("mixed.example.com", 5025, resolver=resolver)


def test_port_outside_the_allowlist_is_rejected():
    resolver = fake_resolver({"192.168.1.50": ["192.168.1.50"]})
    for port in (22, 6379, 80):
        with pytest.raises(InvalidParameterError):
            validate_target("192.168.1.50", port, resolver=resolver)


def test_extra_ports_can_be_allowed():
    resolver = fake_resolver({"192.168.1.50": ["192.168.1.50"]})
    validate_target("192.168.1.50", 1861, allowed_ports=frozenset({5025, 1861}), resolver=resolver)


def test_unresolvable_host_is_rejected():
    def boom(host):
        raise OSError("nope")

    with pytest.raises(InvalidParameterError):
        validate_target("nowhere.invalid", 5025, resolver=boom)


def test_default_allowlist_is_just_the_scpi_port():
    assert DEFAULT_ALLOWED_PORTS == frozenset({5025})


def test_ipv4_mapped_ipv6_loopback_is_rejected():
    # '::ffff:127.0.0.1' is IPv6's textual encoding of the IPv4 loopback address.
    # ipaddress.IPv6Address.is_loopback does NOT recognize this form (it only
    # matches '::1'), so a naive check would let this bypass the gate.
    address = "::ffff:127.0.0.1"
    with pytest.raises(InvalidParameterError):
        validate_target("evil.example.com", 5025, resolver=fake_resolver({"evil.example.com": [address]}))


def test_ipv6_loopback_is_rejected():
    with pytest.raises(InvalidParameterError):
        validate_target("::1", 5025, resolver=fake_resolver({"::1": ["::1"]}))
