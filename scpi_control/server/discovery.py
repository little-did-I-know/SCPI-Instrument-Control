"""LAN discovery of SCPI instruments: TCP port scan + *IDN? probe.

FastAPI-free (stdlib + scpi_control only; Python 3.8-clean), mirroring
sessions.py. The scan runs on the caller's thread; instrument session worker
threads are never involved. Callers must pass already-held addresses in
`skip` — Siglent raw sockets allow one client, so probing a live session's
instrument could disturb it.
"""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, FrozenSet, List, Optional

from scpi_control.exceptions import InvalidParameterError
from scpi_control.models import MODEL_REGISTRY, detect_model_from_idn

SCPI_PORT = 5025
MAX_HOSTS = 1024  # /22

_KIND_PREFIXES = (("SPD", "psu"), ("SDP", "psu"), ("SDG", "awg"), ("SDM", "daq"))


def classify(model: str) -> str:
    upper = model.upper()
    if model in MODEL_REGISTRY or upper.startswith("SDS"):
        return "scope"
    for prefix, kind in _KIND_PREFIXES:
        if upper.startswith(prefix):
            return kind
    return "unknown"


_classify = classify  # backward-compat alias; nothing internal should break


def _local_ip() -> Optional[str]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))  # UDP connect: routes, sends nothing
            return sock.getsockname()[0]
        finally:
            sock.close()
    except OSError:
        return None


def _local_network() -> "ipaddress.IPv4Network":
    local = _local_ip()
    if local is None:
        raise InvalidParameterError("could not determine the local network; pass an explicit cidr")
    return ipaddress.ip_network("{0}/24".format(local), strict=False)


def _expand(cidr: Optional[str]) -> List[str]:
    if cidr is None:
        network = _local_network()
    else:
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
        except ValueError:
            raise InvalidParameterError("invalid cidr: {0}".format(cidr))
        if not isinstance(network, ipaddress.IPv4Network):
            raise InvalidParameterError("only IPv4 ranges are supported")
    if network.num_addresses > MAX_HOSTS:
        raise InvalidParameterError("range too wide: {0} (maximum /22)".format(network))
    if network.num_addresses <= 2:
        return [str(network.network_address)]
    return [str(host) for host in network.hosts()]


def _probe(address: str, port: int, connect_timeout: float, probe_timeout: float) -> Optional[Dict[str, object]]:
    try:
        with socket.create_connection((address, port), timeout=connect_timeout) as sock:
            sock.settimeout(probe_timeout)
            sock.sendall(b"*IDN?\n")
            raw = b""
            while not raw.endswith(b"\n") and len(raw) < 4096:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                raw += chunk
    except OSError:
        return None
    idn = raw.decode("ascii", errors="replace").strip()
    parts = [part.strip() for part in idn.split(",")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    manufacturer, model = parts[0], parts[1]
    kind = _classify(model)
    dialect = ""
    if kind == "scope":
        try:
            dialect = detect_model_from_idn(idn).dialect
        except ValueError:
            pass
    return {"address": address, "idn": idn, "manufacturer": manufacturer, "model": model, "dialect": dialect, "kind": kind}


def _sort_key(entry):
    address = str(entry["address"])
    try:
        numeric = int(ipaddress.ip_address(address))
        return (entry["kind"] != "scope", 0, numeric, "")
    except ValueError:
        # hostname-addressed entries (connected sessions) sort after IP literals
        return (entry["kind"] != "scope", 1, 0, address)


def discover(
    cidr: Optional[str] = None,
    port: int = SCPI_PORT,
    connect_timeout: float = 0.4,
    probe_timeout: float = 1.0,
    skip: FrozenSet[str] = frozenset(),
    max_workers: int = 128,
) -> List[Dict[str, object]]:
    own = _local_ip()
    targets = [address for address in _expand(cidr) if address not in skip and address != own]
    if not targets:
        return []
    results: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(targets))) as pool:
        for found in pool.map(lambda address: _probe(address, port, connect_timeout, probe_timeout), targets):
            if found is not None:
                results.append(found)
    results.sort(key=_sort_key)
    return results
