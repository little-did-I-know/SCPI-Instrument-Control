"""UART (Universal Asynchronous Receiver/Transmitter) protocol decoder."""

import logging
from typing import Any, Dict, List

import numpy as np

from siglent.protocol_decode import DecodedEvent, EventType, ProtocolDecoder

logger = logging.getLogger(__name__)


class UARTDecoder(ProtocolDecoder):
    """UART protocol decoder.

    Decodes asynchronous serial communication (UART/RS-232).
    Supports various baud rates, data bits, parity, and stop bits.
    """

    def __init__(self):
        """Initialize UART decoder."""
        super().__init__("UART")

    def get_required_channels(self) -> List[str]:
        """Get required channel names.

        Returns:
            List of required channels
        """
        return ["TX"]  # RX is optional

    def get_parameters(self) -> Dict[str, Any]:
        """Get decoder parameters.

        Returns:
            Parameter dictionary
        """
        return {
            "baud_rate": 9600,  # Baud rate in bps
            "data_bits": 8,  # Data bits (5-9)
            "parity": "none",  # 'none', 'even', 'odd', 'mark', 'space'
            "stop_bits": 1,  # Stop bits (1, 1.5, 2)
            "threshold": 1.4,  # Voltage threshold
            "idle_high": True,  # Idle state is high
        }

    def decode(self, waveforms: Dict[str, Any], **params) -> List[DecodedEvent]:
        """Decode UART protocol.

        Args:
            waveforms: Dictionary with 'TX' and optionally 'RX' waveforms
            **params: baud_rate, data_bits, parity, stop_bits, threshold, idle_high

        Returns:
            List of decoded events
        """
        self.clear_events()

        # Get parameters
        baud_rate = params.get("baud_rate", 9600)
        data_bits = params.get("data_bits", 8)
        parity = params.get("parity", "none")
        stop_bits = params.get("stop_bits", 1)
        threshold = params.get("threshold", 1.4)
        idle_high = params.get("idle_high", True)

        # Get waveforms
        if "TX" not in waveforms:
            logger.error("UART decode requires TX channel")
            return self.events

        tx_waveform = waveforms["TX"]
        rx_waveform = waveforms.get("RX")

        try:
            # Decode TX channel
            tx_events = self._decode_channel(tx_waveform, "TX", baud_rate, data_bits, parity, stop_bits, threshold, idle_high)
            self.events.extend(tx_events)

            # Decode RX channel if available
            if rx_waveform is not None:
                rx_events = self._decode_channel(rx_waveform, "RX", baud_rate, data_bits, parity, stop_bits, threshold, idle_high)
                self.events.extend(rx_events)

            # Sort events by timestamp
            self.events.sort(key=lambda e: e.timestamp)

            logger.info(f"UART: Decoded {len(self.events)} events")

        except Exception as e:
            logger.error(f"UART decode error: {e}")
            self.events.append(
                DecodedEvent(
                    timestamp=0.0,
                    event_type=EventType.ERROR,
                    data=None,
                    description=f"Decode error: {str(e)}",
                    channel="UART",
                    valid=False,
                )
            )

        return self.events

    def _decode_channel(
        self,
        waveform,
        channel_name: str,
        baud_rate: int,
        data_bits: int,
        parity: str,
        stop_bits: float,
        threshold: float,
        idle_high: bool,
    ) -> List[DecodedEvent]:
        """Decode a single UART channel.

        Args:
            waveform: Waveform data
            channel_name: Channel name ('TX' or 'RX')
            baud_rate: Baud rate
            data_bits: Number of data bits
            parity: Parity type
            stop_bits: Number of stop bits
            threshold: Logic threshold
            idle_high: Whether idle is high

        Returns:
            List of decoded events
        """
        events = []

        signal = waveform.voltage
        time = waveform.time

        # Calculate bit period
        bit_period = 1.0 / baud_rate

        # Find start bits (falling edges if idle high, rising if idle low)
        edge_type = "falling" if idle_high else "rising"
        start_edges = self._detect_edge(signal, time, threshold, edge_type)

        logger.info(f"UART {channel_name}: Found {len(start_edges)} potential start bits")

        for start_time in start_edges:
            try:
                # Sample in the middle of each bit period
                sample_offset = bit_period / 2

                # Verify start bit (should be low if idle high)
                start_bit_time = start_time + sample_offset
                start_bit = self._get_bit_at_time(signal, time, start_bit_time, threshold)

                expected_start = 0 if idle_high else 1
                if start_bit != expected_start:
                    # Not a valid start bit
                    continue

                # Decode data bits
                data_value = 0
                bit_times = []

                for bit_idx in range(data_bits):
                    bit_time = start_time + (bit_idx + 1) * bit_period + sample_offset
                    bit_val = self._get_bit_at_time(signal, time, bit_time, threshold)
                    bit_times.append(bit_time)

                    # LSB first
                    data_value |= bit_val << bit_idx

                # Check parity (if enabled)
                parity_valid = True
                if parity != "none":
                    parity_bit_time = start_time + (data_bits + 1) * bit_period + sample_offset
                    parity_bit = self._get_bit_at_time(signal, time, parity_bit_time, threshold)

                    if parity == "even":
                        expected_parity = bin(data_value).count("1") % 2
                    elif parity == "odd":
                        expected_parity = 1 - (bin(data_value).count("1") % 2)
                    elif parity == "mark":
                        expected_parity = 1
                    elif parity == "space":
                        expected_parity = 0
                    else:
                        expected_parity = parity_bit

                    parity_valid = parity_bit == expected_parity

                # Format data as character if printable
                if 32 <= data_value < 127:
                    data_str = f"0x{data_value:02X} '{chr(data_value)}'"
                else:
                    data_str = f"0x{data_value:02X}"

                # Add data event
                events.append(
                    DecodedEvent(
                        timestamp=start_time,
                        event_type=EventType.DATA,
                        data=data_value,
                        description=f"{channel_name}: {data_str}",
                        channel=channel_name,
                        valid=parity_valid,
                    )
                )

                # Add parity error if invalid
                if not parity_valid:
                    events.append(
                        DecodedEvent(
                            timestamp=start_time,
                            event_type=EventType.ERROR,
                            data=None,
                            description=f"{channel_name}: Parity error",
                            channel=channel_name,
                            valid=False,
                        )
                    )

            except Exception as e:
                logger.warning(f"UART {channel_name}: Failed to decode byte at {start_time:.6f}s: {e}")
                continue

        return events
