"""Result model for a frequency response sweep.

A point carries its diagnostics, not just its answer: a reader who cannot see
how many cycles were in the window or what scale the capture used has no way to
judge whether a number is trustworthy.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from scpi_control.provenance import AcquisitionProvenance


@dataclass(frozen=True)
class ResponsePoint:
    """One measured frequency, with the geometry it was measured under."""

    frequency_hz: float
    gain_db: Optional[float] = None
    phase_deg: Optional[float] = None
    reference_vpp: float = 0.0
    response_vpp: float = 0.0
    cycles_in_window: float = 0.0
    samples_per_cycle: float = 0.0
    volts_per_div: Optional[float] = None
    excluded_reason: Optional[str] = None

    def __post_init__(self) -> None:
        # The pairing is the honesty guarantee: a missing gain always says why,
        # and a present gain never carries a contradicting excuse.
        if (self.gain_db is None) != (self.excluded_reason is not None):
            raise ValueError(f"excluded_reason must be set exactly when gain_db is None (gain_db={self.gain_db!r}, excluded_reason={self.excluded_reason!r})")


@dataclass(frozen=True)
class SweepSettings:
    """What the caller asked for, kept so a result can explain itself."""

    reference_channel: int
    response_channel: int
    awg_channel: int
    frequencies: Tuple[float, ...]
    amplitude_vpp: float
    settle_s: float
    autorange: bool


@dataclass
class FrequencyResponse:
    """The points a sweep measured, plus the settings and provenance behind them."""

    settings: SweepSettings
    points: List[ResponsePoint] = field(default_factory=list)
    provenance: Optional[AcquisitionProvenance] = None

    def usable(self) -> List[ResponsePoint]:
        """Points that carry a gain."""
        return [point for point in self.points if point.gain_db is not None]

    def cutoff_hz(self, level_db: float = -3.0) -> Optional[float]:
        """Frequency where the response first falls `level_db` below its peak.

        The peak of the sweep stands in for the passband, which assumes the
        passband lies inside the swept range. Interpolation is linear in
        log-frequency against dB, so the answer can be no more precise than the
        point spacing. Returns None if the response never crosses.
        """
        usable = self.usable()
        if len(usable) < 2:
            return None
        threshold = max(point.gain_db for point in usable) + level_db
        for earlier, later in zip(usable, usable[1:]):
            if earlier.gain_db >= threshold > later.gain_db:
                span = later.gain_db - earlier.gain_db
                if span == 0:
                    return earlier.frequency_hz
                fraction = (threshold - earlier.gain_db) / span
                log_earlier = math.log10(earlier.frequency_hz)
                log_later = math.log10(later.frequency_hz)
                return 10.0 ** (log_earlier + fraction * (log_later - log_earlier))
        return None
