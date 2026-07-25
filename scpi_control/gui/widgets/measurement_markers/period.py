"""Signal-period estimation shared by the frequency and timing markers.

Extracted from FrequencyMarker so the duty-cycle calc uses the *same* edge
detection -- the two must never disagree about the period of one gated signal.
Unlike the old private version, this returns None when no period can be
confidently detected instead of falling back to the gate width; a fabricated
period is exactly what made the duty-cycle marker wrong (audit H13).
"""

import logging
from typing import Optional

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


def estimate_period(time: np.ndarray, voltage: np.ndarray) -> Optional[float]:
    """Estimate the signal period in seconds, or None if it cannot be measured.

    Tries rising zero-crossings first, then peak spacing. Returns None when
    neither finds at least two reference points (fewer than one full cycle, or
    an edgeless/flat gate) -- callers report N/A rather than a wrong number.
    """
    # Method 1: rising zero-crossings of the AC-coupled signal.
    try:
        voltage_ac = voltage - np.mean(voltage)
        crossings = []
        for i in range(len(voltage_ac) - 1):
            if voltage_ac[i] <= 0 and voltage_ac[i + 1] > 0:
                t_cross = time[i] - voltage_ac[i] * (time[i + 1] - time[i]) / (voltage_ac[i + 1] - voltage_ac[i])
                crossings.append(t_cross)
        if len(crossings) >= 2:
            return float(np.mean(np.diff(crossings)))
    except Exception as exc:  # pragma: no cover - defensive; degenerate arrays
        logger.debug("Zero-crossing period estimate failed: %s", exc)

    # Method 2: peak spacing.
    try:
        peaks, _ = signal.find_peaks(voltage, distance=max(1, len(voltage) // 10))
        if len(peaks) >= 2:
            return float(np.mean(np.diff(time[peaks])))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Peak-detection period estimate failed: %s", exc)

    # No confident estimate. Do NOT fall back to the gate width.
    return None
