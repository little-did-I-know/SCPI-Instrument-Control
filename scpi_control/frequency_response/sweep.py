"""Drive a source across frequencies and measure what comes back.

The orchestration half of the package: it decides what the instruments are set
to, and hands array pairs to estimate.py, which decides what they mean.
"""

import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from scpi_control import exceptions
from scpi_control.automation import DataCollector
from scpi_control.frequency_response.estimate import estimate_point
from scpi_control.frequency_response.model import FrequencyResponse, ResponsePoint, SweepSettings
from scpi_control.frequency_response.ranging import MIN_SAMPLES_PER_CYCLE, choose_timebase, choose_volts_per_div
from scpi_control.provenance import AcquisitionProvenance
from scpi_control.waveform import WaveformData

logger = logging.getLogger(__name__)


def log_spaced_frequencies(start_hz: float, stop_hz: float, points_per_decade: int = 10) -> List[float]:
    """Logarithmically spaced frequencies from start to stop, both included."""
    if start_hz <= 0 or stop_hz <= 0:
        raise exceptions.InvalidParameterError(f"Frequencies must be positive, not {start_hz!r} to {stop_hz!r}")
    if stop_hz <= start_hz:
        raise exceptions.InvalidParameterError(f"stop_hz ({stop_hz}) must not be at or below start_hz ({start_hz})")
    if points_per_decade < 1:
        raise exceptions.InvalidParameterError(f"points_per_decade must be at least 1, not {points_per_decade!r}")
    decades = math.log10(stop_hz / start_hz)
    # Below one point per decade of span, the requested density rounds to
    # zero (e.g. 100-101 Hz at 1 point/decade: decades ~= 0.00432). Clamp
    # rather than reject: a narrow sweep is a legitimate request -- zooming
    # into a resonance, say -- and count=1 yields [start_hz, stop_hz], the
    # honest minimum answer to "sweep from here to there".
    count = max(int(round(decades * points_per_decade)), 1)
    return [start_hz * 10 ** (index * decades / count) for index in range(count + 1)]


def _resolve_frequencies(start_hz: Optional[float], stop_hz: Optional[float], points_per_decade: int, frequencies: Optional[List[float]]) -> Tuple[float, ...]:
    if frequencies is not None and (start_hz is not None or stop_hz is not None):
        raise exceptions.InvalidParameterError("Pass either frequencies or start_hz/stop_hz, not both")
    if frequencies is not None:
        if not frequencies:
            raise exceptions.InvalidParameterError("frequencies must not be empty")
        if any(frequency <= 0 for frequency in frequencies):
            raise exceptions.InvalidParameterError(f"Frequencies must be positive: {frequencies!r}")
        return tuple(float(frequency) for frequency in frequencies)
    if start_hz is None or stop_hz is None:
        raise exceptions.InvalidParameterError("Provide start_hz and stop_hz, or an explicit frequencies list")
    return tuple(log_spaced_frequencies(start_hz, stop_hz, points_per_decade))


def _snapshot_awg(output: Any) -> Dict[str, Any]:
    """Read back what the sweep is about to overwrite, best effort."""
    snapshot: Dict[str, Any] = {}
    for name in ("function", "frequency", "amplitude", "enabled"):
        try:
            snapshot[name] = getattr(output, name)
        except Exception:  # noqa: BLE001 - a source that cannot report a setting still deserves a sweep
            logger.warning("Could not read AWG %s before the sweep; it will not be restored", name)
    return snapshot


def _restore_awg(output: Any, snapshot: Dict[str, Any]) -> None:
    """Put the source back. Never raises: a failed restore must not mask a result."""
    # Output state last: re-enabling before the waveform is back would emit a
    # burst of the sweep's last frequency into the DUT.
    for name in ("function", "frequency", "amplitude", "enabled"):
        if name not in snapshot:
            continue
        try:
            setattr(output, name, snapshot[name])
        except Exception as error:  # noqa: BLE001
            logger.warning("Could not restore AWG %s to %r: %s", name, snapshot[name], error)


