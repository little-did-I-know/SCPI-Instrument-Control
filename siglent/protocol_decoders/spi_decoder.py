"""SPI (Serial Peripheral Interface) protocol decoder."""

import logging
from typing import Any, Dict, List

import numpy as np

from siglent.protocol_decode import DecodedEvent, EventType, ProtocolDecoder

logger = logging.getLogger(__name__)


class SPIDecoder(ProtocolDecoder):
    """SPI protocol decoder.

    Decodes SPI communication with MOSI, MISO, SCK, and CS signals.
    Supports various SPI modes (0-3) and bit orders.
    """

    def __init__(self):
        """Initialize SPI decoder."""
        super().__init__("SPI")

    def get_required_channels(self) -> List[str]:
        """Get required channel names.

        Returns:
            List of required channels
        """
        return ["SCK", "MOSI", "MISO", "CS"]

    def get_parameters(self) -> Dict[str, Any]:
        """Get decoder parameters.

        Returns:
            Parameter dictionary
        """
        return {
            "threshold": 1.4,  # Voltage threshold
            "cpol": 0,  # Clock polarity (0 or 1)
            "cpha": 0,  # Clock phase (0 or 1)
            "bits_per_word": 8,  # Bits per word
            "bit_order": "MSB",  # 'MSB' or 'LSB'
            "cs_active_low": True,  # CS active level
        }

    def decode(self, waveforms: Dict[str, Any], **params) -> List[DecodedEvent]:
        """Decode SPI protocol.

        Args:
            waveforms: Dictionary with 'SCK', 'MOSI', 'MISO', 'CS' waveforms
            **params: threshold, cpol, cpha, bits_per_word, bit_order, cs_active_low

        Returns:
            List of decoded events
        """
        self.clear_events()

        # Get parameters
        threshold = params.get("threshold", 1.4)
        cpol = params.get("cpol", 0)
        cpha = params.get("cpha", 0)
        bits_per_word = params.get("bits_per_word", 8)
        bit_order = params.get("bit_order", "MSB")
        cs_active_low = params.get("cs_active_low", True)

        # Get waveforms
        required = ["SCK", "MOSI", "CS"]
        for ch in required:
            if ch not in waveforms:
                logger.error(f"SPI decode requires {ch} channel")
                return self.events

        sck_waveform = waveforms["SCK"]
        mosi_waveform = waveforms["MOSI"]
        cs_waveform = waveforms["CS"]
        miso_waveform = waveforms.get("MISO")  # MISO is optional

        sck = sck_waveform.voltage
        sck_time = sck_waveform.time
        mosi = mosi_waveform.voltage
        mosi_time = mosi_waveform.time
        cs = cs_waveform.voltage
        cs_time = cs_waveform.time

        # Interpolate to common time base
        time = sck_time
        if not np.array_equal(mosi_time, sck_time):
            mosi = np.interp(time, mosi_time, mosi)
        if not np.array_equal(cs_time, sck_time):
            cs = np.interp(time, cs_time, cs)

        if miso_waveform is not None:
            miso = miso_waveform.voltage
            miso_time = miso_waveform.time
            if not np.array_equal(miso_time, sck_time):
                miso = np.interp(time, miso_time, miso)
        else:
            miso = None

        try:
            # Find CS active periods (transactions)
            cs_periods = self._find_cs_active_periods(cs, time, threshold, cs_active_low)

            logger.info(f"SPI: Found {len(cs_periods)} transactions")

            # Determine clock edge for sampling
            if cpha == 0:
                # Sample on first edge (leading edge)
                sample_edge = "falling" if cpol == 1 else "rising"
            else:
                # Sample on second edge (trailing edge)
                sample_edge = "rising" if cpol == 1 else "falling"

            # Decode each transaction
            for start_time, end_time in cs_periods:
                # Find clock edges within transaction
                clock_edges = self._detect_edge(sck, time, threshold, sample_edge)
                transaction_edges = [t for t in clock_edges if start_time < t < end_time]

                if len(transaction_edges) < bits_per_word:
                    # Not enough clock cycles
                    self.events.append(
                        DecodedEvent(
                            timestamp=start_time,
                            event_type=EventType.ERROR,
                            data=None,
                            description=f"Incomplete transaction ({len(transaction_edges)} bits)",
                            channel="SPI",
                            valid=False,
                        )
                    )
                    continue

                # Decode words
                word_count = len(transaction_edges) // bits_per_word

                for word_idx in range(word_count):
                    word_start_edge = word_idx * bits_per_word
                    word_end_edge = word_start_edge + bits_per_word

                    # Decode MOSI
                    mosi_word = self._decode_word(
                        mosi,
                        time,
                        transaction_edges[word_start_edge:word_end_edge],
                        threshold,
                        bit_order,
                    )

                    # Decode MISO (if available)
                    if miso is not None:
                        miso_word = self._decode_word(
                            miso,
                            time,
                            transaction_edges[word_start_edge:word_end_edge],
                            threshold,
                            bit_order,
                        )
                        data_str = f"MOSI: 0x{mosi_word:02X}, MISO: 0x{miso_word:02X}"
                        data_dict = {"mosi": mosi_word, "miso": miso_word}
                    else:
                        data_str = f"MOSI: 0x{mosi_word:02X}"
                        data_dict = {"mosi": mosi_word}

                    # Add data event
                    self.events.append(
                        DecodedEvent(
                            timestamp=transaction_edges[word_start_edge],
                            event_type=EventType.DATA,
                            data=data_dict,
                            description=data_str,
                            channel="SPI",
                        )
                    )

            logger.info(f"SPI: Decoded {len(self.events)} events")

        except Exception as e:
            logger.error(f"SPI decode error: {e}")
            self.events.append(
                DecodedEvent(
                    timestamp=0.0,
                    event_type=EventType.ERROR,
                    data=None,
                    description=f"Decode error: {str(e)}",
                    channel="SPI",
                    valid=False,
                )
            )

        return self.events

    def _find_cs_active_periods(self, cs: np.ndarray, time: np.ndarray, threshold: float, cs_active_low: bool) -> List[tuple]:
        """Find CS active periods (transactions).

        Args:
            cs: CS signal
            time: Time array
            threshold: Logic threshold
            cs_active_low: Whether CS is active low

        Returns:
            List of (start_time, end_time) tuples
        """
        # Convert to digital
        cs_digital = (cs > threshold).astype(int)

        # Invert if active low
        if cs_active_low:
            cs_digital = 1 - cs_digital

        # Find transitions
        cs_edges = np.diff(cs_digital)

        # Find rising edges (CS activation)
        cs_active = np.where(cs_edges == 1)[0]
        # Find falling edges (CS deactivation)
        cs_inactive = np.where(cs_edges == -1)[0]

        periods = []

        for start_idx in cs_active:
            # Find corresponding end
            end_indices = cs_inactive[cs_inactive > start_idx]
            if len(end_indices) > 0:
                end_idx = end_indices[0]
                periods.append((time[start_idx + 1], time[end_idx + 1]))

        return periods

    def _decode_word(
        self,
        signal: np.ndarray,
        time: np.ndarray,
        clock_edges: List[float],
        threshold: float,
        bit_order: str,
    ) -> int:
        """Decode a word from signal at clock edges.

        Args:
            signal: Signal to decode
            time: Time array
            clock_edges: List of clock edge timestamps
            threshold: Logic threshold
            bit_order: 'MSB' or 'LSB'

        Returns:
            Decoded word value
        """
        word = 0

        for i, edge_time in enumerate(clock_edges):
            bit = self._get_bit_at_time(signal, time, edge_time, threshold)

            if bit_order == "MSB":
                # MSB first
                word = (word << 1) | bit
            else:
                # LSB first
                word = word | (bit << i)

        return word
