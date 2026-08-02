"""Frequency response (Bode) measurement: sweep a source, capture, estimate.

See docs/user-guide/frequency-response.md. Every accuracy claim in this package
is validated against a mock instrument and an analytic RC model, never against
real hardware -- there is no function generator on the development bench.
"""

from scpi_control.frequency_response.estimate import estimate_point, tone_at
from scpi_control.frequency_response.model import FrequencyResponse, ResponsePoint, SweepSettings
from scpi_control.frequency_response.orchestrate import log_spaced_frequencies, sweep

__all__ = ["FrequencyResponse", "ResponsePoint", "SweepSettings", "estimate_point", "log_spaced_frequencies", "sweep", "tone_at"]