def sweep(
    scope: Any,
    awg: Any,
    *,
    reference_channel: int,
    response_channel: int,
    awg_channel: int = 1,
    start_hz: Optional[float] = None,
    stop_hz: Optional[float] = None,
    points_per_decade: int = 10,
    frequencies: Optional[List[float]] = None,
    amplitude_vpp: float = 1.0,
    settle_s: float = 0.05,
    autorange: bool = True,
    on_point: Optional[Callable[[ResponsePoint], None]] = None,
) -> FrequencyResponse:
    """Measure a frequency response by stepping the AWG and capturing both channels.

    Drives `awg_channel` with a sine at `amplitude_vpp` and restores that
    channel's prior state on exit. Scope state is deliberately left where the
    sweep ended: only the source is driving something, and the final ranging is
    worth being able to inspect.

    Raises:
        InvalidParameterError: on any argument problem, before any wire traffic.
        FrequencySweepError: if the session fails mid-sweep; `.partial` holds
            the points measured so far.
    """
    if reference_channel == response_channel:
        raise exceptions.InvalidParameterError(f"reference_channel and response_channel must be distinct, both are {reference_channel}")
    if amplitude_vpp <= 0:
        raise exceptions.InvalidParameterError(f"amplitude_vpp must be positive, not {amplitude_vpp!r}")
    if settle_s < 0:
        raise exceptions.InvalidParameterError(f"settle_s must not be negative, not {settle_s!r}")
    resolved = _resolve_frequencies(start_hz, stop_hz, points_per_decade, frequencies)

    output = awg.get_channel(awg_channel)
    if output is None:
        raise exceptions.InvalidParameterError(f"The function generator has no channel {awg_channel}")

    # Resolved here, before the try below, and not inside it: InvalidParameterError
    # is a SiglentError, and the try wraps mid-sweep SiglentErrors into
    # FrequencySweepError. A bad channel number is an argument mistake, not a
    # sweep that started and then failed on the wire, so it must propagate
    # unchanged. (See the channel-enable step inside the try, which uses these
    # already-validated objects instead of re-resolving them.)
    channels = {}
    for channel_number in (reference_channel, response_channel):
        channel = scope.get_channel(channel_number)
        if channel is None:
            raise exceptions.InvalidParameterError(f"The oscilloscope has no channel {channel_number}")
        channels[channel_number] = channel

    settings = SweepSettings(
        reference_channel=reference_channel,
        response_channel=response_channel,
        awg_channel=awg_channel,
        frequencies=resolved,
        amplitude_vpp=amplitude_vpp,
        settle_s=settle_s,
        autorange=autorange,
    )
    result = FrequencyResponse(settings=settings)
    collector = DataCollector.from_scope(scope)
    snapshot = _snapshot_awg(output)

    try:
        for channel in channels.values():
            if not channel.enabled:
                channel.enabled = True

        output.function = "SINE"
        output.amplitude = amplitude_vpp
        output.enabled = True

        for index, frequency in enumerate(resolved):
            output.frequency = frequency
            if settle_s > 0:
                time.sleep(settle_s)
            point = _measure_point(scope, collector, settings, frequency, first=(index == 0))
            result.points.append(point)
            if result.provenance is None:
                result.provenance = _first_provenance(collector, settings)
            if point.gain_db is not None and point.samples_per_cycle < MIN_SAMPLES_PER_CYCLE:
                logger.warning("Point at %.1f Hz has only %.1f samples per cycle; its phase is coarse", point.frequency_hz, point.samples_per_cycle)
            if on_point is not None:
                on_point(point)
    except exceptions.SiglentError as error:
        raise exceptions.FrequencySweepError(f"Sweep stopped after {len(result.points)} of {len(resolved)} points: {error}", partial=result) from error
    finally:
        _restore_awg(output, snapshot)

    excluded = [point for point in result.points if point.gain_db is None]
    if excluded:
        logger.warning("%d of %d points were not measurable; first reason: %s", len(excluded), len(result.points), excluded[0].excluded_reason)
    return result


def _capture_pair(collector: DataCollector, settings: SweepSettings) -> Tuple[Optional[WaveformData], Optional[WaveformData]]:
    """One acquisition, both channels. Missing keys are normal: capture_single
    logs and drops a channel whose read failed (automation.py:215-222)."""
    captures = collector.capture_single([settings.reference_channel, settings.response_channel])
    return captures.get(settings.reference_channel), captures.get(settings.response_channel)


def _measure_point(scope: Any, collector: DataCollector, settings: SweepSettings, frequency: float, first: bool) -> ResponsePoint:
    """Range for `frequency`, capture both channels, and estimate one point."""
    scope.timebase = choose_timebase(frequency)
    reference, response = _capture_pair(collector, settings)

    if settings.autorange and response is not None:
        chosen = choose_volts_per_div(float(response.voltage.max() - response.voltage.min()))
        if chosen is not None and chosen != response.voltage_scale:
            scope.get_channel(settings.response_channel).voltage_scale = chosen
            reference, response = _capture_pair(collector, settings)
        # The reference is ranged once: the drive amplitude is constant by
        # construction, so re-ranging it every point spends captures to reach
        # the same answer.
        if first and reference is not None:
            reference_scale = choose_volts_per_div(float(reference.voltage.max() - reference.voltage.min()))
            if reference_scale is not None and reference_scale != reference.voltage_scale:
                scope.get_channel(settings.reference_channel).voltage_scale = reference_scale
                reference, response = _capture_pair(collector, settings)

    if reference is None or response is None:
        missing = settings.reference_channel if reference is None else settings.response_channel
        return ResponsePoint(frequency_hz=frequency, gain_db=None, phase_deg=None, excluded_reason=f"capture failed for channel {missing}")

    return estimate_point(reference, response, frequency)


def _first_provenance(collector: DataCollector, settings: SweepSettings) -> Optional[Any]:
    """Snapshot the scope once. Instrument identity does not change mid-sweep,
    and the settings that do are already on each ResponsePoint."""
    try:
        return AcquisitionProvenance.from_scope(collector.scope, channels=[settings.reference_channel, settings.response_channel])
    except Exception as error:  # noqa: BLE001 - provenance is a record, not a requirement
        logger.warning("Could not record provenance for the sweep: %s", error)
        return None
