"""Pure analysis computations for the session poll loop.

Everything here operates on already-acquired WaveformData (no instrument
I/O) and returns stream-frame dicts or None when uncomputable. The poll
loop turns None into a one-shot cleared frame (the `_shown` pattern).
"""

from typing import Any, Dict, Optional

import numpy as np

from scpi_control.analysis import FFTAnalyzer

MAX_FFT_POINTS = 65536  # truncation bounds per-tick compute without aliasing (costs only resolution)
MAX_SPECTRUM_BINS = 2000

_analyzer = FFTAnalyzer()


def _max_pool(values: np.ndarray, cap: int):
    """Decimate a spectrum preserving peaks: max over ceil(n/cap)-sized groups.

    Stride decimation would drop narrow peaks — the whole point of a spectrum.
    Returns (pooled_values, pool_size).
    """
    n = len(values)
    if n <= cap:
        return values, 1
    pool = -(-n // cap)  # ceiling division keeps len <= cap
    pad = (-n) % pool
    padded = np.pad(values, (0, pad), constant_values=-np.inf)
    return padded.reshape(-1, pool).max(axis=1), pool


def empty_spectrum_frame(config: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "spectrum", "channel": config["channel"], "f0": 0.0, "df": 1.0, "points": [], "db": config["db"], "window": config["window"], "peaks": [], "thd": None}


def spectrum_frame(config: Dict[str, Any], acquired: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = acquired.get("C{0}".format(config["channel"]))
    if data is None or len(data.voltage) < 2:
        return None
    if len(data.voltage) > MAX_FFT_POINTS:
        data = type(data)(time=data.time[:MAX_FFT_POINTS], voltage=data.voltage[:MAX_FFT_POINTS], channel=data.channel)
    result = _analyzer.compute_fft(data, window=config["window"], output_db=config["db"])
    if result is None:
        return None
    peaks = [[float(f), float(m)] for f, m in result.get_peak_frequency(5)]
    thd = None
    if peaks:
        thd_value = FFTAnalyzer.calculate_thd(result, peaks[0][0])
        thd = float(thd_value) if thd_value is not None else None
    df = float(result.frequency[1] - result.frequency[0]) if len(result.frequency) > 1 else 1.0
    pooled, pool = _max_pool(result.magnitude, MAX_SPECTRUM_BINS)
    return {
        "type": "spectrum",
        "channel": config["channel"],
        "f0": 0.0,
        "df": df * pool,
        "points": [float(v) for v in pooled],
        "db": config["db"],
        "window": config["window"],
        "peaks": peaks,
        "thd": thd,
    }
