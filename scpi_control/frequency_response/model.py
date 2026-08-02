"""Result model for a frequency response sweep.

A point carries its diagnostics, not just its answer: a reader who cannot see
how many cycles were in the window or what scale the capture used has no way to
judge whether a number is trustworthy.
"""

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from scpi_control.provenance import AcquisitionProvenance


@dataclass(frozen=True)
class ResponsePoint:
    """One measured frequency, with the geometry it was measured under."""

    frequency_hz: float
    gain_db: Optional[float] = None
    phase_deg: Optional[float] = None
    reference_vpp: Optional[float] = None
    response_vpp: Optional[float] = None
    cycles_in_window: Optional[float] = None
    samples_per_cycle: Optional[float] = None
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


_CSV_COLUMNS = ("frequency_hz", "gain_db", "phase_deg", "reference_vpp", "response_vpp", "cycles_in_window", "samples_per_cycle", "volts_per_div", "excluded_reason")


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

        `usable()` is sorted by frequency before walking it: `points` (and
        `frequencies=`) is a documented public input with no ordering
        requirement, and walking it in caller-supplied order silently answers
        a different question for an unordered sweep. Sorting means the two
        points bracketing the crossing may not be adjacent in `self.points`
        -- interpolation can span an excluded point sitting between them in
        frequency.
        """
        usable = sorted(self.usable(), key=lambda point: point.frequency_hz)
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

    def plot(self, title: Optional[str] = None) -> Any:
        """Magnitude over phase against log frequency; returns the Figure.

        Excluded points are plotted as NaN rather than omitted: matplotlib
        breaks the line and skips the marker at a NaN, leaving a real gap at
        that frequency. Omitting the point outright would let semilogx draw
        one continuous line straight through the excluded region -- an
        interpolated claim where no measurement exists. A gap is honest
        about a measurement that was not made; a plotted zero (or an
        unbroken line across the hole) is a claim.
        """
        import matplotlib.pyplot as plt  # Imported here so the module stays usable headless.

        if not self.usable():
            raise ValueError("Cannot plot a frequency response with no usable points")

        frequencies = [point.frequency_hz for point in self.points]
        gains = [float("nan") if point.gain_db is None else point.gain_db for point in self.points]
        phases = [float("nan") if point.phase_deg is None else point.phase_deg for point in self.points]
        figure, (magnitude_axis, phase_axis) = plt.subplots(2, 1, sharex=True, figsize=(8, 6))
        magnitude_axis.semilogx(frequencies, gains, marker="o")
        magnitude_axis.set_ylabel("Gain (dB)")
        magnitude_axis.grid(True, which="both", alpha=0.3)
        phase_axis.semilogx(frequencies, phases, marker="o")
        phase_axis.set_ylabel("Phase (degrees)")
        phase_axis.set_xlabel("Frequency (Hz)")
        phase_axis.grid(True, which="both", alpha=0.3)
        if title:
            magnitude_axis.set_title(title)
        figure.tight_layout()
        return figure

    def to_csv(self, path: Union[str, "Path"]) -> None:
        """Write the points as CSV behind a `#`-commented metadata header.

        The header explains where the numbers came from; the rows below it are
        plain CSV. pandas.read_csv(comment="#") reads the file unaided. numpy's
        genfromtxt does NOT: names=True takes the first line as the header
        whether or not it is a comment, so drop the `#` lines first (a generator
        filtering them, or skip_header=). An unmeasured gain is an EMPTY field
        rather than a sentinel -- a reader that treats it as a number gets NaN,
        not a plausible value.
        """
        with open(path, "w", newline="", encoding="utf-8") as handle:
            for line in self._metadata_lines():
                handle.write(f"# {line}\n")
            writer = csv.writer(handle)
            writer.writerow(_CSV_COLUMNS)
            for point in self.points:
                writer.writerow(
                    [
                        point.frequency_hz,
                        "" if point.gain_db is None else point.gain_db,
                        "" if point.phase_deg is None else point.phase_deg,
                        "" if point.reference_vpp is None else point.reference_vpp,
                        "" if point.response_vpp is None else point.response_vpp,
                        "" if point.cycles_in_window is None else point.cycles_in_window,
                        "" if point.samples_per_cycle is None else point.samples_per_cycle,
                        "" if point.volts_per_div is None else point.volts_per_div,
                        point.excluded_reason or "",
                    ]
                )

    def _metadata_lines(self) -> List[str]:
        instrument = getattr(self.provenance, "instrument", None)
        if instrument is None:
            identity, firmware = "unknown", "unknown"
        else:
            identity = " ".join(part for part in (instrument.manufacturer, instrument.model, instrument.serial) if part) or "unknown"
            firmware = instrument.firmware or "unknown"
        settings = self.settings
        return [
            "SCPI-Instrument-Control frequency response sweep",
            f"instrument: {identity}",
            f"firmware: {firmware}",
            f"library_version: {getattr(self.provenance, 'library_version', None) or 'unknown'}",
            f"acquired_at: {getattr(self.provenance, 'acquired_at', None) or 'unknown'}",
            f"reference_channel: {settings.reference_channel}, response_channel: {settings.response_channel}, awg_channel: {settings.awg_channel}",
            f"amplitude_vpp: {settings.amplitude_vpp}, settle_s: {settings.settle_s}, autorange: {settings.autorange}",
            f"points_requested: {len(settings.frequencies)}, points_measured: {len(self.usable())}",
        ]
