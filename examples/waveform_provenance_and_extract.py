"""Acquisition provenance and the load_waveform() / scpi-extract workflow.

Every saved waveform now embeds a snapshot of the instrument state that
produced it: instrument IDN, per-channel settings (scale, coupling, probe
ratio), trigger configuration, timebase, sample rate, and a UTC timestamp.
This example acquires from a mock oscilloscope (no hardware required), saves
NPZ and CSV, then reads both back with scpi_control.waveform_io.load_waveform()
and prints the instrument model, channel scale, and first few samples --
exactly what scpi-extract does from the command line.

To inspect the saved files yourself:
    scpi-extract provenance_demo.npz
    scpi-extract provenance_demo.csv --json

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
a mock connection, no instrument needed.
"""

from pathlib import Path

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.waveform_io import load_waveform

OUTPUT_DIR = Path.cwd()
NPZ_PATH = OUTPUT_DIR / "provenance_demo.npz"
CSV_PATH = OUTPUT_DIR / "provenance_demo.csv"


def acquire_and_save() -> None:
    """Connect to a mock scope, acquire channel 1 with provenance, and save it."""
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000.0,
        timebase=1e-3,
        waveform_payloads={1: bytes(range(256))},
        # The base mock doesn't answer every legacy-dialect query (e.g. probe
        # ratio); fill in the ones the provenance snapshot reads so channel 1
        # comes back fully populated instead of silently falling back to None.
        custom_responses={"C1:ATTN?": "10", "C1:BWL?": "OFF", "C1:UNIT?": "V"},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        # provenance=True is the default; shown here for clarity.
        waveform = scope.get_waveform(1, provenance=True)
        scope.waveform.save_waveform(waveform, str(NPZ_PATH), format="NPY")
        scope.waveform.save_waveform(waveform, str(CSV_PATH), format="CSV")
        print(f"Saved {NPZ_PATH.name} and {CSV_PATH.name}")
    finally:
        scope.disconnect()


def inspect(path: Path) -> None:
    """Reload a saved waveform and print what its provenance records."""
    loaded = load_waveform(path)
    print(f"\n--- {path.name} ({loaded.source_format}) ---")

    prov = loaded.provenance
    if prov is None:
        print("No provenance recorded (file predates this feature).")
        return

    if prov.instrument is not None:
        print(f"Instrument model: {prov.instrument.model}")

    channel_settings = prov.channels.get(loaded.channel) or prov.channels.get(1)
    if channel_settings is not None:
        print(f"Channel {channel_settings.channel} scale: {channel_settings.voltage_scale} V/div (probe {channel_settings.probe_ratio}x)")

    print(f"Acquired (UTC): {prov.acquired_at}")
    print(f"First 5 samples (V): {loaded.voltage[:5].tolist()}")


def main() -> None:
    acquire_and_save()
    inspect(NPZ_PATH)
    inspect(CSV_PATH)


if __name__ == "__main__":
    main()
