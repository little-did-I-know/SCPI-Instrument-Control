"""Tektronix measurement badges: how repeat measurements reuse a slot.

A Tektronix MSO exposes measurements as numbered "badges" that must be
allocated before they can be read. scpi_control pools them: the first
measurement of a given type allocates a badge, repeats reuse it with a single
query, and disconnecting removes the badges it created without touching any
of the badges the user configured on the front panel.

Requirements: none by default -- runs against a built-in mock MSO58. Pass
--host <ip> to drive a real Tektronix MSO on the network.

Expected output: measured values plus, for the mock run only, the SCPI
traffic that allocated and removed the badge (a real-hardware run has no
`connection` object to inspect, so those two trace lines are skipped). No
files are written.
"""

import argparse

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection

MSO58_IDN = "TEKTRONIX,MSO58,MOCK0300,CF:91.1CT FV:2.0"


def _connect(host):
    if host != "mock":
        return None
    return MockConnection("mock", idn=MSO58_IDN, channel_states={i: True for i in range(1, 9)})


def main():
    parser = argparse.ArgumentParser(description="Tektronix measurement badge pooling")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    args = parser.parse_args()

    connection = _connect(args.host)
    scope = Oscilloscope(args.host, connection=connection)
    scope.connect()
    try:
        print(f"Connected to: {scope.identify()}")

        print(f"CH1 Vpp (first call, allocates a badge): {scope.measurement.measure_vpp(1):.3f} V")
        print(f"CH1 Vpp (second call, reuses the badge): {scope.measurement.measure_vpp(1):.3f} V")
        print(f"CH2 Vpp (different channel, its own slot): {scope.measurement.measure_vpp(2):.3f} V")
    finally:
        scope.disconnect()

    if connection is not None:
        allocated = [w for w in connection.writes if "ADDNew" in w]
        removed = [w for w in connection.writes if "DELete" in w]
        print(f"Badges allocated: {allocated}")
        print(f"Badges removed on disconnect: {removed}")


if __name__ == "__main__":
    main()
