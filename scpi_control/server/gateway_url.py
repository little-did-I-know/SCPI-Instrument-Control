"""Record where the gateway can be reached, so `invite` can print a real link.

`scpi-web invite` runs in its own process and has no way to know the gateway
was started with --host 0.0.0.0 --port 9000. Without this the printed link
would say 127.0.0.1 -- unopenable by the person it was sent to -- or the admin
would have to repeat the flags on every invitation, which is the friction this
feature exists to remove.

This file carries no secrets and no security decisions. A damaged one degrades
to "unknown", never to an error.
"""

import json
import socket
from pathlib import Path
from typing import Any, Optional

FILENAME = "gateway.json"
WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "[::]", ""})


def local_address() -> str:
    """This machine's address on the network it would use to reach the world.

    Connecting a UDP socket sends no packets; it only makes the OS choose a
    source address, which is the one a colleague on the same LAN can reach.
    Falls back to loopback when there is no route at all -- an honest answer
    for a machine that is not on a network.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def write_base_url(config_dir: Path, host: str, port: int) -> str:
    """Record and return the externally-reachable base URL."""
    advertised = local_address() if host in WILDCARD_HOSTS else host
    url = "http://{0}:{1}/".format(advertised, port)
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / FILENAME).write_text(json.dumps({"url": url}, indent=2), encoding="utf-8")
    except OSError:
        pass  # a link we cannot cache is not worth failing a server start over
    return url


def read_base_url(config_dir: Path) -> Optional[str]:
    """The last recorded base URL, or None if unknown or unreadable."""
    try:
        payload: Any = json.loads((config_dir / FILENAME).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    url = payload.get("url") if isinstance(payload, dict) else None
    return url if isinstance(url, str) else None
