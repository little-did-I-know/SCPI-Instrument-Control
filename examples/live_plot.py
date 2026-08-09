"""Live plotting example for Siglent oscilloscope.

This script demonstrates real-time waveform acquisition and plotting
using matplotlib animation.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. matplotlib is a
core dependency, no extra install needed.

Expected output: against --host mock there is no display, so --frames
waveform updates (default: 20) are rendered headlessly -- each one printed
to the console as it happens -- and the final frame is saved to
'live_plot.png' in the current directory. Against a real host, an
interactive plot window updates every 200ms with the live Channel 1
waveform, bounded to --frames updates (repeat=False), until the window is
closed or the frame budget runs out; no files are written in that case.
"""

import argparse
import time

import matplotlib.animation as animation
import matplotlib.pyplot as plt

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec

# Channel colors (matching oscilloscope theme)
CHANNEL_COLORS = {
    1: "#FFD700",  # Yellow
    2: "#00CED1",  # Cyan
    3: "#FF1493",  # Magenta
    4: "#00FF00",  # Green
}


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


class LivePlotter:
    """Live waveform plotter."""

    def __init__(self, scope, channels=[1]):
        """Initialize live plotter.

        Args:
            scope: Connected Oscilloscope instance
            channels: List of channel numbers to plot (default: [1])
        """
        self.scope = scope
        self.channels = channels

        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.ax.set_xlabel("Time (µs)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.set_title("Live Waveform Display")
        self.ax.grid(True, alpha=0.3)

        # Store line objects
        self.lines = {}
        for ch in channels:
            color = CHANNEL_COLORS.get(ch, "white")
            (line,) = self.ax.plot([], [], color=color, linewidth=1.0, label=f"CH{ch}")
            self.lines[ch] = line

        self.ax.legend(loc="upper right")

    def update(self, frame):
        """Animation update function.

        Args:
            frame: Frame number (used only for the progress message)

        Returns:
            List of line objects
        """
        for ch in self.channels:
            try:
                # Acquire waveform
                waveform = self.scope.get_waveform(ch)

                # Update line data
                self.lines[ch].set_data(waveform.time * 1e6, waveform.voltage)

            except Exception as e:
                print(f"Error acquiring channel {ch}: {e}")

        # Autoscale
        self.ax.relim()
        self.ax.autoscale_view()

        print(f"  frame {frame + 1} rendered")
        return list(self.lines.values())

    def start(self, host, frames, interval=200):
        """Drive up to `frames` updates. Caller is responsible for showing or
        saving the figure afterward.

        Against --host mock there is no display and no event loop to drive
        matplotlib's Timer-based animation -- plt.show() is a no-op under
        the Agg backend, and a FuncAnimation left to its own devices renders
        at most one frame from a single savefig()-triggered draw. So the
        mock path calls update() directly in a bounded loop -- the exact
        function a live animation would call -- to genuinely render every
        frame headlessly. Against real hardware, a FuncAnimation drives
        update() on a timer via the GUI event loop the caller's plt.show()
        starts, bounded to `frames` renders (repeat=False).

        Args:
            host: the --host value driving this run ('mock' or a real host)
            frames: number of frames to render before stopping
            interval: update interval in milliseconds, real hardware only (default: 200)

        Returns:
            The FuncAnimation instance for a real host, or None for mock (a
            reference must be kept alive until plt.show() returns, or it is
            garbage-collected and the animation silently stops).
        """
        if host == "mock":
            for frame in range(frames):
                self.update(frame)
            return None
        anim = animation.FuncAnimation(self.fig, self.update, frames=frames, interval=interval, blit=False, cache_frame_data=False, repeat=False)
        return anim


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    parser.add_argument("--frames", type=int, default=20, help="Number of animation frames to render before exiting (default: 20)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))

    try:
        # Connect to oscilloscope
        print(f"Connecting to oscilloscope at {args.host}...")
        scope.connect()
        print(f"Connected to: {scope.device_info['model']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0

        # Set trigger
        scope.trigger.mode = "AUTO"
        scope.trigger.source = "C1"
        scope.trigger.level = 0.0

        # Start acquisition
        scope.run()
        print("Acquisition running...")

        # Real hardware needs a moment for the signal to settle after
        # starting acquisition before the first capture is meaningful; the
        # mock has no such settling behavior to model, so skip the wait
        # there to keep the headless run fast.
        if args.host != "mock":
            time.sleep(0.5)

        # Start live plotting
        print(f"\nStarting live plot ({args.frames} frames)...")
        if args.host != "mock":
            print("Close the plot window to stop.")

        plotter = LivePlotter(scope, channels=[1])
        # anim must stay referenced until plt.show() returns -- if it's
        # garbage-collected first, the animation silently stops (mock's
        # explicit loop above doesn't need it; start() returns None there).
        anim = plotter.start(args.host, args.frames, interval=200)  # Update every 200ms

        if args.host == "mock":
            plt.savefig("live_plot.png")
        else:
            plt.show()

    finally:
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
