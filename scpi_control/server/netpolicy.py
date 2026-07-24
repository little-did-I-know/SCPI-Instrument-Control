"""Address/port policy for outbound instrument connections.

The gateway will happily open a TCP socket to whatever a caller names, so an
authenticated user could otherwise use it as an internal port scanner. Resolve
first, then judge every resolved address -- checking the hostname and connecting
by name would let 'evil.example.com -> 127.0.0.1' through.

IPv6 addresses can encode an IPv4 address inside them (e.g. '::ffff:127.0.0.1',
an IPv4-mapped address). ipaddress.IPv6Address.is_loopback does NOT consider
that form loopback -- it only matches '::1' -- so a naive check would let a
mapped loopback/link-local/metadata address sail through the gate. We unwrap
`ipv4_mapped` before applying the policy so the mapped IPv4 address is judged
on its own terms.
"""

import ipaddress
import socket
from typing import Callable, Iterable, Optional, Union

from scpi_control.exceptions import InvalidParameterError

DEFAULT_ALLOWED_PORTS = frozenset({5025})

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def _default_resolver(host: str) -> Iterable[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def _reject(address: str, reason: str) -> None:
    raise InvalidParameterError("refusing to connect to {0}: {1}".format(address, reason))


def _effective_address(ip: IPAddress) -> IPAddress:
    """Unwrap an IPv4-mapped IPv6 address so it is judged as the IPv4 address it encodes."""
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped if mapped is not None else ip


def validate_target(address: str, port: int, allowed_ports: Optional[frozenset] = None, resolver: Optional[Callable] = None) -> None:
    ports = DEFAULT_ALLOWED_PORTS if allowed_ports is None else allowed_ports
    if port not in ports:
        _reject(address, "port {0} is not in the allowed set {1}".format(port, sorted(ports)))

    resolve = resolver if resolver is not None else _default_resolver
    try:
        resolved = list(resolve(address))
    except OSError as exc:
        _reject(address, "cannot resolve ({0})".format(exc))
        return  # pragma: no cover - _reject always raises; unreachable, keeps type checkers happy

    if not resolved:
        _reject(address, "resolves to no addresses")

    for candidate in resolved:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            _reject(address, "resolved to an unusable address {0!r}".format(candidate))
            continue  # pragma: no cover - unreachable, _reject always raises

        effective = _effective_address(ip)
        if effective.is_loopback or effective.is_link_local or effective.is_multicast or effective.is_reserved or effective.is_unspecified:
            _reject(address, "resolves to the disallowed address {0}".format(ip))
