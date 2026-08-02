"""Frequency response (Bode) measurement: sweep a source, capture, estimate.

See docs/user-guide/frequency-response.md. Every accuracy claim in this package
is validated against a mock instrument and an analytic RC model, never against
real hardware -- there is no function generator on the development bench.
"""

from scpi_control.frequency_response.estimate import estimate_point, tone_at
from scpi_control.frequency_response.model import FrequencyResponse, ResponsePoint, SweepSettings

# This rebinds the package's `sweep` attribute to the function below, shadowing the
# `sweep` submodule of the same name -- `from scpi_control.frequency_response import
# sweep` always gets the function (the supported form), but a bare
# `import scpi_control.frequency_response.sweep` also gets the function, not the
# submodule. Reach the submodule itself via importlib.import_module(...) if needed.
from scpi_control.frequency_response.sweep import log_spaced_frequencies, sweep

__all__ = ["FrequencyResponse", "ResponsePoint", "SweepSettings", "estimate_point", "log_spaced_frequencies", "sweep", "tone_at"]
