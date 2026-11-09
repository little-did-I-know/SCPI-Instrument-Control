"""scpi: one command-line entry point for SCPI Instrument Control.

Examples:
    scpi demo                                  # mock scope + synthesized signal, no hardware
    scpi discover                              # list instruments on the local /24
    scpi idn 192.168.1.207                     # print *IDN?
    scpi screenshot 192.168.1.207 -o scope.png
    scpi capture 192.168.1.207 --channels 1,2 -o run.npz
    scpi capture --mock --channels 1 -o run.csv

Heavy dependencies (matplotlib, Pillow, h5py, the mock/server packages) are
imported lazily, inside the subcommand that needs them.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

MOCK_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
DEFAULT_TIMEOUT = 5.0
MAX_CHANNEL = 8
ASCII_WIDTH = 72
ASCII_HEIGHT = 15
DEMO_SAMPLE_RATE = 20e6
DEMO_TIMEBASE = 500e-6
DEMO_SIGNALS = ("sine", "square", "triangle", "ramp")
WAVEFORM_EXTENSIONS = (".npz", ".csv", ".mat", ".h5", ".hdf5")
SCREENSHOT_EXTENSIONS = (".png", ".bmp")

_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:%\[\]-]*$")


class UsageError(Exception):
    """Bad command-line input; reported with exit status 2."""


# ---- validation ------------------------------------------------------------


def _check_host(args: argparse.Namespace) -> None:
    if args.mock:
        return
    if args.host is None:
        raise UsageError("a host is required (or pass --mock)")
    if not _HOST_RE.match(args.host):
        raise UsageError("invalid host: {0!r}".format(args.host))


def _parse_channels(text: str) -> List[int]:
    channels: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part.isdigit() or not 1 <= int(part) <= MAX_CHANNEL:
            raise UsageError("invalid channel list {0!r}: use comma-separated numbers 1-{1}".format(text, MAX_CHANNEL))
        channels.append(int(part))
    if len(set(channels)) != len(channels):
        raise UsageError("invalid channel list {0!r}: duplicate channel".format(text))
    return channels


def _check_output(path: Path, allowed: Tuple[str, ...]) -> None:
    if path.suffix.lower() not in allowed:
        raise UsageError("unsupported output extension {0!r}; use one of {1}".format(path.suffix, ", ".join(allowed)))
    if path.is_dir():
        raise UsageError("output path is a directory: {0}".format(path))
    if not path.parent.is_dir():
        raise UsageError("output directory does not exist: {0}".format(path.parent))


# ---- scope plumbing --------------------------------------------------------


def _build_mock(channels: Sequence[int], signal: str = "sine", amplitude: float = 1.0, frequency: float = 1000.0) -> Any:
    from scpi_control.connection import MockConnection
    from scpi_control.signal_synth import SignalSpec

    signals = {ch: SignalSpec(kind=signal, frequency=frequency * ch, amplitude=amplitude, noise_rms=0.02 * amplitude, seed=ch) for ch in channels}
    return MockConnection(
        "mock",
        idn=MOCK_IDN,
        channel_states={n: n in channels for n in range(1, 5)},
        trigger_status=["Stop"],
        sample_rate=DEMO_SAMPLE_RATE,
        timebase=DEMO_TIMEBASE,
        signals=signals,
    )


def _open_scope(args: argparse.Namespace, channels: Sequence[int] = (1,), **mock_kwargs: Any) -> Any:
    from scpi_control.oscilloscope import Oscilloscope

    if args.mock:
        scope = Oscilloscope("mock", connection=_build_mock(channels, **mock_kwargs))
    else:
        scope = Oscilloscope(args.host, timeout=args.timeout)
    scope.connect()
    return scope


def _close(scope: Any) -> None:
    try:
        scope.disconnect()
    except Exception:  # best-effort teardown; never mask the real result
        pass


# ---- plotting --------------------------------------------------------------


def _ascii_plot(voltage: Any, width: int = ASCII_WIDTH, height: int = ASCII_HEIGHT) -> str:
    import numpy as np

    idx = np.linspace(0, len(voltage) - 1, width).astype(int)
    samples = np.asarray(voltage)[idx]
    lo, hi = float(samples.min()), float(samples.max())
    span = (hi - lo) or 1.0
    rows = np.round((hi - samples) / span * (height - 1)).astype(int)
    grid = [[" "] * width for _ in range(height)]
    for col, row in enumerate(rows):
        grid[row][col] = "*"
    lines = []
    for r, cells in enumerate(grid):
        label = "{0:+8.3f} V".format(hi) if r == 0 else ("{0:+8.3f} V".format(lo) if r == height - 1 else " " * 10)
        lines.append("{0} |{1}".format(label, "".join(cells)))
    return "\n".join(lines)


def _save_plot_png(waveform: Any, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3))
    try:
        ax.plot(waveform.time * 1e3, waveform.voltage)
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Voltage (V)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(str(path), format="png")
    finally:
        plt.close(fig)


# ---- commands --------------------------------------------------------------


def _cmd_idn(args: argparse.Namespace) -> int:
    scope = _open_scope(args)
    try:
        print(scope.identify())
    finally:
        _close(scope)
    return 0


def _cmd_capture(args: argparse.Namespace) -> int:
    out = Path(args.output)
    channels = args.channel_list
    scope = _open_scope(args, channels)
    try:
        written = []
        for ch in channels:
            wf = scope.get_waveform(ch)
            target = out if len(channels) == 1 else out.with_name("{0}_ch{1}{2}".format(out.stem, ch, out.suffix))
            scope.waveform.save_waveform(wf, str(target))
            written.append((ch, target, len(wf.voltage)))
    finally:
        _close(scope)
    for ch, target, count in written:
        print("CH{0}: {1} samples -> {2}".format(ch, count, target))
    return 0


def _cmd_screenshot(args: argparse.Namespace) -> int:
    out = Path(args.output) if args.output else Path("screenshot_{0}.png".format(datetime.now().strftime("%Y%m%d_%H%M%S")))
    as_png = out.suffix.lower() == ".png"
    if as_png:
        try:
            import PIL.Image  # noqa: F401
        except ImportError:
            raise RuntimeError("PNG output needs Pillow (pip install Pillow); use -o file.bmp for the raw screenshot")
    scope = _open_scope(args)
    try:
        data = scope.screen_capture.capture_screenshot()
    finally:
        _close(scope)
    if as_png:
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.open(io.BytesIO(data)).save(buffer, format="PNG")
        data = buffer.getvalue()
    out.write_bytes(data)
    print("Saved screenshot to {0} ({1} bytes)".format(out, len(data)))
    return 0


def _cmd_discover(args: argparse.Namespace) -> int:
    from scpi_control.server import discovery

    found = discovery.discover(cidr=args.cidr, connect_timeout=args.timeout, probe_timeout=args.timeout * 2)
    if not found:
        print("No instruments found.")
        return 0
    for entry in found:
        print("{0:<16} {1:<7} {2}".format(entry["address"], entry["kind"], entry["idn"]))
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    scope = _open_scope(args, (1,), signal=args.signal, amplitude=args.amplitude, frequency=args.frequency)
    try:
        wf = scope.get_waveform(1)
        freq = scope.measurement.measure_frequency(1)
        if args.output:
            if Path(args.output).suffix.lower() == ".png":
                _save_plot_png(wf, Path(args.output))
            else:
                scope.waveform.save_waveform(wf, args.output)
    finally:
        _close(scope)
    print("Mock scope: {0}  ({1} {2:g} Hz, {3:g} V amplitude)".format(MOCK_IDN.split(",")[1], args.signal, args.frequency, args.amplitude))
    print("Samples {0}".format(len(wf.voltage)))
    print("Vpp  {0:.3f} V".format(float(wf.voltage.max() - wf.voltage.min())))
    print("Freq {0:.2f} Hz".format(float(freq)))
    print()
    print(_ascii_plot(wf.voltage))
    if args.output:
        print("\nSaved to {0}".format(args.output))
    return 0


# ---- parser ----------------------------------------------------------------


def _add_target(p: argparse.ArgumentParser) -> None:
    p.add_argument("host", nargs="?", help="instrument IP address or hostname")
    p.add_argument("--mock", action="store_true", help="use the built-in mock instrument instead of hardware")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="connection timeout in seconds (default: %(default)s)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scpi", description="SCPI Instrument Control command-line tool.")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("demo", help="mock scope with a synthesized signal; no hardware needed")
    p.add_argument("--signal", choices=DEMO_SIGNALS, default="sine")
    p.add_argument("--frequency", type=float, default=1000.0, help="signal frequency in Hz (default: %(default)s)")
    p.add_argument("--amplitude", type=float, default=1.0, help="signal amplitude in volts (default: %(default)s)")
    p.add_argument("-o", "--output", help="save the capture (.npz/.csv/...) or a plot (.png)")
    p.set_defaults(func=_cmd_demo, mock=True, host=None, timeout=DEFAULT_TIMEOUT)

    p = sub.add_parser("discover", help="list SCPI instruments on the LAN")
    p.add_argument("--cidr", help="range to scan, e.g. 192.168.1.0/24 (default: local /24)")
    p.add_argument("--timeout", type=float, default=0.4, help="per-host connect timeout in seconds (default: %(default)s)")
    p.set_defaults(func=_cmd_discover)

    p = sub.add_parser("idn", help="print the instrument's *IDN? reply")
    _add_target(p)
    p.set_defaults(func=_cmd_idn)

    p = sub.add_parser("screenshot", help="save the scope display as PNG or BMP")
    _add_target(p)
    p.add_argument("-o", "--output", help="output file, .png or .bmp (default: screenshot_<timestamp>.png)")
    p.set_defaults(func=_cmd_screenshot)

    p = sub.add_parser("capture", help="acquire channel waveforms and save them")
    _add_target(p)
    p.add_argument("--channels", default="1", help="comma-separated channel numbers (default: %(default)s)")
    p.add_argument("-o", "--output", required=True, help="output file (.npz/.csv/.mat/.h5); with several channels, _chN is added to the name")
    p.set_defaults(func=_cmd_capture)
    return parser


def _validate(args: argparse.Namespace) -> None:
    if args.command in ("idn", "screenshot", "capture"):
        _check_host(args)
    if args.command == "capture":
        args.channel_list = _parse_channels(args.channels)
        _check_output(Path(args.output), WAVEFORM_EXTENSIONS)
    elif args.command == "screenshot" and args.output:
        _check_output(Path(args.output), SCREENSHOT_EXTENSIONS)
    elif args.command == "demo" and args.output:
        _check_output(Path(args.output), WAVEFORM_EXTENSIONS + (".png",))
    if args.command == "discover" and args.timeout <= 0:
        raise UsageError("--timeout must be positive")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_usage(sys.stderr)
        print("scpi: error: a command is required", file=sys.stderr)
        return 2
    try:
        _validate(args)
        return args.func(args)
    except UsageError as exc:
        print("scpi: error: {0}".format(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
