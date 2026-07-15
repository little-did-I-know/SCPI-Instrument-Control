"""SCPI dialect auto-detection and manual override.

The library speaks two Siglent command sets: "legacy" (SDS1000X-E era,
e.g. C1:VDIV 500mV) and "modern" (SDS800X HD era, e.g. :CHANnel1:SCALe 0.5).
The dialect is auto-detected from *IDN? at connect; pass dialect= to force
one when detection guesses wrong. This example uses mock connections so it
runs without hardware.

Requirements: SCPI-Instrument-Control (core install)
"""

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import SiglentTimeoutError

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


def show(scope: Oscilloscope, label: str) -> None:
    scope.connect()
    try:
        print(f"{label}: model={scope.device_info.get('model')}, detected dialect={scope.dialect}")
        scope.timebase = 1e-3  # same API call regardless of dialect
        print(f"  timebase set to {scope.timebase} s/div via the {scope.dialect} command set")
    finally:
        scope.disconnect()


def main() -> None:
    # Auto-detection from *IDN?
    show(Oscilloscope("mock", connection=MockConnection("mock", idn=LEGACY_IDN)), "Legacy scope (auto)")
    show(Oscilloscope("mock", connection=MockConnection("mock", idn=MODERN_IDN)), "Modern scope (auto)")

    # Manual override: dialect= exists for the case where the model registry
    # misidentifies real hardware from *IDN? and you need to force the wire
    # protocol the instrument *actually* speaks. Forcing a dialect the
    # instrument does NOT speak is a misuse - and our mock is faithful enough
    # to prove it: it answers only the real protocol for its *IDN?, so
    # forcing "modern" onto a legacy-speaking instrument here fails exactly
    # like it would on real mismatched hardware (a timeout, not a crash).
    forced = Oscilloscope("mock", connection=MockConnection("mock", idn=LEGACY_IDN), dialect="modern")
    forced.connect()
    try:
        print(f"Legacy IDN, dialect forced to modern: model={forced.device_info.get('model')}, dialect={forced.dialect}")
        try:
            forced.timebase = 1e-3
            print(f"  timebase set to {forced.timebase} s/div via the {forced.dialect} command set")
        except SiglentTimeoutError:
            print("  (expected) a modern-dialect query against a legacy-speaking instrument timed out")
            print("  -- only override dialect to match what the real instrument speaks")
    finally:
        forced.disconnect()
    # On real hardware, override with the dialect the instrument actually
    # speaks: Oscilloscope("192.168.1.100", dialect="modern")


if __name__ == "__main__":
    main()
