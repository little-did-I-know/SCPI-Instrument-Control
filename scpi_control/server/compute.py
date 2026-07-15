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


def filtered_waveform(config: Dict[str, Any], acquired: Dict[str, Any]):
    """Apply the configured Butterworth filter to its source channel's waveform."""
    data = acquired.get("C{0}".format(config["source"]))
    if data is None or len(data.voltage) < 2:
        return None
    kind = config["kind"]
    low = config["cutoff_low"]
    high = config["cutoff_high"]
    order = config["order"]
    if kind == "lowpass" and high is not None:
        return _analyzer.apply_lowpass_filter(data, high, order)
    if kind == "highpass" and low is not None:
        return _analyzer.apply_highpass_filter(data, low, order)
    if kind == "bandpass" and low is not None and high is not None:
        return _analyzer.apply_bandpass_filter(data, low, high, order)
    return None


def reference_stats(reference: Dict[str, Any], acquired: Dict[str, Any]) -> Dict[str, Any]:
    """Correlation + max deviation of the live source-channel trace vs the reference.

    Mirrors ReferenceWaveform.calculate_correlation/_difference semantics
    (interpolate onto the live grid when lengths differ) without instantiating
    the store. Degrades every failure to nulls — never raises.
    """
    stats: Dict[str, Any] = {"type": "reference_stats", "correlation": None, "max_deviation": None}
    channel = reference.get("channel")
    data = acquired.get("C{0}".format(channel)) if channel else None
    if data is None or len(data.voltage) < 2:
        return stats
    try:
        ref_voltage = np.asarray(reference["data"]["voltage"], dtype=float)
        if len(data.voltage) != len(ref_voltage):
            ref_time = np.asarray(reference["data"]["time"], dtype=float)
            ref_voltage = np.interp(data.time, ref_time, ref_voltage)
        stats["max_deviation"] = float(np.max(np.abs(data.voltage - ref_voltage)))
        with np.errstate(divide="ignore", invalid="ignore"):
            correlation = float(np.corrcoef(data.voltage, ref_voltage)[0, 1])
        stats["correlation"] = correlation if np.isfinite(correlation) else None
    except Exception:
        return {"type": "reference_stats", "correlation": None, "max_deviation": None}
    return stats
