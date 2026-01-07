"""Protocol decode framework for analyzing digital communication protocols."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of protocol events."""

    START = "START"
    STOP = "STOP"
    DATA = "DATA"
    ACK = "ACK"
    NACK = "NACK"
    ERROR = "ERROR"
    ADDRESS = "ADDRESS"
    READ = "READ"
    WRITE = "WRITE"
    IDLE = "IDLE"


@dataclass
class DecodedEvent:
    """Represents a decoded protocol event.

    Attributes:
        timestamp: Event timestamp (seconds)
        event_type: Type of event
        data: Event data (bytes, address, etc.)
        description: Human-readable description
        channel: Source channel(s)
        valid: Whether event is valid (no errors)
    """

    timestamp: float
    event_type: EventType
    data: Any
    description: str
    channel: str
    valid: bool = True

    def __repr__(self) -> str:
        """String representation."""
        status = "✓" if self.valid else "✗"
        return f"{status} {self.timestamp:.6f}s [{self.event_type.value}] {self.description}"


class ProtocolDecoder(ABC):
    """Abstract base class for protocol decoders.

    All protocol decoders must inherit from this class and implement
    the decode() method.
    """

    def __init__(self, name: str):
        """Initialize protocol decoder.

        Args:
            name: Decoder name
        """
        self.name = name
        self.events: List[DecodedEvent] = []
        logger.info(f"Protocol decoder initialized: {name}")

    @abstractmethod
    def decode(self, waveforms: Dict[str, Any], **params) -> List[DecodedEvent]:
        """Decode protocol from waveforms.

        Args:
            waveforms: Dictionary of channel_name -> waveform_data
            **params: Protocol-specific parameters

        Returns:
            List of decoded events
        """
        pass

    @abstractmethod
    def get_required_channels(self) -> List[str]:
        """Get list of required channel names.

        Returns:
            List of required channel names (e.g., ['SDA', 'SCL'])
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get decoder parameters with default values.

        Returns:
            Dictionary of parameter_name -> default_value
        """
        pass

    def clear_events(self):
        """Clear all decoded events."""
        self.events.clear()
        logger.debug(f"{self.name}: Events cleared")

    def export_events_csv(self, filename: str):
        """Export events to CSV file.

        Args:
            filename: Output CSV filename
        """
        import csv

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Event Type", "Data", "Description", "Channel", "Valid"])

            for event in self.events:
                writer.writerow(
                    [
                        f"{event.timestamp:.9f}",
                        event.event_type.value,
                        str(event.data),
                        event.description,
                        event.channel,
                        "Yes" if event.valid else "No",
                    ]
                )

        logger.info(f"{self.name}: Exported {len(self.events)} events to {filename}")

    def get_event_summary(self) -> Dict[str, int]:
        """Get summary of event counts by type.

        Returns:
            Dictionary of event_type -> count
        """
        summary = {}
        for event in self.events:
            event_type = event.event_type.value
            summary[event_type] = summary.get(event_type, 0) + 1

        return summary

    def _detect_edge(self, signal: np.ndarray, time: np.ndarray, threshold: float, edge_type: str = "rising") -> List[float]:
        """Detect edges in a digital signal.

        Args:
            signal: Signal voltage array
            time: Time array
            threshold: Voltage threshold for digital high/low
            edge_type: 'rising', 'falling', or 'both'

        Returns:
            List of edge timestamps
        """
        # Convert to digital signal (1 = high, 0 = low)
        digital = (signal > threshold).astype(int)

        # Find edges
        edges = np.diff(digital)

        edge_times = []

        if edge_type in ["rising", "both"]:
            rising_indices = np.where(edges == 1)[0]
            edge_times.extend(time[rising_indices + 1].tolist())

        if edge_type in ["falling", "both"]:
            falling_indices = np.where(edges == -1)[0]
            edge_times.extend(time[falling_indices + 1].tolist())

        return sorted(edge_times)

    def _sample_at_time(self, signal: np.ndarray, time: np.ndarray, sample_time: float, threshold: float) -> bool:
        """Sample digital signal at a specific time.

        Args:
            signal: Signal voltage array
            time: Time array
            sample_time: Time to sample at
            threshold: Voltage threshold

        Returns:
            True if signal is high, False if low
        """
        # Find closest time index
        idx = np.argmin(np.abs(time - sample_time))

        return signal[idx] > threshold

    def _get_bit_at_time(self, signal: np.ndarray, time: np.ndarray, sample_time: float, threshold: float) -> int:
        """Get bit value at a specific time.

        Args:
            signal: Signal voltage array
            time: Time array
            sample_time: Time to sample at
            threshold: Voltage threshold

        Returns:
            1 if high, 0 if low
        """
        return 1 if self._sample_at_time(signal, time, sample_time, threshold) else 0

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.name}Decoder(events={len(self.events)})"
