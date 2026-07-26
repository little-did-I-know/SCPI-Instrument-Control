"""Device-under-test models applied between a signal source and an instrument input.

Written for the mock's AWG -> scope loopback, so a stimulus arrives at the scope
shaped the way real hardware would shape it, but public and usable on its own:
`apply` filters any float array.
"""

import math

import numpy as np
from scipy import signal as scipy_signal

from scpi_control import exceptions

# After 5 time constants a first-order response has settled to within 0.7% of its
# final value -- far below the int8 quantization the mock's scope path applies
# afterwards, so a longer lead-in would cost samples and buy nothing.
_WARMUP_TIME_CONSTANTS = 5

# Backstop on the lead-in, mirroring signal_synth._MAX_RINGING_KERNEL_SAMPLES.
# A near-zero cutoff makes tau -- and so the warmup -- unbounded otherwise.
_MAX_WARMUP_SAMPLES = 200_000


class RCLowPass:
    """A first-order RC low-pass standing in for a device under test.

        y[n] = y[n-1] + alpha * (x[n] - y[n-1]),   alpha = 1 - exp(-dt / tau)

    `alpha` is the exact zero-order-hold (impulse-invariant) discretisation of a
    continuous RC network sampled at `dt` -- not the backward-Euler approximation
    `dt / (tau + dt)`, which agrees with `exp(-dt/tau)` only to second order in
    `dt/tau`. That distinction matters here specifically because `signal_synth`'s
    "exponential" kind is a closed-form solution built directly from
    `exp(-t/tau)`: filtering a square wave through this class is mathematically
    the same construction, so using the exact discretisation makes the two
    agree to near machine precision instead of leaving a ~2% floor between two
    different approximations of the same physics (see
    `tests/test_loopback_capture.py`'s cross-validation test).

    **This filter is stateful**, unlike everything in `signal_synth`, which is
    closed-form precisely so that streamed chunks and consecutive mock
    acquisitions join seamlessly. The recurrence carries `y` across samples, so a
    caller must hand `apply` a buffer that already includes `warmup_samples()` of
    lead-in and discard that lead-in afterwards (see `connection/mock/synth.py`'s
    `raw_volts`). Filtering a bare capture would start from `y = 0` and put a
    settling transient at the head of every acquisition -- the exact defect the
    closed-form generators were written to avoid.
    """

    def __init__(self, cutoff_hz: float) -> None:
        if not np.isfinite(cutoff_hz) or cutoff_hz <= 0:
            raise exceptions.InvalidParameterError(f"cutoff_hz must be a positive finite number: {cutoff_hz}")
        self.cutoff_hz = float(cutoff_hz)
        self.tau = 1.0 / (2.0 * math.pi * self.cutoff_hz)

    def warmup_samples(self, sample_rate: float) -> int:
        """Lead-in length the caller must render before the window it wants."""
        if not np.isfinite(sample_rate) or sample_rate <= 0:
            raise exceptions.InvalidParameterError(f"sample_rate must be a positive finite number: {sample_rate}")
        return int(min(_MAX_WARMUP_SAMPLES, max(1, round(_WARMUP_TIME_CONSTANTS * self.tau * sample_rate))))

    def apply(self, samples: np.ndarray, sample_rate: float) -> np.ndarray:
        """Filter `samples`, including whatever lead-in the caller prepended."""
        if not np.isfinite(sample_rate) or sample_rate <= 0:
            raise exceptions.InvalidParameterError(f"sample_rate must be a positive finite number: {sample_rate}")
        dt = 1.0 / sample_rate
        alpha = 1.0 - math.exp(-dt / self.tau)
        # scipy rather than a Python loop: a 14,000-point capture is the common
        # case and a deep-memory record is far larger.
        return scipy_signal.lfilter([alpha], [1.0, -(1.0 - alpha)], np.asarray(samples, dtype=float))
