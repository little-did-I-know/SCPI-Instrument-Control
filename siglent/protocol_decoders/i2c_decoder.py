"""I2C (Inter-Integrated Circuit) protocol decoder."""

import logging
from typing import Any, Dict, List

import numpy as np

from siglent.protocol_decode import DecodedEvent, EventType, ProtocolDecoder

logger = logging.getLogger(__name__)


class I2CDecoder(ProtocolDecoder):
    """I2C protocol decoder.

    Decodes I2C (TWI) communication with SDA (data) and SCL (clock) signals.
    Supports standard and fast mode I2C.
    """

    def __init__(self):
        """Initialize I2C decoder."""
        super().__init__("I2C")

    def get_required_channels(self) -> List[str]:
        """Get required channel names.

        Returns:
            List of required channels
        """
        return ["SDA", "SCL"]

    def get_parameters(self) -> Dict[str, Any]:
        """Get decoder parameters.

        Returns:
            Parameter dictionary
        """
        return {
            "threshold": 1.4,  # Voltage threshold for logic high
            "address_bits": 7,  # 7-bit or 10-bit addressing
        }

    def decode(self, waveforms: Dict[str, Any], **params) -> List[DecodedEvent]:
        """Decode I2C protocol.

        Args:
            waveforms: Dictionary with 'SDA' and 'SCL' waveforms
            **params: threshold (float), address_bits (int)

        Returns:
            List of decoded events
        """
        self.clear_events()

        # Get parameters
        threshold = params.get("threshold", 1.4)
        address_bits = params.get("address_bits", 7)

        # Get waveforms
        if "SDA" not in waveforms or "SCL" not in waveforms:
            logger.error("I2C decode requires SDA and SCL channels")
            return self.events

        sda_waveform = waveforms["SDA"]
        scl_waveform = waveforms["SCL"]

        sda = sda_waveform.voltage
        sda_time = sda_waveform.time
        scl = scl_waveform.voltage
        scl_time = scl_waveform.time

        # Ensure same time base (interpolate if needed)
        if not np.array_equal(sda_time, scl_time):
            scl = np.interp(sda_time, scl_time, scl)
            time = sda_time
        else:
            time = sda_time

        try:
            # Find START and STOP conditions
            start_times = self._find_start_conditions(sda, scl, time, threshold)
            stop_times = self._find_stop_conditions(sda, scl, time, threshold)

            logger.info(f"I2C: Found {len(start_times)} START and {len(stop_times)} STOP conditions")

            # Decode each transaction
            for start_time in start_times:
                # Find corresponding STOP
                stop_time = None
                for st in stop_times:
                    if st > start_time:
                        stop_time = st
                        break

                if stop_time is None:
                    # Incomplete transaction
                    self.events.append(
                        DecodedEvent(
                            timestamp=start_time,
                            event_type=EventType.START,
                            data=None,
                            description="START (incomplete transaction)",
                            channel="SDA/SCL",
                            valid=False,
                        )
                    )
                    continue

                # Add START event
                self.events.append(
                    DecodedEvent(
                        timestamp=start_time,
                        event_type=EventType.START,
                        data=None,
                        description="START",
                        channel="SDA/SCL",
                    )
                )

                # Decode bytes between START and STOP
                self._decode_transaction(sda, scl, time, threshold, start_time, stop_time, address_bits)

                # Add STOP event
                self.events.append(
                    DecodedEvent(
                        timestamp=stop_time,
                        event_type=EventType.STOP,
                        data=None,
                        description="STOP",
                        channel="SDA/SCL",
                    )
                )

            logger.info(f"I2C: Decoded {len(self.events)} events")

        except Exception as e:
            logger.error(f"I2C decode error: {e}")
            self.events.append(
                DecodedEvent(
                    timestamp=0.0,
                    event_type=EventType.ERROR,
                    data=None,
                    description=f"Decode error: {str(e)}",
                    channel="SDA/SCL",
                    valid=False,
                )
            )

        return self.events

    def _find_start_conditions(self, sda: np.ndarray, scl: np.ndarray, time: np.ndarray, threshold: float) -> List[float]:
        """Find I2C START conditions (SDA falling while SCL high).

        Args:
            sda: SDA signal
            scl: SCL signal
            time: Time array
            threshold: Logic threshold

        Returns:
            List of START timestamps
        """
        start_times = []

        # Convert to digital
        sda_digital = (sda > threshold).astype(int)
        scl_digital = (scl > threshold).astype(int)

        # Find SDA falling edges
        sda_edges = np.diff(sda_digital)
        sda_falling = np.where(sda_edges == -1)[0]

        # Check if SCL is high during SDA falling
        for idx in sda_falling:
            if idx + 1 < len(scl_digital) and scl_digital[idx + 1] == 1:
                start_times.append(time[idx + 1])

        return start_times

    def _find_stop_conditions(self, sda: np.ndarray, scl: np.ndarray, time: np.ndarray, threshold: float) -> List[float]:
        """Find I2C STOP conditions (SDA rising while SCL high).

        Args:
            sda: SDA signal
            scl: SCL signal
            time: Time array
            threshold: Logic threshold

        Returns:
            List of STOP timestamps
        """
        stop_times = []

        # Convert to digital
        sda_digital = (sda > threshold).astype(int)
        scl_digital = (scl > threshold).astype(int)

        # Find SDA rising edges
        sda_edges = np.diff(sda_digital)
        sda_rising = np.where(sda_edges == 1)[0]

        # Check if SCL is high during SDA rising
        for idx in sda_rising:
            if idx + 1 < len(scl_digital) and scl_digital[idx + 1] == 1:
                stop_times.append(time[idx + 1])

        return stop_times

    def _decode_transaction(
        self,
        sda: np.ndarray,
        scl: np.ndarray,
        time: np.ndarray,
        threshold: float,
        start_time: float,
        stop_time: float,
        address_bits: int,
    ):
        """Decode I2C transaction between START and STOP.

        Args:
            sda: SDA signal
            scl: SCL signal
            time: Time array
            threshold: Logic threshold
            start_time: Transaction start time
            stop_time: Transaction stop time
            address_bits: 7 or 10 bit addressing
        """
        # Find SCL rising edges (clock sample points)
        scl_edges = self._detect_edge(scl, time, threshold, "rising")

        # Filter edges within transaction
        clock_edges = [t for t in scl_edges if start_time < t < stop_time]

        if len(clock_edges) < 9:  # Minimum: 7 addr bits + 1 R/W + 1 ACK
            return

        # Decode address byte (first 8 bits + ACK)
        address_byte = 0
        for i in range(7):
            if i < len(clock_edges):
                bit = self._get_bit_at_time(sda, time, clock_edges[i], threshold)
                address_byte = (address_byte << 1) | bit

        # Read/Write bit
        if len(clock_edges) > 7:
            rw_bit = self._get_bit_at_time(sda, time, clock_edges[7], threshold)
            rw_str = "READ" if rw_bit else "WRITE"
        else:
            rw_str = "?"

        # ACK/NACK
        if len(clock_edges) > 8:
            ack_bit = self._get_bit_at_time(sda, time, clock_edges[8], threshold)
            ack = "NACK" if ack_bit else "ACK"
            ack_event_type = EventType.NACK if ack_bit else EventType.ACK
        else:
            ack = "?"
            ack_event_type = EventType.ACK

        # Add address event
        self.events.append(
            DecodedEvent(
                timestamp=clock_edges[0],
                event_type=EventType.ADDRESS,
                data={"address": address_byte, "rw": rw_str},
                description=f"Addr: 0x{address_byte:02X} {rw_str}",
                channel="SDA/SCL",
            )
        )

        # Add ACK event
        self.events.append(
            DecodedEvent(
                timestamp=clock_edges[8] if len(clock_edges) > 8 else clock_edges[-1],
                event_type=ack_event_type,
                data=ack,
                description=ack,
                channel="SDA/SCL",
                valid=(ack == "ACK"),
            )
        )

        # Decode data bytes (9 bits each: 8 data + 1 ACK)
        byte_start = 9
        while byte_start + 8 < len(clock_edges):
            data_byte = 0
            for i in range(8):
                bit_idx = byte_start + i
                if bit_idx < len(clock_edges):
                    bit = self._get_bit_at_time(sda, time, clock_edges[bit_idx], threshold)
                    data_byte = (data_byte << 1) | bit

            # Data ACK
            ack_idx = byte_start + 8
            if ack_idx < len(clock_edges):
                ack_bit = self._get_bit_at_time(sda, time, clock_edges[ack_idx], threshold)
                data_ack = "NACK" if ack_bit else "ACK"
                data_ack_type = EventType.NACK if ack_bit else EventType.ACK

                # Add data event
                self.events.append(
                    DecodedEvent(
                        timestamp=clock_edges[byte_start],
                        event_type=EventType.DATA,
                        data=data_byte,
                        description=f"Data: 0x{data_byte:02X} ({chr(data_byte) if 32 <= data_byte < 127 else '?'})",
                        channel="SDA/SCL",
                    )
                )

                # Add ACK event
                self.events.append(
                    DecodedEvent(
                        timestamp=clock_edges[ack_idx],
                        event_type=data_ack_type,
                        data=data_ack,
                        description=data_ack,
                        channel="SDA/SCL",
                        valid=(data_ack == "ACK"),
                    )
                )

            byte_start += 9
