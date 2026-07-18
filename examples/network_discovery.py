"""Discover SCPI instruments on the local network.

Scans a range of addresses, probes each for a SCPI *IDN? response, and prints
what it finds. This example scans a documentation-only TEST-NET range so it
returns quickly with no results in most environments; change `cidr` (or pass
cidr=None to auto-scan your local /24) to find real instruments.

Requirements: SCPI-Instrument-Control (core install, no hardware)
"""

from scpi_control.server.discovery import discover


def main():
    print("=" * 60)
    print("Network instrument discovery")
    print("=" * 60)

    # A small TEST-NET-1 range (RFC 5737): fast and hostless, for a safe demo.
    # For real use: discover(cidr=None) auto-scans your local subnet, or pass a
    # CIDR like discover(cidr="192.168.1.0/24").
    cidr = "192.0.2.0/30"
    print(f"Scanning {cidr} ...")
    found = discover(cidr=cidr, connect_timeout=0.3, probe_timeout=0.5)

    if not found:
        print("No instruments found in this range.")
    else:
        print(f"Found {len(found)} instrument(s):")
        for entry in found:
            print(f"  {entry}")

    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
