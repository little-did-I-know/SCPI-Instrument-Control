"""Serial protocol decoding: I2C, SPI and UART.

Shows what each decoder needs before it can run -- which channels it must be
given and which parameters it exposes -- then decodes a captured waveform and
summarises the events found.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Note: the mock synthesizes analogue test signals (sine, square, ramp, ...),
not framed bus traffic, so a mock run demonstrates decoder setup and the
decode call rather than a realistic bus transcript. Running the UART decoder
against the mock's 10 kHz square wave finds no real UART frames: the
captured buffer holds 14 falling edges, and the decoder tries each as a
candidate start bit, but every one is correctly rejected. The first 13 fail
the start-bit check outright (the wave's ~50 us low phase has already
flipped back high by the time the decoder samples 52 us later). The 14th is
the last edge in the buffer, close enough to the end that its start-bit and
eight data-bit sample times fall past the end of the capture; the decoder
now recognises those as unresolvable (the sample-time-to-index lookup is
bounds-checked and returns None past either end of the buffer, rather than
clamping to the nearest end sample) and abandons that candidate frame
instead of fabricating a byte from samples that were never captured. Point
--host at hardware probing a real UART line to see genuine decoded bytes.

Expected output: each decoder's required channels and parameters, then the
UART event summary for the mock's square wave -- deterministically
`UART event summary: {}`, since none of the 14 candidate start bits above
survive both checks. No files are written.
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
