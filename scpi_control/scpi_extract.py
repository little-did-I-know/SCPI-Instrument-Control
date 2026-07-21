"""scpi-extract: inspect and export saved waveform files from the command line.

Examples:
    scpi-extract capture.npz                 # provenance + metadata summary
    scpi-extract capture.mat --csv out.csv   # dump raw time/voltage rows
    scpi-extract capture.h5 --json           # machine-readable metadata
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Optional

from scpi_control.waveform_io import LoadedWaveform, load_waveform


def _info_lines(loaded: LoadedWaveform) -> List[str]:
    lines = [
        f"File:        {loaded.source_path} ({loaded.source_format})",
        f"Channel:     {loaded.channel}",
        f"Samples:     {len(loaded.voltage)}",
        f"Sample rate: {loaded.sample_rate}",
    ]
    prov = loaded.provenance
    if prov is None:
        lines.append("Provenance:  (none — file predates provenance capture)")
    else:
        if prov.instrument is not None:
            lines.append(f"Instrument:  {prov.instrument.manufacturer} {prov.instrument.model} (serial {prov.instrument.serial}, firmware {prov.instrument.firmware})")
        lines.append(f"Acquired:    {prov.acquired_at}")
        lines.append(f"Address:     {prov.address}  Dialect: {prov.dialect}  Library: v{prov.library_version}")
        for n, ch in sorted(prov.channels.items()):
            lines.append(f"Channel {n}:   scale={ch.voltage_scale} V/div offset={ch.voltage_offset} V coupling={ch.coupling} probe={ch.probe_ratio}x bw={ch.bandwidth_limit}")
        if prov.trigger is not None:
            lines.append(f"Trigger:     {prov.trigger.trigger_type} {prov.trigger.slope} on {prov.trigger.source} @ {prov.trigger.level} V ({prov.trigger.mode})")
        if prov.timebase is not None:
            lines.append(f"Timebase:    {prov.timebase} s/div")
    if loaded.metadata:
        lines.append("Metadata:")
        for key, value in sorted(loaded.metadata.items()):
            lines.append(f"  {key}: {value}")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="scpi-extract", description="Extract raw data and acquisition provenance from waveform files saved by SCPI Instrument Control.")
    parser.add_argument("file", type=Path, help="waveform file (.npz/.csv/.mat/.h5/.hdf5)")
    parser.add_argument("--format", choices=["NPZ", "CSV", "MAT", "HDF5"], help="override format auto-detection")
    parser.add_argument("--info", action="store_true", help="print a provenance/metadata summary (default when no other flag is given)")
    parser.add_argument("--csv", metavar="OUT", type=Path, help="write raw time,voltage rows to OUT")
    parser.add_argument("--json", action="store_true", help="print metadata + provenance as JSON")
    args = parser.parse_args(argv)

    try:
        loaded = load_waveform(args.file, format=args.format)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    acted = False
    if args.csv is not None:
        with open(args.csv, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Time (s)", "Voltage (V)"])
            for t, v in zip(loaded.time, loaded.voltage):
                writer.writerow([t, v])
        print(f"Wrote {len(loaded.voltage)} samples to {args.csv}")
        acted = True
    if args.json:
        payload = {
            "file": str(loaded.source_path),
            "format": loaded.source_format,
            "channel": loaded.channel,
            "samples": len(loaded.voltage),
            "sample_rate": loaded.sample_rate,
            "metadata": loaded.metadata,
            "provenance": loaded.provenance.to_dict() if loaded.provenance is not None else None,
        }
        print(json.dumps(payload, indent=2, default=str))
        acted = True
    if args.info or not acted:
        print("\n".join(_info_lines(loaded)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
