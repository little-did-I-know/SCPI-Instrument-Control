"""Serial protocol decoding: I2C, SPI and UART.

Shows what each decoder needs before it can run -- which channels it must be
given and which parameters it exposes -- then decodes a captured waveform and
summarises the events found.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Note: the mock synthesizes analogue test signals (sine, square, ramp, ...),
not framed bus traffic, so a mock run demonstrates decoder setup and the
decode call rather than a realistic bus transcript. Running the UART decoder
against the mock's 10 kHz square wave does not find real UART frames -- but
it is not guaranteed to find *zero* events either: the decoder's edge
detector treats every falling edge as a candidate start bit, and by chance
one of the square wave's own periodic edges can line up with the 9600-baud
bit grid closely enough to pass the start/stop checks, producing a single
spurious byte (0x00) that has nothing to do with real bus data -- an
aliasing artefact of feeding a periodic test signal to a decoder tuned for
asynchronous framing, not a decoded transmission. Point --host at hardware
probing a real UART line to see genuine decoded bytes.

Expected output: each decoder's required channels and parameters, then the
UART event summary for the mock's square wave -- deterministically
`UART event summary: {'DATA': 1}`, the single spurious byte described above.
No files are written.
"""

import argparse

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.protocol_decoders import I2CDecoder, SPIDecoder, UARTDecoder
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True, 2: True},
        signals={
            1: SignalSpec(kind="square", frequency=10000.0, amplitude=1.65, offset=1.65),
            2: SignalSpec(kind="square", frequency=5000.0, amplitude=1.65, offset=1.65),
        },
        sample_rate=10e6,
        timebase=1e-3,
    )


def main():
    parser = argparse.ArgumentParser(description="Serial protocol decoding")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    args = parser.parse_args()

    for decoder in (I2CDecoder(), SPIDecoder(), UARTDecoder()):
        name = type(decoder).__name__
        print(f"{name}: channels={decoder.get_required_channels()} parameters={sorted(decoder.get_parameters())}")

    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    try:
        waveform = scope.get_waveform(channel=1)
        decoder = UARTDecoder()
        decoder.decode({"TX": waveform})
        print(f"UART event summary: {decoder.get_event_summary()}")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
